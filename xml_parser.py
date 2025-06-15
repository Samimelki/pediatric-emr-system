import xml.etree.ElementTree as ET
import re
from datetime import datetime

# Namespace for SpreadsheetML
NS = {
    '': "urn:schemas-microsoft-com:office:spreadsheet",  # Default namespace
    'ss': "urn:schemas-microsoft-com:office:spreadsheet"
}

def parse_date_to_iso(date_str, input_format='%d-%m-%y'):
    """Converts date string to YYYY-MM-DD.
       Handles dd-mm-yy (assuming yy >= 70 is 19yy, else 20yy)
       and dd/mm/yyyy.
    """
    if not date_str:
        return None
    try:
        if input_format == '%d-%m-%y':
            day, month, year_short = map(int, date_str.split('-'))
            year = 1900 + year_short if year_short >= 70 else 2000 + year_short
            return datetime(year, month, day).strftime('%Y-%m-%d')
        elif input_format == '%d/%m/%Y':
            dt_obj = datetime.strptime(date_str, '%d/%m/%Y')
            return dt_obj.strftime('%Y-%m-%d')
    except ValueError:
        # print(f"Warning: Could not parse date '{date_str}' with format '{input_format}'")
        return None # Or return original string, or log error
    return None

def preclean_measurement_string(measurement_str):
    """
    Pre-clean measurement strings to fix common formatting issues before parsing.
    
    Rules:
    1. Weight should be 2-5 digits (20-14000g range) - extended for older babies
    2. Height should be 2-3 digits (20-200cm range) 
    3. Head circumference should be 2-3 digits (20-100cm range)
    4. Handle decimals properly
    5. Handle missing slashes between height and HC
    """
    
    if not measurement_str or '/' not in measurement_str:
        return measurement_str
    
    # Split by slashes
    parts = measurement_str.split('/')
    
    if len(parts) < 2:
        return measurement_str
    
    # Clean each part
    cleaned_parts = []
    
    for i, part in enumerate(parts):
        if part.strip():
            cleaned_parts.append(part.strip())
    
    if len(cleaned_parts) < 2:
        return measurement_str
    
    # Pattern 0: Check for missing slash between height and HC (like "10.1/6946" -> "10.1/69/46")
    if len(cleaned_parts) == 2:  # Only weight/heightHC format
        try:
            weight_val = float(cleaned_parts[0])
            height_hc_str = cleaned_parts[1]
            
            # If second part is 3-4 digits, might be concatenated height+HC
            if len(height_hc_str) >= 3 and height_hc_str.replace('.', '').isdigit():
                # Try different split positions for height/HC
                for height_digits in [2, 3]:  # Try 2 digits for height first, then 3
                    if height_digits < len(height_hc_str):
                        potential_height = height_hc_str[:height_digits]
                        potential_hc = height_hc_str[height_digits:]
                        
                        try:
                            height_val = float(potential_height)
                            hc_val = float(potential_hc)
                            
                            # Check if this makes sense
                            if (20 <= height_val <= 200 and    # Reasonable height range
                                20 <= hc_val <= 100):          # Reasonable HC range
                                
                                result = f"{cleaned_parts[0]}/{potential_height}/{potential_hc}"
                                return result
                                
                        except ValueError:
                            continue
        except ValueError:
            pass
    
    # Focus on the first part (weight) - this is where most concatenation happens
    first_part = cleaned_parts[0]
    
    # Pattern 1: First part is too long and contains concatenated weight+height
    # BUT: Skip if we already have valid measurements in the original format
    if len(first_part) >= 5:
        
        # Check if the original format is already valid before trying to split
        if len(cleaned_parts) >= 2:
            try:
                original_weight = float(cleaned_parts[0])
                original_height = float(cleaned_parts[1])
                
                # If original measurements are already reasonable, don't split
                if (1000 <= original_weight <= 14000 and 20 <= original_height <= 200):
                    # Skip Pattern 1 - original format is already good
                    pass
                else:
                    # Original format has issues, proceed with Pattern 1 splitting
                    # Handle decimal numbers
                    if '.' in first_part:
                        integer_part, decimal_part = first_part.split('.', 1)
                        
                        # If integer part is 5+ digits, likely concatenated
                        if len(integer_part) >= 5:
                            # Try different split positions for weight
                            for weight_digits in [4, 5, 3]:  # Try 4 digits first, then 5, then 3
                                if weight_digits < len(integer_part):
                                    potential_weight = integer_part[:weight_digits]
                                    potential_height = integer_part[weight_digits:] + '.' + decimal_part
                                    
                                    try:
                                        weight_val = int(potential_weight)
                                        height_val = float(potential_height)
                                        
                                        # Check if this makes sense - EXTENDED WEIGHT RANGE
                                        if (20 <= weight_val <= 14000 and  # Extended weight range for older babies
                                            20 <= height_val <= 200):       # Reasonable height range
                                            
                                            # Reconstruct the measurement string
                                            new_parts = [potential_weight, potential_height]
                                            if len(cleaned_parts) > 1:
                                                new_parts.extend(cleaned_parts[1:])
                                            
                                            result = '/'.join(new_parts)
                                            return result
                                            
                                    except ValueError:
                                        continue
                    
                    # Handle non-decimal numbers
                    else:
                        if first_part.isdigit() and len(first_part) >= 5:
                            # Try different split positions
                            for weight_digits in [4, 5, 3]:  # Try 4 digits first, then 5, then 3
                                if weight_digits < len(first_part):
                                    potential_weight = first_part[:weight_digits]
                                    potential_height = first_part[weight_digits:]
                                    
                                    try:
                                        weight_val = int(potential_weight)
                                        height_val = int(potential_height)
                                        
                                        # Check if this makes sense - EXTENDED WEIGHT RANGE
                                        if (20 <= weight_val <= 14000 and  # Extended weight range for older babies
                                            20 <= height_val <= 200):       # Reasonable height range
                                            
                                            # Reconstruct the measurement string
                                            new_parts = [potential_weight, potential_height]
                                            if len(cleaned_parts) > 1:
                                                new_parts.extend(cleaned_parts[1:])
                                            
                                            result = '/'.join(new_parts)
                                            return result
                                            
                                    except ValueError:
                                        continue
            except ValueError:
                # If we can't parse the original values, proceed with Pattern 1 anyway
                pass
    
    # Pattern 2: Check if weight is too small and height is too large (like "34/5678/44")
    # BUT: Skip this pattern if we already have a valid weight/height combination
    if len(cleaned_parts) >= 2:
        try:
            first_val = float(cleaned_parts[0])
            second_val = float(cleaned_parts[1])
            
            # Skip Pattern 2 if we already have reasonable values
            if (1000 <= first_val <= 14000 and 20 <= second_val <= 200):
                # This is already a valid weight/height combination, don't modify
                pass
            elif first_val < 100 and second_val > 1000:
                # Only process cases where weight is too small AND height is too large
                # Merge first two parts
                merged = cleaned_parts[0] + str(int(second_val))
                
                # Try to split the merged number
                if len(merged) >= 4:
                    for weight_digits in [4, 3, 5]:
                        if weight_digits < len(merged):
                            potential_weight = merged[:weight_digits]
                            potential_height = merged[weight_digits:]
                            
                            try:
                                weight_val = int(potential_weight)
                                height_val = int(potential_height)
                                
                                # EXTENDED WEIGHT RANGE
                                if (100 <= weight_val <= 14000 and  # Extended weight range
                                    20 <= height_val <= 200):        # Reasonable height range
                                    
                                    new_parts = [potential_weight, potential_height]
                                    if len(cleaned_parts) > 2:
                                        new_parts.extend(cleaned_parts[2:])
                                    
                                    result = '/'.join(new_parts)
                                    return result
                                    
                            except ValueError:
                                continue
        except ValueError:
            pass
    
    # Pattern 3: Check for missing decimal in height (like "5300/595/39" -> "5300/59.5/39")
    if len(cleaned_parts) >= 2:
        try:
            height_val = float(cleaned_parts[1])
            if height_val > 200 and len(cleaned_parts[1]) == 3:  # Like "595"
                # Try adding decimal point
                height_str = cleaned_parts[1]
                potential_height = height_str[:2] + '.' + height_str[2:]
                potential_height_val = float(potential_height)
                
                if 20 <= potential_height_val <= 200:
                    new_parts = [cleaned_parts[0], potential_height]
                    if len(cleaned_parts) > 2:
                        new_parts.extend(cleaned_parts[2:])
                    
                    result = '/'.join(new_parts)
                    return result
        except ValueError:
            pass
    
    # No cleaning needed
    return measurement_str

def _parse_measurement_string(measurement_str):
    """Parse measurement string like '3880/51/37' into weight_g, height_cm, hc_cm.
    Now includes pre-cleaning to fix common formatting issues.
    """
    if not measurement_str:
        return None, None, None
    
    # PRE-CLEAN the measurement string first
    cleaned_measurement_str = preclean_measurement_string(measurement_str)
    
    # Split by '/' to get parts
    parts = cleaned_measurement_str.split('/')
    
    weight_g = None
    height_cm = None
    hc_cm = None
    
    try:
        if len(parts) >= 1 and parts[0].strip():
            weight_value = float(parts[0].strip())
            # Improved weight conversion logic
            if weight_value < 50:  # Values < 50 are likely in kg (like 10.1 kg)
                weight_g = int(weight_value * 1000)
            else:
                weight_g = int(weight_value)  # Already in grams (like 11450g)
        if len(parts) >= 2 and parts[1].strip():
            height_cm = float(parts[1].strip())
        if len(parts) >= 3 and parts[2].strip():
            hc_cm = float(parts[2].strip())
    except (ValueError, IndexError):
        pass

    return weight_g, height_cm, hc_cm

def parse_memo_text(memo_text):
    """Parse memo text to extract birth measurements and visits."""
    if not memo_text:
        return {'birth_measurements': {}, 'parsed_visits': []}
    
    lines = [line.strip() for line in memo_text.strip().split('\n') if line.strip()]
    if not lines:
        return {'birth_measurements': {}, 'parsed_visits': []}
    
    birth_measurements_data = {}
    parsed_visits = []
    processed_birth_measurement_lines = 0
    
    # Enhanced regex to capture measurements at start of line with optional text after
    standalone_measurement_pattern = re.compile(r"^(\d+(?:\.\d+)?(?:/\d*(?:\.\d+)?(?:/\d*(?:\.\d+)?)?)?)(.*)$")
    
    # Check first line for birth measurements
    if lines and not lines[0].startswith('*'):
        first_line_match = standalone_measurement_pattern.match(lines[0].strip())
        if first_line_match:
            bm_w, bm_h, bm_hc = _parse_measurement_string(first_line_match.group(1))
            if bm_w is not None: 
                birth_measurements_data['weight_g'] = bm_w
                birth_measurements_data['height_cm'] = bm_h
                birth_measurements_data['hc_cm'] = bm_hc
                birth_notes = first_line_match.group(2)
                if birth_notes:
                    birth_measurements_data['notes'] = birth_notes.strip()
                processed_birth_measurement_lines = 1

    # Process remaining lines for visits
    visit_pattern = re.compile(
        r"^\*(?P<date>\d{2}-\d{2}-\d{2})\*\s*"
        r"(?:(?P<measurements_raw>\d+(?:\.\d+)?(?:/\d*(?:\.\d+)?(?:/\d*(?:\.\d+)?)?)?)\s*)?"
        r"(?P<note>.*)$"
    )
    
    # Start processing for visits from the line after any processed birth measurement lines
    for entry_text in lines[processed_birth_measurement_lines:]:
        entry_text = entry_text.strip()
        if not entry_text:
            continue
        
        match = visit_pattern.match(entry_text)
        if match:
            data = match.groupdict()
            visit_date_iso = parse_date_to_iso(data['date'], input_format='%d-%m-%y')
            weight_g, height_cm, hc_cm = _parse_measurement_string(data.get('measurements_raw'))
            
            parsed_visits.append({
                'visit_date': visit_date_iso,
                'weight_g': weight_g, 'height_cm': height_cm,
                'head_circumference_cm': hc_cm,
                'notes': data['note'].strip() if data['note'] else "",
                'raw_visit_entry': entry_text
            })
        elif entry_text.startswith("*") and entry_text.count("*") >= 2 and parsed_visits:
            # This handles notes that continue on a new line and also start with *
            parsed_visits[-1]['notes'] += "\n" + entry_text
        elif parsed_visits: # If it's not a visit and not a continuation starting with *, append to previous note
             parsed_visits[-1]['notes'] += "\n" + entry_text

    return {'birth_measurements': birth_measurements_data, 'parsed_visits': parsed_visits}

def parse_autres_vac_text(autres_vac_content_raw):
    """
    Parses the raw text from /fichier/autres_vac into a list of non-standard vaccines.
    Expected format per line: Vaccine Name: dd/mm/yyyy
    """
    if not autres_vac_content_raw:
        return []
    normalized_content = autres_vac_content_raw.replace("&#10;", "\n")
    potential_entries = re.split(r'\r\n|\n|\r', normalized_content)
    parsed_vaccines = []
    # Regex to capture vaccine name and date (dd/mm/yyyy)
    # Allows for spaces around the colon
    vaccine_pattern = re.compile(r"^(?P<name>.+?)\s*:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})$")

    for entry_text in potential_entries:
        entry_text = entry_text.strip()
        if not entry_text:
            continue
        match = vaccine_pattern.match(entry_text)
        if match:
            data = match.groupdict()
            vaccine_date_iso = parse_date_to_iso(data['date'], input_format='%d/%m/%Y')
            if vaccine_date_iso: # Only add if date is valid
                parsed_vaccines.append({
                    'vaccine_name': data['name'].strip(),
                    'vaccine_date': vaccine_date_iso,
                    'raw_entry': entry_text
                })
        # else: line doesn't match format, ignore for now or log
    return parsed_vaccines

def _extract_headers_from_row(header_row, ns):
    """Extract headers from the header row."""
    headers = {}
    logical_col_idx = 1
    cells = header_row.findall('{%s}Cell' % ns[''], ns)
    
    for cell in cells:
        ss_index = cell.get('{%s}Index' % ns['ss'])
        if ss_index:
            logical_col_idx = int(ss_index)
        
        data_element = cell.find('{%s}Data' % ns[''], ns)
        if data_element is not None and data_element.text:
            headers[logical_col_idx] = data_element.text.strip()
        
        logical_col_idx += 1
    
    return headers

def _process_row(row_element, headers, ns):
    """Processes a single data row and returns patient data."""
    patient_data = {}
    logical_col_idx = 1
    row_cells = row_element.findall('{%s}Cell' % ns[''], ns)

    memo_header_key = '/fichier/dossier'
    autres_vac_header_key = '/fichier/autres_vac'

    for cell_node in row_cells:
        cell_ss_index_str = cell_node.get('{%s}Index' % ns['ss'])
        if cell_ss_index_str:
            logical_col_idx = int(cell_ss_index_str)
        
        if logical_col_idx > 37: # Only process relevant columns
            logical_col_idx +=1 
            continue 

        header_name = headers.get(logical_col_idx)
        data_value = ""
        data_element = cell_node.find('{%s}Data' % ns[''], ns)
        if data_element is not None:
            data_value = data_element.text if data_element.text is not None else ""
        
        if header_name:
            patient_data[header_name] = data_value.strip()
            if header_name == memo_header_key:
                patient_data['parsed_dossier_content'] = parse_memo_text(data_value)
            elif header_name == autres_vac_header_key:
                patient_data['parsed_autres_vaccins'] = parse_autres_vac_text(data_value)
        
        logical_col_idx += 1
    return patient_data

def parse_excel_xml(file_path):
    """Parses data from an Excel XML file."""
    all_patients_data = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ET.parse(f)
        root = tree.getroot()
        table = root.find('.//{%s}Worksheet[@ss:Name="databasepap"]/{%s}Table' % (NS[''], NS['']), NS)
        if table is None:
            table = root.find('.//{%s}Table' % NS[''], NS)
            if table is None:
                print("Error: Could not find any Table in the XML.")
                return []

        rows = table.findall('{%s}Row' % NS[''], NS)
        if len(rows) < 2:
            print("Error: Not enough rows for headers and data.")
            return []

        headers = _extract_headers_from_row(rows[1], NS)
        
        for row_element in rows[2:]:
            patient_data = _process_row(row_element, headers, NS)
            if patient_data: # Ensure patient_data is not empty
                all_patients_data.append(patient_data)
                
    except ET.ParseError as e:
        print(f"XML Parsing Error: {e}")
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    return all_patients_data 