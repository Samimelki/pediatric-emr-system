import docx
import sqlite3
import re
from datetime import datetime
import json
from typing import Dict, Optional, List, Tuple
import os
from word_document_manager import WordDocumentManager
from emr_config import emr_config

class WordDocumentImporter:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect_db(self) -> sqlite3.Connection:
        """Create a database connection."""
        return sqlite3.connect(self.db_path)

    def _parse_date_string(self, date_str_input: Optional[str], doc_path_for_warning: str, field_name: str = "date") -> Optional[str]:
        """Robustly parses a date string from various formats into YYYY-MM-DD."""
        if not date_str_input or not date_str_input.strip():
            return None

        str_to_parse_final = date_str_input.strip()
        parsed_dt_iso_str = None

        # 1. Handle Year-Only (e.g., "1940")
        if re.fullmatch(r'\d{4}', str_to_parse_final):
            year = int(str_to_parse_final)
            if 1900 <= year <= datetime.now().year + 5:
                print(f"Info: Parsed '{str_to_parse_final}' as year-only for {field_name}. Defaulting to YYYY-01-01. Path: {doc_path_for_warning}")
                return f"{year:04d}-01-01"

        # 2. Handle Month-Year (e.g., "06-1969", "06/1969")
        month_year_match = re.fullmatch(r'(\d{1,2})[./-](\d{4})', str_to_parse_final)
        if month_year_match:
            month, year = int(month_year_match.group(1)), int(month_year_match.group(2))
            if 1 <= month <= 12 and 1900 <= year <= datetime.now().year + 5:
                print(f"Info: Parsed '{str_to_parse_final}' as month-year for {field_name}. Defaulting to YYYY-MM-01. Path: {doc_path_for_warning}")
                return f"{year:04d}-{month:02d}-01"

        # 3. Handle "Month Day(st/nd/rd/th) Year" (e.g., "February 3rd 1945", "Feb 3 1945")
        month_names = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        textual_month_match = re.search(
            r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,\s*|\s+)(\d{4})\b',
            str_to_parse_final,
            re.IGNORECASE
        )
        if textual_month_match:
            month_str, day_str, year_str = textual_month_match.groups()
            month = month_names.get(month_str[:3].lower())
            day = int(day_str)
            year = int(year_str)
            if month and (1 <= day <= 31) and (1900 <= year <= datetime.now().year + 5):
                try:
                    # Validate day for month/year combination
                    dt_obj = datetime(year, month, day)
                    print(f"Info: Parsed textual month date '{str_to_parse_final}' for {field_name}. Path: {doc_path_for_warning}")
                    return dt_obj.strftime('%Y-%m-%d')
                except ValueError:
                    pass # Invalid day for month (e.g., Feb 30)

        # 4. Handle Season Year (e.g., "Spring 1936")
        season_map = {
            'spring': '03-01', 'summer': '06-01',
            'autumn': '09-01', 'fall': '09-01',
            'winter': '12-01'
        }
        season_year_match = re.search(r'(Spring|Summer|Autumn|Fall|Winter)\s+(\d{4})\b', str_to_parse_final, re.IGNORECASE)
        if season_year_match:
            season, year_str = season_year_match.groups()
            year = int(year_str)
            month_day = season_map.get(season.lower())
            if month_day and (1900 <= year <= datetime.now().year + 5):
                print(f"Info: Parsed season-year '{str_to_parse_final}' for {field_name}. Defaulting to {month_day}. Path: {doc_path_for_warning}")
                return f"{year:04d}-{month_day}"

        # 5. Existing Regex for d/m/y and y/m/d numeric formats
        # Using a more specific regex here, then trying formats
        date_pattern_match = re.search(r'(\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|\b\d{4}[./-]\d{1,2}[./-]\d{1,2}\b)', str_to_parse_final)
        numeric_date_str_to_parse = str_to_parse_final # Default to full string if specific pattern not found
        if date_pattern_match:
            numeric_date_str_to_parse = date_pattern_match.group(1)
        
        formats_to_try = [
            '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%Y-%m-%d',
            '%d-%m-%Y', '%m-%d-%Y',
            '%d.%m.%Y', '%m.%d.%Y', '%Y.%m.%d',
            '%d/%m/%y', '%m/%d/%y',
            '%d-%m-%y', '%m-%d-%y',
            '%d.%m.%y', '%m.%d.%y',
        ]

        for fmt in formats_to_try:
            try:
                normalized_date_val = numeric_date_str_to_parse.replace('-', '/').replace('.', '/')
                dt_obj = datetime.strptime(normalized_date_val, fmt)
                if '%y' in fmt.lower(): # Python's default %y handling (00-68 -> 20xx, 69-99 -> 19xx) is usually okay
                    pass 
                if not (1900 <= dt_obj.year <= datetime.now().year + 5):
                    continue
                parsed_dt_iso_str = dt_obj.strftime('%Y-%m-%d')
                break
            except ValueError:
                continue
        
        if parsed_dt_iso_str:
            return parsed_dt_iso_str

        # Final fallback: if input contains "DOB:" try to strip it and re-parse the remainder with a simpler set of rules
        if "dob:" in date_str_input.lower():
            remainder_after_dob = date_str_input.lower().split("dob:",1)[-1].strip()
            if remainder_after_dob and remainder_after_dob != date_str_input.lower().strip(): # Avoid infinite recursion
                # print(f"Retrying parse after stripping 'DOB:' for: {remainder_after_dob}")
                return self._parse_date_string(remainder_after_dob, doc_path_for_warning, field_name + " (after DOB strip)")

        print(f"Warning: Could not parse {field_name} from input '{date_str_input}'. Path: {doc_path_for_warning}")
        return None

    def get_file_creation_date(self, file_path: str) -> Optional[str]:
        """Get the file creation date from Word document properties, fallback to filesystem date."""
        try:
            # Try to get creation date from Word document properties
            doc = docx.Document(file_path)
            created = doc.core_properties.created
            if created:
                # created is a datetime object
                return created.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"Warning: Could not get creation date from Word properties for {file_path}: {str(e)}. Will try filesystem date.")
        try:
            creation_time = os.path.getctime(file_path)
            creation_date_obj = datetime.fromtimestamp(creation_time)
            return creation_date_obj.strftime('%Y-%m-%d')
        except Exception as e:
            print(f"Error getting creation date for {file_path}: {str(e)}. Will attempt to use today.")
            return datetime.now().strftime('%Y-%m-%d')

    def parse_patient_doc(self, doc_path: str) -> Optional[Dict]:
        """Parse a Word document and extract patient information using stateful parsing for visits."""
        try:
            doc = docx.Document(doc_path)
            full_text_lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()] 

            if not full_text_lines:
                print(f"Document {doc_path} is empty after stripping blank paragraphs.")
                return None

            patient_data = {
                'first_name': '', 'last_name': '', 'date_of_birth': None,
                'sex': '', 'phone': '', 'address': '', 'email': '',
                'insurance': '', 'primary_physician': '',
                'pmh': '', 'psh': '', 'family_history': '',
                'medications': '', 'allergies': '',
                'smoker': False, 'smoker_details': '',
                'alcohol': False, 'alcohol_details': '',
                'visits': [],
                'vaccines': []
            }

            # 1. Name and potential DOB Parsing (from first line)
            start_line_for_visits_and_history = 1 # Default: after name line
            if full_text_lines:
                name_line = full_text_lines[0]
                name_parts = name_line.split()
                
                # Check if the last part of the name line could be a date
                potential_dob_from_name_line = None
                if len(name_parts) > 1:
                    last_part = name_parts[-1]
                    parsed_date_from_name = self._parse_date_string(last_part, doc_path, "DOB from name line")
                    if parsed_date_from_name:
                        patient_data['date_of_birth'] = parsed_date_from_name
                        name_parts_for_name = name_parts[:-1]
                        # --- Improved name parsing logic ---
                        if len(name_parts_for_name) == 2:
                            # Two words: first is first name, second is last name
                            patient_data['first_name'] = name_parts_for_name[0]
                            patient_data['last_name'] = name_parts_for_name[1]
                        elif len(name_parts_for_name) > 2 and '-' in name_parts_for_name[0]:
                            # First word has hyphen, treat as first name, rest as last name
                            patient_data['last_name'] = name_parts_for_name[0]
                            patient_data['fist_name'] = ' '.join(name_parts_for_name[1:])
                        else:
                            # Default: first is first name, rest is last name
                            if name_parts_for_name:
                                patient_data['first_name'] = name_parts_for_name[0]
                                if len(name_parts_for_name) > 1:
                                    patient_data['last_name'] = ' '.join(name_parts_for_name[1:])
                                else:
                                    patient_data['last_name'] = ''
                        start_line_for_visits_and_history = 1
                    else:
                        # No date found in the last part, treat whole line as name
                        if len(name_parts) == 2:
                            patient_data['first_name'] = name_parts[0]
                            patient_data['last_name'] = name_parts[1]
                        elif len(name_parts) > 2 and '-' in name_parts[0]:
                            patient_data['first_name'] = name_parts[0]
                            patient_data['last_name'] = ' '.join(name_parts[1:])
                        else:
                            if name_parts:
                                patient_data['first_name'] = name_parts[0]
                                if len(name_parts) > 1:
                                    patient_data['last_name'] = ' '.join(name_parts[1:])
                        start_line_for_visits_and_history = 1
                elif name_parts:
                    patient_data['first_name'] = name_parts[0]
                    start_line_for_visits_and_history = 1

            # 2. Date of Birth Parsing (Typically second line, IF NOT ALREADY FOUND)
            if patient_data['date_of_birth'] is None: # Only try parsing from line 2 if not found in line 1
                dob_line_candidate_index = 1 # This is the second line of the document
                if len(full_text_lines) > dob_line_candidate_index:
                    potential_dob_line_text = full_text_lines[dob_line_candidate_index]
                    non_date_keywords_for_dob_line = ['pmh', 'psh', 'medication', 'meds', 'allerg', 'history']
                    is_likely_history = any(keyword in potential_dob_line_text.lower() for keyword in non_date_keywords_for_dob_line)
                    contains_digits = bool(re.search(r'\d', potential_dob_line_text))

                    if is_likely_history and not contains_digits:
                        print(f"Info: Line {dob_line_candidate_index+1} '{potential_dob_line_text}' in {doc_path} looks like history, not DOB. Skipping it for DOB parsing.")
                        start_line_for_visits_and_history = max(start_line_for_visits_and_history, dob_line_candidate_index + 1)
                    else:
                        # Attempt to parse this line as DOB
                        parsed_dob = self._parse_date_string(potential_dob_line_text, doc_path, "Date of Birth from second line")
                        if parsed_dob:
                            patient_data['date_of_birth'] = parsed_dob
                            start_line_for_visits_and_history = max(start_line_for_visits_and_history, dob_line_candidate_index + 1) # Process after this DOB line
                        # If not parsed, it might be the start of history/notes, so start_line_for_visits_and_history doesn't necessarily change
                        # unless we are sure this line should have been DOB. The current logic correctly falls through.
                # If DOB still not found, it remains None. History/visits parsing starts from start_line_for_visits_and_history.
            else: # DOB was found on the first line
                 start_line_for_visits_and_history = 1 # History/visits start from the line after the combined Name/DOB line.

            # Ensure start_line_for_visits_and_history is at least 1 if Name/DOB took line 0.
            # If Name was on line 0, DOB on line 1, then history starts on line 2.
            # If Name+DOB was on line 0, history starts on line 1.
            # If Name on line 0, no DOB on line 1 (and line 1 becomes history), history starts on line 1.
            # The logic above tries to set start_line_for_visits_and_history correctly.
            # Quick check: if full_text_lines[0] was name AND dob, history starts at 1.
            # If full_text_lines[0] was name, full_text_lines[1] was dob, history starts at 2.
            # If full_text_lines[0] was name, full_text_lines[1] was NOT dob (e.g. history), history starts at 1.
            # The variable start_line_for_visits_and_history should already reflect this based on where DOB was found or skipped.

            patient_history_lines = []
            # --- Visit Parsing Logic ---
            visits_list = []
            current_visit_notes_collector = []
            current_visit_parsed_date = None
            doc_creation_date_iso = self.get_file_creation_date(doc_path)
            visit_date_line_pattern = re.compile(r"^\s*(\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})(.?)")
            parsing_state = 0 
            if len(full_text_lines) > start_line_for_visits_and_history:
                lines_iterator = iter(full_text_lines[start_line_for_visits_and_history:])
                for line_content in lines_iterator:
                    line_lower = line_content.lower()
                    potential_date_match = visit_date_line_pattern.match(line_content)
                    matched_date_str = None
                    if potential_date_match:
                        following_char = potential_date_match.group(2)
                        if not following_char or not following_char.isdigit():
                            matched_date_str = potential_date_match.group(1)
                    
                    is_patient_history_field = False
                    if parsing_state == 0: 
                        if 'pmh:' in line_lower or 'past medical history' in line_lower:
                            patient_data['pmh'] = (patient_data['pmh'] + ' ' + line_content.split(':',1)[-1].strip()).strip()
                            is_patient_history_field = True
                        elif 'psh:' in line_lower or 'past surgical history' in line_lower:
                            patient_data['psh'] = (patient_data['psh'] + ' ' + line_content.split(':',1)[-1].strip()).strip()
                            is_patient_history_field = True
                        elif line_lower.startswith('meds:') or line_lower.startswith('medications:'):
                            patient_data['medications'] = (patient_data['medications'] + ' ' + line_content.split(':',1)[-1].strip()).strip()
                            is_patient_history_field = True
                        elif 'allergies:' in line_lower or 'allergy:' in line_lower or (line_lower.startswith('allerg') and ':' in line_lower):
                            patient_data['allergies'] = (patient_data['allergies'] + ' ' + line_content.split(':',1)[-1].strip()).strip()
                            is_patient_history_field = True
                        elif 'nkda' in line_lower:
                            patient_data['allergies'] = 'NKDA'
                            is_patient_history_field = True
                        elif re.search(r'\b(smoker|smoking)\b', line_lower):
                            details = line_content.split(':',1)[-1].strip() if ':' in line_lower else line_content.strip()
                            patient_data['smoker'] = not (re.search(r'\bno\b', details.lower()) or 'non-smoker' in details.lower())
                            patient_data['smoker_details'] = details
                            is_patient_history_field = True
                        elif re.search(r'\b(alcohol|drinker|drinking)\b', line_lower):
                            details = line_content.split(':',1)[-1].strip() if ':' in line_lower else line_content.strip()
                            patient_data['alcohol'] = not (re.search(r'\bno\b', details.lower()) or 'non-drinker' in details.lower())
                            patient_data['alcohol_details'] = details
                            is_patient_history_field = True
                        elif 'fh:' in line_lower or 'family history:' in line_lower:
                            patient_data['family_history'] = (patient_data['family_history'] + ' ' + line_content.split(':',1)[-1].strip()).strip()
                            is_patient_history_field = True
                        elif line_lower.startswith('tel:') or line_lower.startswith('phone:'):
                             patient_data['phone'] = (patient_data['phone'] + ' ' + line_content.split(':',1)[-1].strip()).strip()
                             is_patient_history_field = True
                        
                        # Parse vaccines - look for patterns like "Vaccine Name: dd/mm/yyyy" or "Vaccine Name - dd/mm/yyyy"
                        vaccine_match = re.match(r'^(.+?)\s*[:\-]\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})\s*$', line_content.strip())
                        if vaccine_match and not is_patient_history_field:
                            vaccine_name = vaccine_match.group(1).strip()
                            vaccine_date_str = vaccine_match.group(2).strip()
                            
                            # Skip if it looks like a visit date (starts with year)
                            if not re.match(r'^\d{4}', vaccine_date_str):
                                # Parse the vaccine date
                                vaccine_date_iso = self._parse_date_string(vaccine_date_str, doc_path, f"Vaccine {vaccine_name}")
                                if vaccine_date_iso:
                                    patient_data['vaccines'].append({
                                        'vaccine_name': vaccine_name,
                                        'vaccine_date': vaccine_date_iso,
                                        'raw_entry': line_content.strip()
                                    })
                                    is_patient_history_field = True  # Don't add to visit notes

                        if is_patient_history_field:
                            patient_history_lines.append(line_content)
                            continue  # Do not add to visit notes

                        if matched_date_str and not is_patient_history_field:
                            if current_visit_notes_collector:
                                visits_list.append({'visit_date': doc_creation_date_iso, 'notes': '\n'.join(current_visit_notes_collector).strip()})
                                current_visit_notes_collector = []
                            current_visit_parsed_date = self._parse_date_string(matched_date_str, doc_path, "Visit Date")
                            remaining_text = line_content[len(potential_date_match.group(0)):].strip()
                            if remaining_text: current_visit_notes_collector.append(remaining_text)
                            parsing_state = 2
                        elif not is_patient_history_field and line_content.strip():
                            current_visit_notes_collector.append(line_content)
                            parsing_state = 1

                    elif parsing_state == 1:
                        if matched_date_str:
                            if current_visit_notes_collector:
                                visits_list.append({'visit_date': doc_creation_date_iso, 'notes': '\n'.join(current_visit_notes_collector).strip()})
                            current_visit_parsed_date = self._parse_date_string(matched_date_str, doc_path, "Visit Date")
                            current_visit_notes_collector = []
                            remaining_text = line_content[len(potential_date_match.group(0)):].strip()
                            if remaining_text: current_visit_notes_collector.append(remaining_text)
                            parsing_state = 2
                        else:
                            current_visit_notes_collector.append(line_content)
                    
                    elif parsing_state == 2:
                        if matched_date_str:
                            if current_visit_parsed_date or current_visit_notes_collector:
                                visits_list.append({'visit_date': current_visit_parsed_date, 'notes': '\n'.join(current_visit_notes_collector).strip()})
                            current_visit_parsed_date = self._parse_date_string(matched_date_str, doc_path, "Visit Date")
                            current_visit_notes_collector = []
                            remaining_text = line_content[len(potential_date_match.group(0)):].strip()
                            if remaining_text: current_visit_notes_collector.append(remaining_text)
                        else:
                            current_visit_notes_collector.append(line_content)
            
            if parsing_state == 0:
                if current_visit_notes_collector:
                     visits_list.append({'visit_date': doc_creation_date_iso, 'notes': '\n'.join(current_visit_notes_collector).strip()})
            elif parsing_state == 1:
                if current_visit_notes_collector:
                    visits_list.append({'visit_date': doc_creation_date_iso, 'notes': '\n'.join(current_visit_notes_collector).strip()})
            elif parsing_state == 2:
                if current_visit_parsed_date or current_visit_notes_collector:
                    visits_list.append({'visit_date': current_visit_parsed_date, 'notes': '\n'.join(current_visit_notes_collector).strip()})

            patient_data['visits'] = [v for v in visits_list if v.get('notes') or v.get('visit_date')]
            patient_data['patient_history_text'] = '\n'.join(patient_history_lines).strip()
            # Set raw_dossier_text to only the parsed visits
            patient_data['raw_dossier_text'] = "\n\n".join(
                f"{v['visit_date'] or '[No Date]'}\n{v['notes']}" for v in patient_data['visits'] if v.get('notes')
            )

            for key in ['pmh', 'psh', 'medications', 'allergies', 'family_history', 'phone']:
                if isinstance(patient_data[key], str):
                    patient_data[key] = ' '.join(patient_data[key].split())
            
            return patient_data

        except Exception as e:
            print(f"CRITICAL Error parsing document {doc_path}: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def get_or_create_patient(self, cursor: sqlite3.Cursor, patient_data: Dict, new_doc_mrn: Optional[str] = None) -> int:
        """Get existing patient ID by name/DOB or MRN, or create new patient. Handles None for date_of_birth."""
        dob_for_db = patient_data.get('date_of_birth')
        if dob_for_db == '': dob_for_db = None

        first_name_norm = patient_data.get('first_name', '').strip().lower()
        last_name_norm = patient_data.get('last_name', '').strip().lower()

        # 1. Try to find patient by First Name, Last Name, and DOB (if DOB is available)
        existing_patient_id = None
        if first_name_norm and last_name_norm and dob_for_db:
            cursor.execute("""
                SELECT id, mrn FROM Patients 
                WHERE lower(first_name) = ? AND lower(last_name) = ? AND (date_of_birth = ? OR naissance_date = ?)
            """, (first_name_norm, last_name_norm, dob_for_db, dob_for_db))
            result = cursor.fetchone()
            if result:
                existing_patient_id = result[0]
                existing_mrn = result[1]
                print(f"Info: Found existing patient ID {existing_patient_id} (MRN: {existing_mrn}) by matching Name & DOB for document data: {first_name_norm} {last_name_norm}, {dob_for_db}. Current doc MRN (if any): {new_doc_mrn or patient_data.get('mrn')}")
                
                # Update existing patient to ensure both date fields are synchronized
                if dob_for_db:
                    cursor.execute("""
                        UPDATE Patients 
                        SET date_of_birth = ?, naissance_date = ? 
                        WHERE id = ? AND (date_of_birth IS NULL OR naissance_date IS NULL)
                    """, (dob_for_db, dob_for_db, existing_patient_id))
                    print(f"Info: Synchronized birth date fields for existing patient ID {existing_patient_id}")
        
        # 2. If not found by Name/DOB, and an MRN is provided in patient_data, try by MRN
        #    The `new_doc_mrn` is the one generated by batch import or passed as override.
        #    `patient_data.get('mrn')` might be from parsing (if MRN was in doc, though not currently parsed).
        current_mrn_to_check = new_doc_mrn or patient_data.get('mrn')
        if not existing_patient_id and current_mrn_to_check:
            cursor.execute("SELECT id FROM Patients WHERE mrn = ?", (current_mrn_to_check,))
            result = cursor.fetchone()
            if result:
                existing_patient_id = result[0]
                print(f"Info: Found existing patient ID {existing_patient_id} by MRN {current_mrn_to_check}.")

        if existing_patient_id:
            # Update existing patient record with any new non-empty values?
            # For now, we will NOT update, just use the existing ID. 
            # This prevents overwriting existing good data with potentially partial new data.
            # A more sophisticated merge would compare fields and update intelligently.
            # We also need to decide what MRN to keep if a merge happens. For now, existing MRN is kept.
            return existing_patient_id
        else:
            # Create new patient
            # Use the new_doc_mrn if provided (e.g., from batch O{idx} or override_mrn), 
            # otherwise, generate a TEMP one if patient_data doesn't have one.
            mrn_for_new_patient = current_mrn_to_check
            if not mrn_for_new_patient:
                # This case should be rare if import_batch or import_document always assigns an MRN before calling this.
                mrn_for_new_patient = f"TEMP_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
                print(f"Warning: No MRN provided for new patient {first_name_norm} {last_name_norm}, generating {mrn_for_new_patient}")
            
            print(f"Info: Creating new patient for MRN {mrn_for_new_patient} ({first_name_norm} {last_name_norm}).")
            sql_fields = [
                'mrn', 'first_name', 'last_name', 'date_of_birth', 'naissance_date', 'sex', 'phone',
                'address', 'email', 'insurance', 'primary_physician',
                'pmh', 'psh', 'family_history', 'medications', 'allergies',
                'smoker', 'smoker_details', 'alcohol', 'alcohol_details', 'raw_dossier_text'
            ]
            sql_placeholders = ', '.join(['?' for _ in sql_fields])
            sql_values = [
                mrn_for_new_patient, # Use the determined MRN
                patient_data.get('first_name'), patient_data.get('last_name'), dob_for_db, dob_for_db,  # Store birth date in both fields
                patient_data.get('sex'), patient_data.get('phone'), patient_data.get('address'),
                patient_data.get('email'), patient_data.get('insurance'), patient_data.get('primary_physician'),
                patient_data.get('pmh'), patient_data.get('psh'), patient_data.get('family_history'),
                patient_data.get('medications'), patient_data.get('allergies'),
                bool(patient_data.get('smoker', False)), patient_data.get('smoker_details'),
                bool(patient_data.get('alcohol', False)), patient_data.get('alcohol_details'),
                patient_data.get('raw_dossier_text')
            ]
            try:
                cursor.execute(f'''INSERT INTO Patients ({ ", ".join(sql_fields) }) VALUES ({sql_placeholders})''', sql_values)
                new_patient_id = cursor.lastrowid
                print(f"Info: Successfully created new patient ID {new_patient_id} with MRN {mrn_for_new_patient}.")
                return new_patient_id
            except sqlite3.IntegrityError as ie:
                print(f"Error: Integrity error creating patient MRN {mrn_for_new_patient}: {ie}")
                # This might happen if, despite checks, an MRN collision occurs (e.g., two parallel processes tried to create with same temp MRN)
                # Or if the Name/DOB check somehow missed an existing patient who still has the same MRN (unlikely with current logic)
                # Try to fetch by MRN again just in case it was a race condition on creation but now exists.
                cursor.execute("SELECT id FROM Patients WHERE mrn = ?", (mrn_for_new_patient,))
                existing = cursor.fetchone()
                if existing: 
                    print(f"Info: Patient with MRN {mrn_for_new_patient} was found after an integrity error, likely created in a race. Using ID {existing[0]}.")
                    return existing[0]
                # If the integrity error was on something else (e.g. NOT NULL constraint), this won't help.
                raise # Re-raise if still can't resolve

    def add_visit(self, cursor: sqlite3.Cursor, patient_id: int, visit_data: Dict):
        """Add a new visit record. visit_data['visit_date'] is YYYY-MM-DD or None."""
        parsed_visit_date = visit_data.get('visit_date') # Should be YYYY-MM-DD or None
        notes = visit_data.get('notes', '').strip()

        if not notes and not parsed_visit_date: # Avoid adding truly empty visits
            # print(f"Skipping visit for patient {patient_id} due to no date and no notes.")
            return
        if not notes: # If there is a date but no notes, log it or decide policy
            # print(f"Visit for patient {patient_id} on {parsed_visit_date} has no notes.")
            notes = "[No specific notes recorded for this date]" # Or skip

        # Construct a simple raw_visit_entry string
        raw_visit_entry = f"Date: {parsed_visit_date if parsed_visit_date else '[Undated Entry]'}\nNotes: {notes}"
        
        try:
            cursor.execute('''
                INSERT INTO Visits (patient_id, visit_date, notes, raw_visit_entry)
                VALUES (?, ?, ?, ?)
            ''', (patient_id, parsed_visit_date, notes, raw_visit_entry))
        except Exception as e:
            print(f"Error adding visit for patient {patient_id}, date {parsed_visit_date}: {e}")

    def add_vaccines(self, cursor: sqlite3.Cursor, patient_id: int, vaccines_data: List[Dict]):
        """Add vaccine records to the database."""
        if not vaccines_data:
            return
        
        try:
            for vaccine in vaccines_data:
                # Insert into Immunizations table (unified table)
                cursor.execute('''
                    INSERT INTO Immunizations (patient_id, immunization, administered_date, notes)
                    VALUES (?, ?, ?, ?)
                ''', (
                    patient_id, 
                    vaccine.get('vaccine_name'), 
                    vaccine.get('vaccine_date'),
                    f"Imported from Word document: {vaccine.get('raw_entry', '')}"
                ))
            print(f"Added {len(vaccines_data)} vaccines for patient ID {patient_id}")
        except Exception as e:
            print(f"Error adding vaccines for patient ID {patient_id}: {str(e)}")

    def import_batch(self, doc_paths: List[str], document_format='md') -> List[Tuple[str, bool, str]]:
        results = []
        conn = self.connect_db()
        cursor = conn.cursor()
        word_manager = WordDocumentManager(self.db_path, emr_config.get_word_docs_folder())
        try:
            for idx, doc_path in enumerate(doc_paths, start=1):
                doc_specific_mrn = f"O{idx:03d}"
                success = False
                message = ""
                try:
                    patient_data = self.parse_patient_doc(doc_path)
                    if patient_data:
                        patient_id = self.get_or_create_patient(cursor, patient_data, new_doc_mrn=doc_specific_mrn)
                        if patient_id:
                            for visit_entry in patient_data.get('visits', []):
                                self.add_visit(cursor, patient_id, visit_entry)
                            # Add vaccines if any were parsed
                            self.add_vaccines(cursor, patient_id, patient_data.get('vaccines', []))
                            conn.commit()  # Commit so WordDocumentManager can see the patient
                            
                            # Create/update document (failsafe feature) - skip if format is 'none'
                            if document_format != 'none':
                                try:
                                    doc_path = word_manager.create_or_update_document(patient_id, document_format)
                                    format_name = "Word document" if document_format == 'docx' else "Markdown document"
                                    print(f"Created {format_name} for patient ID {patient_id}: {os.path.basename(doc_path)}")
                                except Exception as e:
                                    print(f"Warning: Failed to create Word document for patient ID {patient_id}: {e}")
                            
                            success = True
                            cursor.execute("SELECT mrn FROM Patients WHERE id = ?", (patient_id,))
                            final_mrn_for_message = cursor.fetchone()[0]
                            message = f"Processed for patient MRN {final_mrn_for_message} (ID: {patient_id}). Original doc MRN was {doc_specific_mrn if final_mrn_for_message != doc_specific_mrn else 'N/A'}."
                        else:
                            message = f"Failed to get/create patient for document {os.path.basename(doc_path)} (tentative MRN {doc_specific_mrn})"
                    else:
                        message = f"Failed to parse document structure for {os.path.basename(doc_path)} (tentative MRN {doc_specific_mrn})"
                except Exception as e_doc:
                    message = f"Error processing document {os.path.basename(doc_path)} for MRN {doc_specific_mrn}: {str(e_doc)}"
                    print(message)
                    import traceback
                    traceback.print_exc()
                results.append((os.path.basename(doc_path), success, message))
            if any(r[1] for r in results):
                conn.commit()
            else:
                conn.rollback()
        except Exception as e_batch:
            conn.rollback()
            print(f"Critical error during batch import: {e_batch}")
            results.append(("BATCH_ERROR", False, str(e_batch)))
        finally:
            conn.close()
        return results

    def import_document(self, doc_path: str, override_mrn: str = None) -> Tuple[bool, str]:
        """Import a single Word document and create a patient record."""
        conn = self.connect_db()
        cursor = conn.cursor()
        try:
            patient_data = self.parse_patient_doc(doc_path)
            if not patient_data:
                return False, "Failed to parse document structure."
            
            # Use override MRN if provided, otherwise generate one based on filename
            if override_mrn:
                mrn_for_lookup_or_creation = override_mrn
            else:
                # Generate MRN from filename (remove extension and use as base)
                base_filename = os.path.splitext(os.path.basename(doc_path))[0]
                mrn_for_lookup_or_creation = f"DOC_{base_filename}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            patient_id = self.get_or_create_patient(cursor, patient_data, new_doc_mrn=mrn_for_lookup_or_creation)
            if not patient_id:
                return False, "Failed to create or find patient record."
            
            # Add visits
            for visit_entry in patient_data.get('visits', []):
                self.add_visit(cursor, patient_id, visit_entry)
            
            # Add vaccines if any were parsed
            self.add_vaccines(cursor, patient_id, patient_data.get('vaccines', []))
            
            conn.commit()

            
            # Create/update Word document (failsafe feature) - skip if format is 'none'
            # Note: This method doesn't take document_format parameter, so we'll always create markdown by default
            # If you need to control this, you'd need to modify the method signature
            try:
                word_manager = WordDocumentManager(self.db_path, emr_config.get_word_docs_folder())
                doc_path = word_manager.create_or_update_document(patient_id)
                print(f"Created Word document for patient ID {patient_id}: {os.path.basename(doc_path)}")
            except Exception as e:
                print(f"Warning: Failed to create Word document for patient ID {patient_id}: {e}")
            
            # Fetch the final MRN for the message, as it might have come from a merged existing record
            cursor.execute("SELECT mrn FROM Patients WHERE id = ?", (patient_id,))
            final_mrn_for_message = cursor.fetchone()[0]
            return True, f"Imported document. Patient MRN {final_mrn_for_message} (ID: {patient_id}). Original MRN for this doc was {mrn_for_lookup_or_creation if final_mrn_for_message != mrn_for_lookup_or_creation else 'N/A'}."
        except Exception as e:
            conn.rollback()
            print(f"Error during single document import ({doc_path}): {str(e)}")
            import traceback
            traceback.print_exc()
            return False, f"Import error: {str(e)}"
        finally:
            conn.close()

# Removed import_directory as import_batch is preferred for UI driven imports.
# If CLI usage of import_directory is needed, it can be reinstated or adapted.

if __name__ == "__main__":
    # Example for testing the importer with a few files
    # Ensure your db_path and test_doc_paths are correct
    db_path = 'word_docs_emr.db' # Or your actual test DB name
    # test_importer = WordDocumentImporter(db_path)

    # Create dummy DB and schema for testing if it doesn't exist
    # conn_main = sqlite3.connect(db_path)
    # from database import init_db_schema # Assuming database.py is in PYTHONPATH
    # with conn_main: # Use app context if get_db relies on Flask g or current_app
    #     # This part is tricky without Flask app context for init_db_schema
    #     # For standalone testing, you might need a simplified init_db_schema or manual table creation here.
    #     print("Standalone: Ensure DB schema exists or is created manually for testing.")
    # conn_main.close()

    # Example: Provide a list of documents to the batch importer
    # test_docs = [
    #     "Patient records/Test Patient 1.docx", 
    #     "Patient records/Test Patient 2.docx",
    #     # Add more paths to your test .docx files
    # ]
    # if not all(os.path.exists(p) for p in test_docs):
    #     print(f"Warning: Not all test documents found. Checked paths: {test_docs}")
    # else:
    #     print(f"Starting batch import for: {test_docs}")
    #     results = test_importer.import_batch(test_docs)
    #     for filename, success, message in results:
    #         print(f"File: {filename} - {'Success' if success else 'FAIL'} - Message: {message}")
    pass # End of __main__ example 