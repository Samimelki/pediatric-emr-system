import os
import sqlite3
from datetime import datetime
from docx import Document  # RESTORED for dual format support
from docx.shared import Pt  # RESTORED for dual format support
from docx.enum.text import WD_ALIGN_PARAGRAPH  # RESTORED for dual format support
from emr_config import emr_config
from database import get_db
from typing import Optional, Dict, Any

class WordDocumentManager:
    def __init__(self, db_path: str, documents_folder: str):
        self.db_path = db_path
        self.documents_folder = documents_folder
        self.config = emr_config
        self._ensure_documents_folder()

    def _ensure_documents_folder(self):
        """Ensure the documents folder exists"""
        if not os.path.exists(self.documents_folder):
            os.makedirs(self.documents_folder)
            print(f"Created documents folder at: {self.documents_folder}")

    def format_filename(self, first_name, last_name, date_of_birth, format_type='md'):
        """Format filename according to the specified pattern."""
        extension = '.docx' if format_type == 'docx' else '.md'
        
        if not date_of_birth:
            # If date of birth is missing, use a placeholder
            return f"{first_name} {last_name} NO_DOB{extension}"
        
        try:
            # Parse the date string into a datetime object
            dob = datetime.strptime(date_of_birth, '%Y-%m-%d')
            # Format the date as ddmmyyyy
            formatted_date = dob.strftime('%d%m%Y')
            return f"{first_name} {last_name} {formatted_date}{extension}"
        except (ValueError, TypeError):
            # If date parsing fails, use a placeholder
            return f"{first_name} {last_name} INVALID_DOB{extension}"

    def _get_patient_data(self, patient_id: int) -> dict:
        """Get patient data from database"""
        db = get_db()
        cursor = db.cursor()
        cursor.execute("""
            SELECT first_name, last_name, date_of_birth, sex, phone, address, email,
                   insurance, primary_physician, pmh, psh, family_history, medications,
                   allergies, smoker, smoker_details, alcohol, alcohol_details, raw_dossier_text
            FROM patients WHERE id = ?
        """, (patient_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Patient with ID {patient_id} not found")
        
        return {
            'first_name': row[0],
            'last_name': row[1],
            'date_of_birth': row[2],
            'sex': row[3],
            'phone': row[4],
            'address': row[5],
            'email': row[6],
            'insurance': row[7],
            'primary_physician': row[8],
            'pmh': row[9],
            'psh': row[10],
            'family_history': row[11],
            'medications': row[12],
            'allergies': row[13],
            'smoker': row[14],
            'smoker_details': row[15],
            'alcohol': row[16],
            'alcohol_details': row[17],
            'raw_dossier_text': row[18]
        }

    def _format_filename(self, patient_data: dict, format_type='md') -> str:
        """Format filename according to convention"""
        extension = '.docx' if format_type == 'docx' else '.md'
        try:
            dob = datetime.strptime(patient_data['date_of_birth'], '%Y-%m-%d')
            formatted_dob = dob.strftime('%d%m%Y')
            return f"{patient_data['first_name']}_{patient_data['last_name']}_{formatted_dob}{extension}"
        except (ValueError, TypeError):
            return f"{patient_data['first_name']}_{patient_data['last_name']}_NO_DOB{extension}"

    def _get_patient_visits(self, patient_id: int) -> list:
        """Retrieve all visits for a patient."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT * FROM Visits 
                WHERE patient_id = ? 
                ORDER BY visit_date DESC
            """, (patient_id,))
            visits = cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, visit)) for visit in visits]
        finally:
            conn.close()

    def create_or_update_document(self, patient_id: int, format_type='md') -> str:
        """Create or update a document for a patient in specified format (md or docx)"""
        if format_type == 'docx':
            return self._create_docx_document(patient_id)
        else:
            return self._create_markdown_document(patient_id)

    def _create_markdown_document(self, patient_id: int) -> str:
        """Create or update a markdown document for a patient (FAST version)"""
        try:
            # Ensure folder exists
            self._ensure_documents_folder()
            
            # Get patient data
            patient_data = self._get_patient_data(patient_id)
            
            # Format filename
            filename = self._format_filename(patient_data, 'md')
            filepath = os.path.join(self.documents_folder, filename)
            
            # Create markdown content (MUCH FASTER than docx)
            content = self._create_markdown_content(patient_data, patient_id)
            
            # Write to file (simple text write - very fast)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Created/updated markdown document: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"Error creating/updating markdown document: {str(e)}")
            raise

    def _create_docx_document(self, patient_id: int) -> str:
        """Create or update a Word document for a patient (PRETTY but slower version)"""
        try:
            # Ensure folder exists
            self._ensure_documents_folder()
            
            # Get patient data
            patient_data = self._get_patient_data(patient_id)
            
            # Format filename
            filename = self._format_filename(patient_data, 'docx')
            filepath = os.path.join(self.documents_folder, filename)
            
            # Create or update document
            doc = Document()
            
            # Add patient information
            doc.add_heading('Patient Information', 0)
            doc.add_paragraph(f"Name: {patient_data['first_name']} {patient_data['last_name']}")
            doc.add_paragraph(f"Date of Birth: {patient_data['date_of_birth']}")
            doc.add_paragraph(f"Sex: {patient_data['sex']}")
            doc.add_paragraph(f"Phone: {patient_data['phone']}")
            doc.add_paragraph(f"Address: {patient_data['address']}")
            doc.add_paragraph(f"Email: {patient_data['email']}")
            doc.add_paragraph(f"Insurance: {patient_data['insurance']}")
            doc.add_paragraph(f"Primary Physician: {patient_data['primary_physician']}")
            
            # Add medical information
            doc.add_heading('Medical Information', 1)
            doc.add_paragraph(f"Past Medical History: {patient_data['pmh']}")
            doc.add_paragraph(f"Past Surgical History: {patient_data['psh']}")
            doc.add_paragraph(f"Family History: {patient_data['family_history']}")
            doc.add_paragraph(f"Medications: {patient_data['medications']}")
            doc.add_paragraph(f"Allergies: {patient_data['allergies']}")
            
            # Add lifestyle information
            doc.add_heading('Lifestyle Information', 1)
            doc.add_paragraph(f"Smoker: {'Yes' if patient_data['smoker'] else 'No'}")
            if patient_data['smoker']:
                doc.add_paragraph(f"Smoking Details: {patient_data['smoker_details']}")
            doc.add_paragraph(f"Alcohol: {'Yes' if patient_data['alcohol'] else 'No'}")
            if patient_data['alcohol']:
                doc.add_paragraph(f"Alcohol Details: {patient_data['alcohol_details']}")
            
            # Add raw dossier text if available
            if patient_data['raw_dossier_text']:
                doc.add_heading('Raw Dossier Text', 1)
                doc.add_paragraph(patient_data['raw_dossier_text'])
            
            # Add visits if any
            visits = self._get_patient_visits(patient_id)
            if visits:
                doc.add_heading('Visit History', 1)
                for visit in visits:
                    doc.add_heading(f"Visit on {visit.get('visit_date', 'Unknown date')}", 2)
                    if visit.get('notes'):
                        doc.add_paragraph(f"Notes: {visit['notes']}")
                    if visit.get('weight_g'):
                        doc.add_paragraph(f"Weight: {visit['weight_g']}g")
                    if visit.get('height_cm'):
                        doc.add_paragraph(f"Height: {visit['height_cm']}cm")
                    if visit.get('head_circumference_cm'):
                        doc.add_paragraph(f"Head Circumference: {visit['head_circumference_cm']}cm")
            
            # Save document
            doc.save(filepath)
            print(f"Created/updated Word document: {filepath}")
            
            return filepath
        except Exception as e:
            print(f"Error creating/updating Word document: {str(e)}")
            raise

    def _create_markdown_content(self, patient_data: dict, patient_id: int) -> str:
        """Create markdown content for patient (fast alternative to docx)"""
        content = []
        
        # Header
        content.append(f"# Patient Record: {patient_data['first_name']} {patient_data['last_name']}")
        content.append(f"*Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        content.append("")
        
        # Patient Information
        content.append("## Patient Information")
        content.append(f"- **Name:** {patient_data['first_name']} {patient_data['last_name']}")
        content.append(f"- **Date of Birth:** {patient_data['date_of_birth'] or 'N/A'}")
        content.append(f"- **Sex:** {patient_data['sex'] or 'N/A'}")
        content.append(f"- **Phone:** {patient_data['phone'] or 'N/A'}")
        content.append(f"- **Address:** {patient_data['address'] or 'N/A'}")
        content.append(f"- **Email:** {patient_data['email'] or 'N/A'}")
        content.append(f"- **Insurance:** {patient_data['insurance'] or 'N/A'}")
        content.append(f"- **Primary Physician:** {patient_data['primary_physician'] or 'N/A'}")
        content.append("")
        
        # Medical Information
        content.append("## Medical Information")
        content.append(f"- **Past Medical History:** {patient_data['pmh'] or 'N/A'}")
        content.append(f"- **Past Surgical History:** {patient_data['psh'] or 'N/A'}")
        content.append(f"- **Family History:** {patient_data['family_history'] or 'N/A'}")
        content.append(f"- **Medications:** {patient_data['medications'] or 'N/A'}")
        content.append(f"- **Allergies:** {patient_data['allergies'] or 'N/A'}")
        content.append("")
        
        # Lifestyle Information
        content.append("## Lifestyle Information")
        content.append(f"- **Smoker:** {'Yes' if patient_data['smoker'] else 'No'}")
        if patient_data['smoker'] and patient_data['smoker_details']:
            content.append(f"  - Details: {patient_data['smoker_details']}")
        content.append(f"- **Alcohol:** {'Yes' if patient_data['alcohol'] else 'No'}")
        if patient_data['alcohol'] and patient_data['alcohol_details']:
            content.append(f"  - Details: {patient_data['alcohol_details']}")
        content.append("")
        
        # Raw dossier text if available
        if patient_data['raw_dossier_text']:
            content.append("## Raw Dossier Text")
            content.append("```")
            content.append(patient_data['raw_dossier_text'])
            content.append("```")
            content.append("")
        
        # Add visits if any
        visits = self._get_patient_visits(patient_id)
        if visits:
            content.append("## Visit History")
            for visit in visits:
                content.append(f"### Visit on {visit.get('visit_date', 'Unknown date')}")
                if visit.get('notes'):
                    content.append(f"**Notes:** {visit['notes']}")
                if visit.get('weight_g'):
                    content.append(f"**Weight:** {visit['weight_g']}g")
                if visit.get('height_cm'):
                    content.append(f"**Height:** {visit['height_cm']}cm")
                if visit.get('head_circumference_cm'):
                    content.append(f"**Head Circumference:** {visit['head_circumference_cm']}cm")
                content.append("")
        
        content.append("---")
        content.append(f"*Document ID: {patient_id} | Generated by EMR System*")
        
        return "\n".join(content)

    def rename_existing_documents(self) -> list:
        """Rename all existing documents to match the new naming convention"""
        try:
            # Ensure folder exists
            self._ensure_documents_folder()
            
            renamed_files = []
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT id, first_name, last_name, date_of_birth FROM patients")
            patients = cursor.fetchall()
            
            for patient in patients:
                patient_id, first_name, last_name, dob = patient
                if dob:
                    try:
                        dob_date = datetime.strptime(dob, '%Y-%m-%d')
                        new_filename = f"{first_name}_{last_name}_{dob_date.strftime('%d%m%Y')}"
                        
                        # Find existing document for this patient (look for both .docx and .md)
                        for filename in os.listdir(self.documents_folder):
                            if filename.endswith(('.docx', '.md')):
                                old_filepath = os.path.join(self.documents_folder, filename)
                                extension = '.docx' if filename.endswith('.docx') else '.md'
                                new_filepath = os.path.join(self.documents_folder, new_filename + extension)
                                try:
                                    os.rename(old_filepath, new_filepath)
                                    renamed_files.append((old_filepath, new_filepath))
                                    print(f"Renamed: {old_filepath} -> {new_filepath}")
                                    break
                                except Exception as e:
                                    print(f"Error renaming {old_filepath}: {str(e)}")
                    except (ValueError, TypeError):
                        print(f"Invalid date format for patient {patient_id}: {dob}")
                        continue
            
            return renamed_files
        except Exception as e:
            print(f"Error renaming documents: {str(e)}")
            raise 