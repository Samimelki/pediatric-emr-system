import os
import sqlite3
from typing import Dict, Any, Optional, List, Tuple
from word_document_manager import WordDocumentManager
from database import get_db, get_custom_demographic_fields
from config_manager import load_config

class DatabaseOperations:
    def __init__(self, db_path: str, documents_folder: str):
        self.db_path = db_path
        self.documents_folder = documents_folder
        self.config = load_config()
        self.word_manager = WordDocumentManager(db_path, documents_folder)
        self._ensure_word_documents_folder()

    def _ensure_word_documents_folder(self):
        """Ensure the Word documents folder exists"""
        if not os.path.exists(self.documents_folder):
            os.makedirs(self.documents_folder)
            print(f"Created Word documents folder at: {self.documents_folder}")

    def create_patient(self, patient_data: Dict[str, Any]) -> Tuple[int, str]:
        """Create a new patient and their Word document."""
        db = get_db()
        cursor = db.cursor()
        try:
            # Insert patient data
            columns = [
                'mrn', 'first_name', 'last_name', 'date_of_birth', 'sex', 'phone',
                'address', 'email', 'insurance', 'primary_physician', 'pmh', 'psh',
                'family_history', 'medications', 'allergies', 'smoker', 'smoker_details',
                'alcohol', 'alcohol_details', 'raw_dossier_text'
            ]
            placeholders = ', '.join(['?' for _ in columns])
            values = [patient_data.get(col, '') for col in columns]
            
            cursor.execute(
                f"INSERT INTO Patients ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            patient_id = cursor.lastrowid
            
            # Create Word document
            doc_path = self.word_manager.create_or_update_document(patient_id)
            
            db.commit()
            return patient_id, doc_path
        except Exception as e:
            db.rollback()
            raise e

    def update_patient(self, patient_id: int, patient_data: Dict[str, Any]) -> str:
        """Update patient data and their Word document."""
        db = get_db()
        cursor = db.cursor()
        try:
            # Update patient data
            set_clause = ', '.join([f"{col} = ?" for col in patient_data.keys()])
            values = list(patient_data.values())
            values.append(patient_id)
            
            cursor.execute(
                f"UPDATE Patients SET {set_clause} WHERE id = ?",
                values
            )
            
            # Update Word document
            doc_path = self.word_manager.create_or_update_document(patient_id)
            
            db.commit()
            return doc_path
        except Exception as e:
            db.rollback()
            raise e

    def add_visit(self, patient_id: int, visit_data: Dict[str, Any]) -> Tuple[int, str]:
        """Add a new visit and update the patient's Word document."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Insert visit data
            columns = [
                'patient_id', 'visit_date', 'vital_signs', 'chief_complaint',
                'subjective', 'objective', 'assessment', 'plan', 'notes',
                'raw_visit_entry'
            ]
            placeholders = ', '.join(['?' for _ in columns])
            values = [visit_data.get(col, '') for col in columns]
            values[0] = patient_id  # Ensure patient_id is set
            
            cursor.execute(
                f"INSERT INTO Visits ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            visit_id = cursor.lastrowid
            
            # Update Word document
            doc_path = self.word_manager.create_or_update_patient_document(patient_id)
            
            conn.commit()
            return visit_id, doc_path
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_visit(self, visit_id: int, visit_data: Dict[str, Any]) -> str:
        """Update a visit and the patient's Word document."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Get patient_id for this visit
            cursor.execute("SELECT patient_id FROM Visits WHERE id = ?", (visit_id,))
            result = cursor.fetchone()
            if not result:
                raise ValueError(f"Visit with ID {visit_id} not found")
            patient_id = result['patient_id']
            
            # Update visit data
            set_clause = ', '.join([f"{col} = ?" for col in visit_data.keys()])
            values = list(visit_data.values())
            values.append(visit_id)
            
            cursor.execute(
                f"UPDATE Visits SET {set_clause} WHERE id = ?",
                values
            )
            
            # Update Word document
            doc_path = self.word_manager.create_or_update_patient_document(patient_id)
            
            conn.commit()
            return doc_path
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def delete_patient(self, patient_id: int) -> None:
        """Delete a patient and their Word document."""
        db = get_db()
        cursor = db.cursor()
        try:
            # Get patient data to find the Word document
            cursor.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
            patient = cursor.fetchone()
            if patient:
                # Delete visits first (due to foreign key constraint)
                cursor.execute("DELETE FROM Visits WHERE patient_id = ?", (patient_id,))
                # Delete patient
                cursor.execute("DELETE FROM Patients WHERE id = ?", (patient_id,))
                
                # Delete Word document if it exists
                filename = self.word_manager._format_filename(dict(patient))
                doc_path = os.path.join(self.documents_folder, filename)
                if os.path.exists(doc_path):
                    os.remove(doc_path)
            
            db.commit()
        except Exception as e:
            db.rollback()
            raise e

    def rename_all_documents(self) -> List[Tuple[str, str]]:
        """Rename all existing Word documents to match the new naming convention."""
        return self.word_manager.rename_existing_documents()

    def import_patients(self, patients_data: List[Dict[str, Any]]) -> List[Tuple[int, str]]:
        """Import multiple patients and create their Word documents."""
        results = []
        db = get_db()
        cursor = db.cursor()
        try:
            for patient_data in patients_data:
                # Insert patient data
                columns = [
                    'mrn', 'first_name', 'last_name', 'date_of_birth', 'sex', 'phone',
                    'address', 'email', 'insurance', 'primary_physician', 'pmh', 'psh',
                    'family_history', 'medications', 'allergies', 'smoker', 'smoker_details',
                    'alcohol', 'alcohol_details', 'raw_dossier_text'
                ]
                placeholders = ', '.join(['?' for _ in columns])
                values = [patient_data.get(col, '') for col in columns]
                
                cursor.execute(
                    f"INSERT INTO Patients ({', '.join(columns)}) VALUES ({placeholders})",
                    values
                )
                patient_id = cursor.lastrowid
                
                # Create Word document
                doc_path = self.word_manager.create_or_update_document(patient_id)
                results.append((patient_id, doc_path))
            
            db.commit()
            return results
        except Exception as e:
            db.rollback()
            raise e

    def add_patient(self, patient_data):
        """Add a new patient and create their Word document"""
        try:
            # Add patient to database
            patient_id = self.db.execute("""
                INSERT INTO patients (
                    first_name, last_name, date_of_birth, sex, phone, address, email,
                    insurance, primary_physician, pmh, psh, family_history, medications,
                    allergies, smoker, smoker_details, alcohol, alcohol_details, raw_dossier_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                patient_data.get('first_name', ''),
                patient_data.get('last_name', ''),
                patient_data.get('date_of_birth', ''),
                patient_data.get('sex', ''),
                patient_data.get('phone', ''),
                patient_data.get('address', ''),
                patient_data.get('email', ''),
                patient_data.get('insurance', ''),
                patient_data.get('primary_physician', ''),
                patient_data.get('pmh', ''),
                patient_data.get('psh', ''),
                patient_data.get('family_history', ''),
                patient_data.get('medications', ''),
                patient_data.get('allergies', ''),
                patient_data.get('smoker', False),
                patient_data.get('smoker_details', ''),
                patient_data.get('alcohol', False),
                patient_data.get('alcohol_details', ''),
                patient_data.get('raw_dossier_text', '')
            )).lastrowid
            
            # Create Word document for the new patient
            self.word_manager.create_or_update_document(patient_id)
            
            return patient_id
        except Exception as e:
            print(f"Error adding patient: {str(e)}")
            raise

    def update_patient(self, patient_id, patient_data):
        """Update patient data and their Word document"""
        try:
            # Update patient in database
            self.db.execute("""
                UPDATE patients SET
                    first_name = ?, last_name = ?, date_of_birth = ?, sex = ?,
                    phone = ?, address = ?, email = ?, insurance = ?,
                    primary_physician = ?, pmh = ?, psh = ?, family_history = ?,
                    medications = ?, allergies = ?, smoker = ?, smoker_details = ?,
                    alcohol = ?, alcohol_details = ?, raw_dossier_text = ?
                WHERE id = ?
            """, (
                patient_data.get('first_name', ''),
                patient_data.get('last_name', ''),
                patient_data.get('date_of_birth', ''),
                patient_data.get('sex', ''),
                patient_data.get('phone', ''),
                patient_data.get('address', ''),
                patient_data.get('email', ''),
                patient_data.get('insurance', ''),
                patient_data.get('primary_physician', ''),
                patient_data.get('pmh', ''),
                patient_data.get('psh', ''),
                patient_data.get('family_history', ''),
                patient_data.get('medications', ''),
                patient_data.get('allergies', ''),
                patient_data.get('smoker', False),
                patient_data.get('smoker_details', ''),
                patient_data.get('alcohol', False),
                patient_data.get('alcohol_details', ''),
                patient_data.get('raw_dossier_text', ''),
                patient_id
            ))
            
            # Update Word document
            self.word_manager.create_or_update_document(patient_id)
            
            return True
        except Exception as e:
            print(f"Error updating patient: {str(e)}")
            raise

    def import_patients(self, patients_data):
        """Import multiple patients and create their Word documents"""
        try:
            for patient_data in patients_data:
                patient_id = self.add_patient(patient_data)
                # Word document is created in add_patient
            return True
        except Exception as e:
            print(f"Error importing patients: {str(e)}")
            raise 