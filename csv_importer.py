#!/usr/bin/env python3

import csv
import sqlite3
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

class CSVImporter:
    """
    CSV Importer for EMR data with support for French accented characters.
    Handles importing patients, visits, and immunizations from CSV files.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self.patient_id_mapping = {}  # Maps old IDs to new IDs
        
    def _clean_utf8_bom(self, text: str) -> str:
        """Remove UTF-8 BOM from text if present"""
        if text.startswith('\ufeff'):
            return text[1:]
        return text
    
    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string and return in YYYY-MM-DD format"""
        if not date_str or date_str.strip() == '':
            return None
            
        date_str = date_str.strip()
        
        # Try different date formats
        date_formats = [
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%Y-%m-%d %H:%M:%S',
            '%d/%m/%Y %H:%M:%S'
        ]
        
        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.strftime('%Y-%m-%d')
            except ValueError:
                continue
                
        self.logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _safe_int(self, value: str) -> Optional[int]:
        """Safely convert string to int"""
        if not value or value.strip() == '':
            return None
        try:
            return int(value.strip())
        except ValueError:
            return None
    
    def _safe_float(self, value: str) -> Optional[float]:
        """Safely convert string to float"""
        if not value or value.strip() == '':
            return None
        try:
            return float(value.strip())
        except ValueError:
            return None
    
    def import_patients_csv(self, csv_file_path: str, update_existing: bool = False) -> Dict[str, int]:
        """
        Import patients from CSV file.
        
        Args:
            csv_file_path: Path to the patients CSV file
            update_existing: If True, update existing patients; if False, skip duplicates
            
        Returns:
            Dictionary with import statistics
        """
        stats = {
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
                # Use utf-8-sig to automatically handle BOM
                reader = csv.DictReader(csvfile)
                
                # Clean BOM from fieldnames if present
                if reader.fieldnames:
                    reader.fieldnames = [self._clean_utf8_bom(field) for field in reader.fieldnames]
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 for header
                    try:
                        # Clean BOM from first field value if present
                        first_key = list(row.keys())[0] if row else None
                        if first_key and row[first_key]:
                            row[first_key] = self._clean_utf8_bom(row[first_key])
                        
                        # Extract patient data
                        old_patient_id = self._safe_int(row.get('id'))  # Store original ID for mapping
                        patient_data = {
                            'mrn': row.get('mrn', '').strip(),
                            'first_name': row.get('first_name', '').strip(),
                            'last_name': row.get('last_name', '').strip(),
                            'date_of_birth': self._parse_date(row.get('date_of_birth')),
                            'sex': row.get('sex', '').strip(),
                            'phone': row.get('phone', '').strip(),
                            'address': row.get('address', '').strip(),
                            'email': row.get('email', '').strip(),
                            'insurance': row.get('insurance', '').strip(),
                            'primary_physician': row.get('primary_physician', '').strip(),
                            'pmh': row.get('pmh', '').strip(),
                            'psh': row.get('psh', '').strip(),
                            'family_history': row.get('family_history', '').strip(),
                            'medications': row.get('medications', '').strip(),
                            'allergies': row.get('allergies', '').strip(),
                            'smoker': row.get('smoker', '').strip(),
                            'smoker_details': row.get('smoker_details', '').strip(),
                            'alcohol': row.get('alcohol', '').strip(),
                            'alcohol_details': row.get('alcohol_details', '').strip(),
                            'raw_dossier_text': row.get('raw_dossier_text', '').strip()
                        }
                        
                        # Validate required fields
                        if not patient_data['first_name'] or not patient_data['last_name']:
                            self.logger.warning(f"Row {row_num}: Missing required fields (first_name, last_name)")
                            stats['errors'] += 1
                            continue
                        
                        # Check if patient exists (by MRN or name+DOB)
                        existing_patient = None
                        existing_patient_id = None
                        
                        if patient_data['mrn']:
                            cursor.execute("SELECT id FROM patients WHERE mrn = ?", (patient_data['mrn'],))
                            result = cursor.fetchone()
                            if result:
                                existing_patient = result
                                existing_patient_id = result[0]
                        
                        if not existing_patient and patient_data['date_of_birth']:
                            cursor.execute("""
                                SELECT id FROM patients 
                                WHERE first_name = ? AND last_name = ? AND date_of_birth = ?
                            """, (patient_data['first_name'], patient_data['last_name'], patient_data['date_of_birth']))
                            result = cursor.fetchone()
                            if result:
                                existing_patient = result
                                existing_patient_id = result[0]
                        
                        if existing_patient:
                            if update_existing:
                                # Update existing patient
                                cursor.execute("""
                                    UPDATE patients SET
                                        mrn = ?, first_name = ?, last_name = ?, date_of_birth = ?,
                                        sex = ?, phone = ?, address = ?, email = ?, insurance = ?,
                                        primary_physician = ?, pmh = ?, psh = ?, family_history = ?,
                                        medications = ?, allergies = ?, smoker = ?, smoker_details = ?,
                                        alcohol = ?, alcohol_details = ?, raw_dossier_text = ?
                                    WHERE id = ?
                                """, (
                                    patient_data['mrn'], patient_data['first_name'], patient_data['last_name'],
                                    patient_data['date_of_birth'], patient_data['sex'], patient_data['phone'],
                                    patient_data['address'], patient_data['email'], patient_data['insurance'],
                                    patient_data['primary_physician'], patient_data['pmh'], patient_data['psh'],
                                    patient_data['family_history'], patient_data['medications'], patient_data['allergies'],
                                    patient_data['smoker'], patient_data['smoker_details'], patient_data['alcohol'],
                                    patient_data['alcohol_details'], patient_data['raw_dossier_text'],
                                    existing_patient_id
                                ))
                                stats['updated'] += 1
                                # Map old ID to existing ID
                                if old_patient_id:
                                    self.patient_id_mapping[old_patient_id] = existing_patient_id
                            else:
                                stats['skipped'] += 1
                                # Still map the ID for relationships
                                if old_patient_id:
                                    self.patient_id_mapping[old_patient_id] = existing_patient_id
                        else:
                            # Insert new patient (let database auto-generate ID)
                            cursor.execute("""
                                INSERT INTO patients (
                                    mrn, first_name, last_name, date_of_birth, sex, phone, address, email,
                                    insurance, primary_physician, pmh, psh, family_history, medications,
                                    allergies, smoker, smoker_details, alcohol, alcohol_details, raw_dossier_text
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                patient_data['mrn'], patient_data['first_name'], patient_data['last_name'],
                                patient_data['date_of_birth'], patient_data['sex'], patient_data['phone'],
                                patient_data['address'], patient_data['email'], patient_data['insurance'],
                                patient_data['primary_physician'], patient_data['pmh'], patient_data['psh'],
                                patient_data['family_history'], patient_data['medications'], patient_data['allergies'],
                                patient_data['smoker'], patient_data['smoker_details'], patient_data['alcohol'],
                                patient_data['alcohol_details'], patient_data['raw_dossier_text']
                            ))
                            
                            # Get the new patient ID
                            new_patient_id = cursor.lastrowid
                            stats['imported'] += 1
                            
                            # Map old ID to new ID
                            if old_patient_id:
                                self.patient_id_mapping[old_patient_id] = new_patient_id
                            
                    except Exception as e:
                        self.logger.error(f"Error processing row {row_num}: {e}")
                        stats['errors'] += 1
                        continue
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error importing patients CSV: {e}")
        finally:
            conn.close()
        
        return stats
    
    def import_visits_csv(self, csv_file_path: str, update_existing: bool = False) -> Dict[str, int]:
        """
        Import visits from CSV file.
        
        Args:
            csv_file_path: Path to the visits CSV file
            update_existing: If True, update existing visits; if False, skip duplicates
            
        Returns:
            Dictionary with import statistics
        """
        stats = {
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Clean BOM from fieldnames if present
                if reader.fieldnames:
                    reader.fieldnames = [self._clean_utf8_bom(field) for field in reader.fieldnames]
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Clean BOM from first field value if present
                        first_key = list(row.keys())[0] if row else None
                        if first_key and row[first_key]:
                            row[first_key] = self._clean_utf8_bom(row[first_key])
                        
                        # Extract visit data
                        old_patient_id = self._safe_int(row.get('patient_id'))
                        
                        # Map old patient ID to new patient ID
                        mapped_patient_id = self.patient_id_mapping.get(old_patient_id, old_patient_id)
                        
                        visit_data = {
                            'patient_id': mapped_patient_id,
                            'visit_date': self._parse_date(row.get('visit_date')),
                            'age_at_visit_months': self._safe_int(row.get('age_at_visit_months')),
                            'weight_kg': self._safe_float(row.get('weight_kg')),
                            'height_cm': self._safe_float(row.get('height_cm')),
                            'head_circumference_cm': self._safe_float(row.get('head_circumference_cm')),
                            'temperature_c': self._safe_float(row.get('temperature_c')),
                            'heart_rate_bpm': self._safe_int(row.get('heart_rate_bpm')),
                            'respiratory_rate_bpm': self._safe_int(row.get('respiratory_rate_bpm')),
                            'blood_pressure_systolic': self._safe_int(row.get('blood_pressure_systolic')),
                            'blood_pressure_diastolic': self._safe_int(row.get('blood_pressure_diastolic')),
                            'oxygen_saturation_percent': self._safe_float(row.get('oxygen_saturation_percent')),
                            'visit_notes': row.get('visit_notes', '').strip(),
                            'diagnosis': row.get('diagnosis', '').strip(),
                            'treatment_plan': row.get('treatment_plan', '').strip(),
                            'follow_up_instructions': row.get('follow_up_instructions', '').strip()
                        }
                        
                        # Validate required fields
                        if not visit_data['patient_id'] or not visit_data['visit_date']:
                            self.logger.warning(f"Row {row_num}: Missing required fields (patient_id, visit_date)")
                            stats['errors'] += 1
                            continue
                        
                        # Check if patient exists
                        cursor.execute("SELECT id FROM patients WHERE id = ?", (visit_data['patient_id'],))
                        if not cursor.fetchone():
                            self.logger.warning(f"Row {row_num}: Patient ID {visit_data['patient_id']} not found")
                            stats['errors'] += 1
                            continue
                        
                        # Check if visit exists
                        existing_visit = None
                        cursor.execute("""
                            SELECT id FROM Visits 
                            WHERE patient_id = ? AND visit_date = ?
                        """, (visit_data['patient_id'], visit_data['visit_date']))
                        existing_visit = cursor.fetchone()
                        
                        if existing_visit:
                            if update_existing:
                                # Update existing visit
                                cursor.execute("""
                                    UPDATE Visits SET
                                        patient_id = ?, visit_date = ?, age_at_visit_months = ?,
                                        weight_kg = ?, height_cm = ?, head_circumference_cm = ?,
                                        temperature_c = ?, heart_rate_bpm = ?, respiratory_rate_bpm = ?,
                                        blood_pressure_systolic = ?, blood_pressure_diastolic = ?,
                                        oxygen_saturation_percent = ?, visit_notes = ?, diagnosis = ?,
                                        treatment_plan = ?, follow_up_instructions = ?
                                    WHERE id = ?
                                """, (
                                    visit_data['patient_id'], visit_data['visit_date'], visit_data['age_at_visit_months'],
                                    visit_data['weight_kg'], visit_data['height_cm'], visit_data['head_circumference_cm'],
                                    visit_data['temperature_c'], visit_data['heart_rate_bpm'], visit_data['respiratory_rate_bpm'],
                                    visit_data['blood_pressure_systolic'], visit_data['blood_pressure_diastolic'],
                                    visit_data['oxygen_saturation_percent'], visit_data['visit_notes'], visit_data['diagnosis'],
                                    visit_data['treatment_plan'], visit_data['follow_up_instructions'],
                                    existing_visit[0]
                                ))
                                stats['updated'] += 1
                            else:
                                stats['skipped'] += 1
                        else:
                            # Insert new visit
                            cursor.execute("""
                                INSERT INTO Visits (
                                    patient_id, visit_date, age_at_visit_months, weight_kg, height_cm,
                                    head_circumference_cm, temperature_c, heart_rate_bpm, respiratory_rate_bpm,
                                    blood_pressure_systolic, blood_pressure_diastolic, oxygen_saturation_percent,
                                    visit_notes, diagnosis, treatment_plan, follow_up_instructions
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                visit_data['patient_id'], visit_data['visit_date'], visit_data['age_at_visit_months'],
                                visit_data['weight_kg'], visit_data['height_cm'], visit_data['head_circumference_cm'],
                                visit_data['temperature_c'], visit_data['heart_rate_bpm'], visit_data['respiratory_rate_bpm'],
                                visit_data['blood_pressure_systolic'], visit_data['blood_pressure_diastolic'],
                                visit_data['oxygen_saturation_percent'], visit_data['visit_notes'], visit_data['diagnosis'],
                                visit_data['treatment_plan'], visit_data['follow_up_instructions']
                            ))
                            stats['imported'] += 1
                            
                    except Exception as e:
                        self.logger.error(f"Error processing row {row_num}: {e}")
                        stats['errors'] += 1
                        continue
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error importing visits CSV: {e}")
        finally:
            conn.close()
        
        return stats
    
    def import_immunizations_csv(self, csv_file_path: str, update_existing: bool = False) -> Dict[str, int]:
        """
        Import immunizations from CSV file.
        
        Args:
            csv_file_path: Path to the immunizations CSV file
            update_existing: If True, update existing immunizations; if False, skip duplicates
            
        Returns:
            Dictionary with import statistics
        """
        stats = {
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        if not os.path.exists(csv_file_path):
            raise FileNotFoundError(f"CSV file not found: {csv_file_path}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Clean BOM from fieldnames if present
                if reader.fieldnames:
                    reader.fieldnames = [self._clean_utf8_bom(field) for field in reader.fieldnames]
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Clean BOM from first field value if present
                        first_key = list(row.keys())[0] if row else None
                        if first_key and row[first_key]:
                            row[first_key] = self._clean_utf8_bom(row[first_key])
                        
                        # Extract immunization data
                        old_patient_id = self._safe_int(row.get('patient_id'))
                        
                        # Map old patient ID to new patient ID
                        mapped_patient_id = self.patient_id_mapping.get(old_patient_id, old_patient_id)
                        
                        immunization_data = {
                            'patient_id': mapped_patient_id,
                            'immunization': row.get('immunization', '').strip(),
                            'administered_date': self._parse_date(row.get('administered_date')),
                            'brand_name': row.get('brand_name', '').strip(),
                            'dose_number': self._safe_int(row.get('dose_number')),
                            'notes': row.get('notes', '').strip()
                        }
                        
                        # Validate required fields
                        if not immunization_data['patient_id'] or not immunization_data['immunization']:
                            self.logger.warning(f"Row {row_num}: Missing required fields (patient_id, immunization)")
                            stats['errors'] += 1
                            continue
                        
                        # Check if patient exists
                        cursor.execute("SELECT id FROM patients WHERE id = ?", (immunization_data['patient_id'],))
                        if not cursor.fetchone():
                            self.logger.warning(f"Row {row_num}: Patient ID {immunization_data['patient_id']} not found")
                            stats['errors'] += 1
                            continue
                        
                        # Check if immunization exists
                        existing_immunization = None
                        cursor.execute("""
                            SELECT id FROM Immunizations 
                            WHERE patient_id = ? AND immunization = ? AND administered_date = ?
                        """, (immunization_data['patient_id'], immunization_data['immunization'], immunization_data['administered_date']))
                        existing_immunization = cursor.fetchone()
                        
                        if existing_immunization:
                            if update_existing:
                                # Update existing immunization
                                cursor.execute("""
                                    UPDATE Immunizations SET
                                        patient_id = ?, immunization = ?, administered_date = ?,
                                        brand_name = ?, dose_number = ?, notes = ?
                                    WHERE id = ?
                                """, (
                                    immunization_data['patient_id'], immunization_data['immunization'],
                                    immunization_data['administered_date'], immunization_data['brand_name'],
                                    immunization_data['dose_number'], immunization_data['notes'],
                                    existing_immunization[0]
                                ))
                                stats['updated'] += 1
                            else:
                                stats['skipped'] += 1
                        else:
                            # Insert new immunization
                            cursor.execute("""
                                INSERT INTO Immunizations (
                                    patient_id, immunization, administered_date, brand_name, dose_number, notes
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                immunization_data['patient_id'], immunization_data['immunization'],
                                immunization_data['administered_date'], immunization_data['brand_name'],
                                immunization_data['dose_number'], immunization_data['notes']
                            ))
                            stats['imported'] += 1
                            
                    except Exception as e:
                        self.logger.error(f"Error processing row {row_num}: {e}")
                        stats['errors'] += 1
                        continue
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Error importing immunizations CSV: {e}")
        finally:
            conn.close()
        
        return stats
    
    def import_csv_bundle(self, csv_directory: str, update_existing: bool = False) -> Dict[str, Dict[str, int]]:
        """
        Import a complete CSV bundle (patients, visits, immunizations).
        
        Args:
            csv_directory: Directory containing the CSV files
            update_existing: If True, update existing records; if False, skip duplicates
            
        Returns:
            Dictionary with import statistics for each file type
        """
        results = {}
        
        # Clear patient ID mapping for fresh import
        self.patient_id_mapping = {}
        
        # Import in order: patients first, then visits, then immunizations
        csv_files = [
            ('patients', 'patients.csv'),
            ('visits', 'visits.csv'),
            ('immunizations', 'immunizations.csv')
        ]
        
        for file_type, filename in csv_files:
            csv_path = os.path.join(csv_directory, filename)
            
            if os.path.exists(csv_path):
                try:
                    if file_type == 'patients':
                        results[file_type] = self.import_patients_csv(csv_path, update_existing)
                    elif file_type == 'visits':
                        results[file_type] = self.import_visits_csv(csv_path, update_existing)
                    elif file_type == 'immunizations':
                        results[file_type] = self.import_immunizations_csv(csv_path, update_existing)
                        
                    self.logger.info(f"Imported {file_type}: {results[file_type]}")
                    
                except Exception as e:
                    self.logger.error(f"Error importing {file_type}: {e}")
                    results[file_type] = {'error': str(e)}
            else:
                self.logger.warning(f"CSV file not found: {csv_path}")
                results[file_type] = {'error': f'File not found: {filename}'}
        
        return results


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python csv_importer.py <database_path> <csv_file_or_directory>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    csv_path = sys.argv[2]
    
    importer = CSVImporter(db_path)
    
    if os.path.isdir(csv_path):
        # Import bundle
        results = importer.import_csv_bundle(csv_path, update_existing=True)
        print("Import Results:")
        for file_type, stats in results.items():
            print(f"  {file_type}: {stats}")
    else:
        # Import single file
        if 'patients' in csv_path:
            results = importer.import_patients_csv(csv_path, update_existing=True)
        elif 'visits' in csv_path:
            results = importer.import_visits_csv(csv_path, update_existing=True)
        elif 'immunizations' in csv_path:
            results = importer.import_immunizations_csv(csv_path, update_existing=True)
        else:
            print("Could not determine CSV file type from filename")
            sys.exit(1)
        
        print(f"Import Results: {results}")