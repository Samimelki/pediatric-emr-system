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
        self.detailed_errors = []  # Store detailed error messages for reporting
        self._ensure_database_schema()
        
    def _ensure_database_schema(self):
        """Ensure the database has the proper schema initialized."""
        try:
            # Check if database exists and has tables
            if not os.path.exists(self.db_path):
                # Database doesn't exist, create it with schema
                self._create_database_schema()
                self.logger.info(f"Created new database with schema: {self.db_path}")
            else:
                # Database exists, check if it has the required tables
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Check for patients table
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='patients'")
                if not cursor.fetchone():
                    # Tables don't exist, initialize schema
                    conn.close()
                    self._create_database_schema()
                    self.logger.info(f"Initialized schema for existing database: {self.db_path}")
                else:
                    conn.close()
                    
        except Exception as e:
            self.logger.error(f"Error ensuring database schema: {e}")
            raise Exception(f"Failed to initialize database schema: {e}")
    
    def _create_database_schema(self):
        """Create database schema if it doesn't exist - matches unified_database.py schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Use the same schema as unified_database.py
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS Patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mrn TEXT UNIQUE,
                mrn_agg INTEGER,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                prenom TEXT,
                nom TEXT,
                date_of_birth TEXT,
                naissance_date TEXT,
                birth_weight_g INTEGER,
                birth_height_cm REAL,
                birth_head_circumference_cm REAL,
                birth_notes TEXT,
                sex TEXT,
                sexe TEXT,
                phone TEXT,
                telephone TEXT,
                address TEXT,
                domicile TEXT,
                email TEXT,
                insurance TEXT,
                primary_physician TEXT,
                pmh TEXT,
                psh TEXT,
                family_history TEXT,
                medications TEXT,
                allergies TEXT,
                smoker BOOLEAN,
                smoker_details TEXT,
                alcohol BOOLEAN,
                alcohol_details TEXT,
                mere_nom TEXT,
                pere_nom TEXT,
                pediatre_initiales TEXT,
                third_party_payer TEXT,
                hopital TEXT,
                diag1 TEXT,
                diag2 TEXT,
                obstetrical_history TEXT,
                monotest1 TEXT,
                monotest2 TEXT,
                monotest3 TEXT,
                rougeole_seule_date TEXT,
                dtcp1_date TEXT,
                dtcp2_date TEXT,
                dtcp3_date TEXT,
                dtcp_rappel1_date TEXT,
                dtcp_rappel2_date TEXT,
                dtcp_rappel3_date TEXT,
                dtcp_rappel4_date TEXT,
                hep_b1_date TEXT,
                hep_b2_date TEXT,
                hep_b3_date TEXT,
                hib1_date TEXT,
                hib2_date TEXT,
                hib3_date TEXT,
                hib_rappel_date TEXT,
                ror_date TEXT,
                raw_dossier_text TEXT,
                raw_autres_vaccins_text TEXT,
                notes TEXT,
                created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                modified_date TEXT DEFAULT CURRENT_TIMESTAMP,
                emr_mode TEXT DEFAULT 'mixed',
                patient_history_text TEXT
            );
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS Visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                visit_date TEXT NOT NULL,
                
                -- Adult Visit Fields
                vital_signs TEXT,           -- JSON string containing BP, HR, Temp, etc.
                chief_complaint TEXT,
                subjective TEXT,
                objective TEXT,
                assessment TEXT,
                plan TEXT,
                
                -- Pediatric Visit Fields  
                weight_g INTEGER,           -- Weight in grams (pediatric)
                weight_kg REAL,             -- Weight in kg (adult)
                height_cm REAL,
                head_circumference_cm REAL,
                
                -- Shared Fields
                notes TEXT,
                raw_visit_entry TEXT,
                
                -- Metadata
                visit_type TEXT,            -- 'adult', 'pediatric', 'mixed'
                created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (patient_id) REFERENCES Patients (id)
            );
            """)
            
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS Immunizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                immunization TEXT NOT NULL,    -- Canonical disease name (e.g., "DTaP - IPV", "Hepatitis A")
                administered_date TEXT NOT NULL,
                brand_name TEXT,               -- Original brand name (e.g., "HAVRIX", "SYNFLORIX")
                dose_number INTEGER,           -- Auto-calculated sequence number for this immunization
                notes TEXT,                    -- Additional notes including import source
                source TEXT DEFAULT 'import',  -- Track data source ('import', 'manual', etc.)
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES Patients (id)
            );
            """)
            
            conn.commit()
            self.logger.info("Database schema created successfully")
            
        except Exception as e:
            conn.rollback()
            raise Exception(f"Failed to create database schema: {e}")
        finally:
            conn.close()
    
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
                        
                        # Handle MRN - generate if not provided
                        mrn_value = row.get('mrn', '').strip()
                        if not mrn_value:
                            # Auto-generate MRN using timestamp and row number for uniqueness
                            import time
                            mrn_value = f"CSV{int(time.time())}{row_num:04d}"
                        
                        patient_data = {
                            'mrn': mrn_value,
                            'first_name': row.get('prenom', row.get('first_name', '')).strip(),
                            'last_name': row.get('nom', row.get('last_name', '')).strip(),
                            'date_of_birth': self._parse_date(row.get('naissance_date', row.get('date_of_birth'))),
                            'naissance_date': self._parse_date(row.get('naissance_date', row.get('date_of_birth'))),
                            'sex': row.get('sexe', row.get('sex', '')).strip(),
                            'sexe': row.get('sexe', row.get('sex', '')).strip(),
                            'phone': row.get('telephone', row.get('phone', '')).strip(),
                            'telephone': row.get('telephone', row.get('phone', '')).strip(),
                            'address': row.get('domicile', row.get('address', '')).strip(),
                            'domicile': row.get('domicile', row.get('address', '')).strip(),
                            'email': row.get('email', '').strip(),
                            'insurance': row.get('insurance', '').strip(),
                            'primary_physician': row.get('pediatre_initiales', row.get('primary_physician', '')).strip(),
                            'pediatre_initiales': row.get('pediatre_initiales', row.get('primary_physician', '')).strip(),
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
                        
                        # Validate required fields - allow patients with at least one name
                        if not patient_data['first_name'] and not patient_data['last_name']:
                            error_msg = f"Patients row {row_num}: Missing required fields (both first_name and last_name are empty)"
                            self.logger.warning(error_msg)
                            self.detailed_errors.append(error_msg)
                            stats['errors'] += 1
                            continue
                        
                        # Check if patient exists (by MRN or name+DOB)
                        existing_patient = None
                        existing_patient_id = None
                        
                        if patient_data['mrn']:
                            cursor.execute("SELECT id FROM Patients WHERE mrn = ?", (patient_data['mrn'],))
                            result = cursor.fetchone()
                            if result:
                                existing_patient = result
                                existing_patient_id = result[0]
                        
                        if not existing_patient and patient_data['date_of_birth']:
                            cursor.execute("""
                                SELECT id FROM Patients 
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
                                    UPDATE Patients SET
                                        mrn = ?, first_name = ?, last_name = ?, date_of_birth = ?, naissance_date = ?,
                                        sex = ?, sexe = ?, phone = ?, telephone = ?, address = ?, domicile = ?, 
                                        email = ?, insurance = ?, primary_physician = ?, pediatre_initiales = ?,
                                        pmh = ?, psh = ?, family_history = ?, medications = ?, allergies = ?, 
                                        smoker = ?, smoker_details = ?, alcohol = ?, alcohol_details = ?, raw_dossier_text = ?
                                    WHERE id = ?
                                """, (
                                    patient_data['mrn'], patient_data['first_name'], patient_data['last_name'],
                                    patient_data['date_of_birth'], patient_data['naissance_date'], 
                                    patient_data['sex'], patient_data['sexe'], patient_data['phone'], patient_data['telephone'],
                                    patient_data['address'], patient_data['domicile'], patient_data['email'], patient_data['insurance'],
                                    patient_data['primary_physician'], patient_data['pediatre_initiales'], patient_data['pmh'], patient_data['psh'],
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
                                INSERT INTO Patients (
                                    mrn, first_name, last_name, date_of_birth, naissance_date, sex, sexe, 
                                    phone, telephone, address, domicile, email, insurance, primary_physician, pediatre_initiales,
                                    pmh, psh, family_history, medications, allergies, smoker, smoker_details, 
                                    alcohol, alcohol_details, raw_dossier_text
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                patient_data['mrn'], patient_data['first_name'], patient_data['last_name'],
                                patient_data['date_of_birth'], patient_data['naissance_date'], patient_data['sex'], patient_data['sexe'],
                                patient_data['phone'], patient_data['telephone'], patient_data['address'], patient_data['domicile'],
                                patient_data['email'], patient_data['insurance'], patient_data['primary_physician'], patient_data['pediatre_initiales'],
                                patient_data['pmh'], patient_data['psh'], patient_data['family_history'], patient_data['medications'], 
                                patient_data['allergies'], patient_data['smoker'], patient_data['smoker_details'], 
                                patient_data['alcohol'], patient_data['alcohol_details'], patient_data['raw_dossier_text']
                            ))
                            
                            # Get the new patient ID
                            new_patient_id = cursor.lastrowid
                            stats['imported'] += 1
                            
                            # Map old ID to new ID
                            if old_patient_id:
                                self.patient_id_mapping[old_patient_id] = new_patient_id
                            
                    except Exception as e:
                        error_msg = f"Patients row {row_num}: {str(e)} - Data: {dict(row)}"
                        self.logger.error(error_msg)
                        self.detailed_errors.append(error_msg)
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
                        
                        # Extract weight - handle both grams and kg
                        weight_g_raw = self._safe_float(row.get('weight_g'))
                        weight_kg_raw = self._safe_float(row.get('weight_kg'))
                        
                        # Determine final weight values
                        weight_g_final = None
                        weight_kg_final = None
                        
                        if weight_g_raw:
                            weight_g_final = weight_g_raw
                            weight_kg_final = weight_g_raw / 1000  # Convert to kg for weight_kg field
                        elif weight_kg_raw:
                            weight_kg_final = weight_kg_raw
                            weight_g_final = weight_kg_raw * 1000  # Convert to grams for weight_g field
                        
                        visit_data = {
                            'patient_id': mapped_patient_id,
                            'visit_date': self._parse_date(row.get('visit_date')),
                            'weight_g': weight_g_final,
                            'weight_kg': weight_kg_final,
                            'height_cm': self._safe_float(row.get('height_cm')),
                            'head_circumference_cm': self._safe_float(row.get('head_circumference_cm')),
                            'notes': row.get('notes', '').strip(),
                            'raw_visit_entry': row.get('raw_visit_entry', '').strip(),
                            'visit_type': 'pediatric',  # Default for CSV imports
                            'vital_signs': None,  # Will be populated if needed
                            'chief_complaint': None,
                            'subjective': None,
                            'objective': None,
                            'assessment': None,
                            'plan': None
                        }
                        
                        # Validate required fields
                        if not visit_data['patient_id'] or not visit_data['visit_date']:
                            error_msg = f"Visits row {row_num}: Missing required fields (patient_id, visit_date)"
                            self.logger.warning(error_msg)
                            self.detailed_errors.append(error_msg)
                            stats['errors'] += 1
                            continue
                        
                        # Check if patient exists
                        cursor.execute("SELECT id FROM Patients WHERE id = ?", (visit_data['patient_id'],))
                        if not cursor.fetchone():
                            error_msg = f"Visits row {row_num}: Patient ID {visit_data['patient_id']} not found"
                            self.logger.warning(error_msg)
                            self.detailed_errors.append(error_msg)
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
                                        patient_id = ?, visit_date = ?, weight_g = ?, weight_kg = ?,
                                        height_cm = ?, head_circumference_cm = ?, notes = ?,
                                        raw_visit_entry = ?, visit_type = ?
                                    WHERE id = ?
                                """, (
                                    visit_data['patient_id'], visit_data['visit_date'], visit_data['weight_g'],
                                    visit_data['weight_kg'], visit_data['height_cm'], visit_data['head_circumference_cm'],
                                    visit_data['notes'], visit_data['raw_visit_entry'], visit_data['visit_type'],
                                    existing_visit[0]
                                ))
                                stats['updated'] += 1
                            else:
                                stats['skipped'] += 1
                        else:
                            # Insert new visit
                            cursor.execute("""
                                INSERT INTO Visits (
                                    patient_id, visit_date, weight_g, weight_kg, height_cm,
                                    head_circumference_cm, notes, raw_visit_entry, visit_type
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                visit_data['patient_id'], visit_data['visit_date'], visit_data['weight_g'],
                                visit_data['weight_kg'], visit_data['height_cm'], visit_data['head_circumference_cm'],
                                visit_data['notes'], visit_data['raw_visit_entry'], visit_data['visit_type']
                            ))
                            stats['imported'] += 1
                            
                    except Exception as e:
                        error_msg = f"Visits row {row_num}: {str(e)} - Data: {dict(row)}"
                        self.logger.error(error_msg)
                        self.detailed_errors.append(error_msg)
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
                        
                        # Handle administered_date - skip records with "None" or empty dates
                        administered_date_raw = row.get('administered_date', '').strip()
                        if administered_date_raw.lower() == 'none' or not administered_date_raw:
                            # Skip immunizations without valid dates
                            stats['skipped'] += 1
                            continue
                        
                        immunization_data = {
                            'patient_id': mapped_patient_id,
                            'immunization': row.get('immunization', '').strip(),
                            'administered_date': self._parse_date(administered_date_raw),
                            'brand_name': row.get('brand_name', '').strip(),
                            'dose_number': self._safe_int(row.get('dose_number')),
                            'notes': row.get('notes', '').strip()
                        }
                        
                        # Validate required fields
                        if not immunization_data['patient_id'] or not immunization_data['immunization'] or not immunization_data['administered_date']:
                            error_msg = f"Immunizations row {row_num}: Missing required fields (patient_id, immunization, administered_date)"
                            self.logger.warning(error_msg)
                            self.detailed_errors.append(error_msg)
                            stats['errors'] += 1
                            continue
                        
                        # Check if patient exists
                        cursor.execute("SELECT id FROM Patients WHERE id = ?", (immunization_data['patient_id'],))
                        if not cursor.fetchone():
                            error_msg = f"Immunizations row {row_num}: Patient ID {immunization_data['patient_id']} not found"
                            self.logger.warning(error_msg)
                            self.detailed_errors.append(error_msg)
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
                        error_msg = f"Immunizations row {row_num}: {str(e)} - Data: {dict(row)}"
                        self.logger.error(error_msg)
                        self.detailed_errors.append(error_msg)
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
    
    def get_detailed_errors(self, limit: int = 10) -> List[str]:
        """
        Get detailed error messages from the last import operation.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of detailed error messages
        """
        return self.detailed_errors[:limit]
    
    def clear_errors(self):
        """Clear the detailed errors list."""
        self.detailed_errors = []


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