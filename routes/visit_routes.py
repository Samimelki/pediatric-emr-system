# =============================================================================
# VISIT MANAGEMENT ROUTES MODULE
# 
# Extracted from patient_routes.py for better organization.
# Handles all visit-related functionality including:
# - Adding visits to patients
# - Editing visit measurements and dates
# - Adding visit addendums
# - Visit media management (upload/delete)
# =============================================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
import json
from datetime import datetime
from database import get_db
from word_document_manager import WordDocumentManager
from emr_config import emr_config
from utils.patient_utils import convert_weight_to_kg, convert_kg_to_storage_format
from utils.form_validators import parse_user_date_input, validate_date_not_before_birth

visit_bp = Blueprint('visit', __name__, url_prefix='/patient')

# =============================================================================
# VISIT CRUD OPERATIONS
# =============================================================================

@visit_bp.route('/<int:patient_id>/visit/add', methods=['POST'])
def add_visit(patient_id):
    """Add a new visit for a patient"""
    db = get_db()
    try:
        patient_cursor = db.execute("SELECT date_of_birth FROM Patients WHERE id = ?", (patient_id,))
        patient_data = patient_cursor.fetchone()
        patient_birth_date = None
        if patient_data and patient_data['date_of_birth']:
            try:
                patient_birth_date = datetime.strptime(patient_data['date_of_birth'].split('T')[0], '%Y-%m-%d').date()
            except ValueError:
                flash("Patient's birth date is invalid. Please correct it before adding new visits.", 'warning')

        visit_date_str = request.form.get('visit_date')
        # Adult vital fields
        weight_kg = request.form.get('weight_kg')
        bp = request.form.get('bp')
        temperature = request.form.get('temperature')
        hr = request.form.get('hr')
        spo2 = request.form.get('spo2')
        # Pediatric measurement fields (stored as direct columns)
        weight_g = request.form.get('weight_g')
        height_cm = request.form.get('height_cm')
        head_circumference_cm = request.form.get('head_circumference_cm')
        chief_complaint = request.form.get('chief_complaint', '').strip()
        subjective = request.form.get('subjective', '').strip()
        objective = request.form.get('objective', '').strip()
        assessment = request.form.get('assessment', '').strip()
        plan = request.form.get('plan', '').strip()
        notes = request.form.get('visit_notes', '').strip()

        if not visit_date_str or not notes:
            flash('Visit date and notes are required.', 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # Parse visit date using extracted utility
        date_result = parse_user_date_input(visit_date_str, "visit date")
        if not date_result['success']:
            flash(date_result['error_message'], 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))
        
        visit_date_obj = date_result['parsed_date']
        visit_date_iso = date_result['iso_date']
        formatted_date_for_raw = visit_date_obj.strftime('%d-%m-%y')

        # Validate visit date is not before birth date
        birth_date_str = patient_birth_date.strftime('%Y-%m-%d') if patient_birth_date else None
        birth_validation = validate_date_not_before_birth(visit_date_obj, birth_date_str, visit_date_str)
        if not birth_validation['success']:
            flash(f"Error: {birth_validation['error_message']}", 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # Build the vital_signs JSON
        vital_signs = {
            'weight_kg': float(weight_kg) if weight_kg else None,
            'height_cm': float(height_cm) if height_cm else None,
            'head_circumference_cm': float(head_circumference_cm) if head_circumference_cm else None,
            'bp': bp if bp else None,
            'temperature': float(temperature) if temperature else None,
            'hr': int(hr) if hr else None,
            'spo2': float(spo2) if spo2 else None
        }
        vital_signs = {k: v for k, v in vital_signs.items() if v is not None}
        vital_signs_json = json.dumps(vital_signs)

        # Use weight_g directly from form or convert from weight_kg if provided
        weight_g_val = None
        if weight_g:
            weight_g_val = float(weight_g)
        elif weight_kg:
            weight_g_val = convert_kg_to_storage_format(weight_kg)
        height_cm_val = float(height_cm) if height_cm else None
        head_circumference_cm_val = float(head_circumference_cm) if head_circumference_cm else None

        # Compose a readable string for raw_visit_entry
        vs_parts = []
        if weight_g_val: 
            # Display weight in kg format for readability
            weight_display = convert_weight_to_kg(weight_g_val)
            vs_parts.append(f"W: {weight_display} kg")
        elif weight_kg: 
            vs_parts.append(f"W: {weight_kg} kg")
        if height_cm: vs_parts.append(f"H: {height_cm} cm")
        if head_circumference_cm: vs_parts.append(f"HC: {head_circumference_cm} cm")
        if bp: vs_parts.append(f"BP: {bp}")
        if temperature: vs_parts.append(f"Temp: {temperature}°C")
        if hr: vs_parts.append(f"HR: {hr}")
        if spo2: vs_parts.append(f"SpO2: {spo2}%")
        vs_string = ", ".join(vs_parts)

        raw_visit_parts = [f"*{formatted_date_for_raw}*"]
        if vs_string: raw_visit_parts.append(f"VS: {vs_string}")
        if chief_complaint: raw_visit_parts.append(f"CC: {chief_complaint}")
        if subjective: raw_visit_parts.append(f"Subjective: {subjective}")
        if objective: raw_visit_parts.append(f"Objective: {objective}")
        if assessment: raw_visit_parts.append(f"Assessment: {assessment}")
        if plan: raw_visit_parts.append(f"Plan: {plan}")
        raw_visit_parts.append(f"- Notes: {notes}")
        raw_visit_entry = ' '.join(raw_visit_parts)

        sql_insert_visit = """INSERT INTO Visits \
            (patient_id, visit_date, weight_g, height_cm, head_circumference_cm, vital_signs, chief_complaint, subjective, objective, assessment, plan, notes, raw_visit_entry) \
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        db.execute(sql_insert_visit, (
            patient_id, visit_date_iso, weight_g_val, height_cm_val, head_circumference_cm_val, vital_signs_json, 
            chief_complaint, subjective, objective, assessment, plan, notes, raw_visit_entry
        ))
        
        patient_cursor = db.execute("SELECT raw_dossier_text FROM Patients WHERE id = ?", (patient_id,))
        patient_data = patient_cursor.fetchone()
        current_dossier_text = patient_data['raw_dossier_text'] if patient_data['raw_dossier_text'] else ''
        updated_dossier_text = (current_dossier_text + '\n' if current_dossier_text and not current_dossier_text.endswith('\n') else current_dossier_text) + raw_visit_entry
        db.execute("UPDATE Patients SET raw_dossier_text = ? WHERE id = ?", (updated_dossier_text, patient_id))
        
        db.commit()
        # Update Word document after adding visit
        word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
        word_manager.create_or_update_document(patient_id)
        flash('New visit added successfully!', 'success')

    except sqlite3.Error as e:
        db.rollback()
        flash(f"Database error adding visit: {e}", 'danger')
    except ValueError as e:
        db.rollback()
        flash(f"Invalid data for visit: {e}", 'danger')
    except Exception as e:
        db.rollback()
        flash(f"An unexpected error occurred while adding visit: {e}", 'danger')

    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@visit_bp.route('/visit/<int:visit_id>/addendum', methods=['POST'])
def add_visit_addendum(visit_id):
    """Add an addendum to an existing visit"""
    db = get_db()
    try:
        addendum_text = request.form.get('addendum_text', '').strip()
        if not addendum_text:
            flash('Addendum text cannot be empty.', 'danger')
            visit_cursor = db.execute("SELECT patient_id FROM Visits WHERE id = ?", (visit_id,))
            visit = visit_cursor.fetchone()
            if visit:
                return redirect(url_for('patient.patient_detail', patient_id=visit['patient_id']))
            else:
                flash('Original visit not found while trying to add addendum.', 'danger')
                return redirect(url_for('patient.list_patients'))

        current_dt_obj = datetime.now()
        addendum_datetime_iso = current_dt_obj.strftime('%Y-%m-%d %H:%M:%S')
        addendum_datetime_formatted = current_dt_obj.strftime('%d-%m-%y %H:%M')

        visit_cursor = db.execute("SELECT patient_id, visit_date FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        if not visit:
            flash('Original visit not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        patient_id = visit['patient_id']
        original_visit_date_iso = visit['visit_date']
        try:
            original_visit_date_obj = datetime.strptime(original_visit_date_iso, '%Y-%m-%d')
            original_visit_date_formatted = original_visit_date_obj.strftime('%d-%m-%y')
        except (ValueError, TypeError):
            original_visit_date_formatted = original_visit_date_iso

        raw_addendum_entry = f"*ADDENDUM to visit of {original_visit_date_formatted}* {addendum_text} - (Added: {addendum_datetime_formatted})*"

        sql_insert_addendum = "INSERT INTO VisitAddenda (visit_id, addendum_datetime, addendum_text, raw_addendum_entry) VALUES (?, ?, ?, ?)"
        db.execute(sql_insert_addendum, (visit_id, addendum_datetime_iso, addendum_text, raw_addendum_entry))

        patient_cursor = db.execute("SELECT raw_dossier_text FROM Patients WHERE id = ?", (patient_id,))
        patient_data = patient_cursor.fetchone()
        current_dossier_text = patient_data['raw_dossier_text'] if patient_data and patient_data['raw_dossier_text'] else ''
        
        if current_dossier_text and not current_dossier_text.endswith('\n'):
            updated_dossier_text = current_dossier_text + '\n' + raw_addendum_entry
        else:
            updated_dossier_text = current_dossier_text + raw_addendum_entry
        
        db.execute("UPDATE Patients SET raw_dossier_text = ? WHERE id = ?", (updated_dossier_text, patient_id))
        
        db.commit()
        # Update Word document after addendum
        word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
        word_manager.create_or_update_document(patient_id)
        flash('Visit addendum added successfully!', 'success')

    except sqlite3.Error as e:
        db.rollback()
        flash(f"Database error adding addendum: {e}", 'danger')
    except Exception as e:
        db.rollback()
        flash(f"An unexpected error occurred: {e}", 'danger')
    
    if 'patient_id' in locals() and patient_id is not None:
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    else:
        return redirect(request.referrer or url_for('patient.list_patients'))

# =============================================================================
# VISIT MEASUREMENTS MANAGEMENT
# =============================================================================

@visit_bp.route('/visit/<int:visit_id>/edit_measurements', methods=['GET'])
def edit_visit_measurements(visit_id):
    """Display form to edit visit measurements"""
    db = get_db()
    try:
        visit_cursor = db.execute("SELECT * FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        
        if not visit:
            flash('Visit not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (visit['patient_id'],))
        patient = patient_cursor.fetchone()
        
        if not patient:
            flash('Patient not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        return render_template('edit_visit_measurements.html', 
                             title='Edit Visit Measurements',
                             visit=visit, 
                             patient=patient)
                             
    except Exception as e:
        flash(f'Error loading visit measurements: {e}', 'danger')
        return redirect(url_for('patient.list_patients'))

@visit_bp.route('/visit/<int:visit_id>/edit_measurements', methods=['POST'])
def update_visit_measurements(visit_id):
    """Update visit measurements"""
    db = get_db()
    try:
        # Get the current visit to validate it exists and get patient_id
        visit_cursor = db.execute("SELECT patient_id FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        
        if not visit:
            flash('Visit not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        patient_id = visit['patient_id']
        
        # Get form data
        weight_g = request.form.get('weight_g')
        height_cm = request.form.get('height_cm')
        head_circumference_cm = request.form.get('head_circumference_cm')
        
        # Convert empty strings to None for database storage
        weight_g_val = float(weight_g) if weight_g else None
        height_cm_val = float(height_cm) if height_cm else None
        head_circumference_cm_val = float(head_circumference_cm) if head_circumference_cm else None
        
        # Update the visit
        db.execute("""
            UPDATE Visits 
            SET weight_g = ?, height_cm = ?, head_circumference_cm = ?
            WHERE id = ?
        """, (weight_g_val, height_cm_val, head_circumference_cm_val, visit_id))
        
        db.commit()
        
        # Update Word document
        word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
        word_manager.create_or_update_document(patient_id)
        
        flash('Visit measurements updated successfully!', 'success')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
        
    except ValueError as e:
        flash(f'Invalid measurement values: {e}', 'danger')
        return redirect(url_for('visit.edit_visit_measurements', visit_id=visit_id))
    except Exception as e:
        db.rollback()
        flash(f'Error updating visit measurements: {e}', 'danger')
        return redirect(url_for('visit.edit_visit_measurements', visit_id=visit_id))

# =============================================================================
# VISIT DATE MANAGEMENT
# =============================================================================

@visit_bp.route('/visit/<int:visit_id>/edit_date', methods=['GET'])
def edit_visit_date(visit_id):
    """Display form to edit visit date"""
    db = get_db()
    try:
        visit_cursor = db.execute("SELECT * FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        
        if not visit:
            flash('Visit not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (visit['patient_id'],))
        patient = patient_cursor.fetchone()
        
        if not patient:
            flash('Patient not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        return render_template('edit_visit_date.html', 
                             title='Edit Visit Date',
                             visit=visit, 
                             patient=patient)
                             
    except Exception as e:
        flash(f'Error loading visit date editor: {e}', 'danger')
        return redirect(url_for('patient.list_patients'))

@visit_bp.route('/visit/<int:visit_id>/edit_date', methods=['POST'])
def edit_single_visit_date(visit_id):
    """Update a single visit's date"""
    db = get_db()
    try:
        # Get the current visit to validate it exists and get patient info
        visit_cursor = db.execute("SELECT v.*, p.date_of_birth FROM Visits v JOIN Patients p ON v.patient_id = p.id WHERE v.id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        
        if not visit:
            flash('Visit not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        patient_id = visit['patient_id']
        patient_birth_date_str = visit['date_of_birth']
        
        new_visit_date_str = request.form.get('visit_date')
        if not new_visit_date_str:
            flash('Visit date is required.', 'danger')
            return redirect(url_for('visit.edit_visit_date', visit_id=visit_id))

        # Parse visit date using extracted utility
        date_result = parse_user_date_input(new_visit_date_str, "visit date")
        if not date_result['success']:
            flash(date_result['error_message'], 'danger')
            return redirect(url_for('visit.edit_visit_date', visit_id=visit_id))
        
        visit_date_obj = date_result['parsed_date']
        visit_date_iso = date_result['iso_date']

        # Validate visit date is not before birth date
        birth_validation = validate_date_not_before_birth(visit_date_obj, patient_birth_date_str, new_visit_date_str)
        if not birth_validation['success']:
            flash(f"Error: {birth_validation['error_message']}", 'danger')
            return redirect(url_for('visit.edit_visit_date', visit_id=visit_id))

        # Update the visit date
        db.execute("UPDATE Visits SET visit_date = ? WHERE id = ?", (visit_date_iso, visit_id))
        db.commit()
        
        # Update Word document
        word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
        word_manager.create_or_update_document(patient_id)
        
        flash('Visit date updated successfully!', 'success')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
        
    except Exception as e:
        db.rollback()
        flash(f'Error updating visit date: {e}', 'danger')
        return redirect(url_for('visit.edit_visit_date', visit_id=visit_id))

# =============================================================================
# VISIT MEDIA MANAGEMENT
# =============================================================================

@visit_bp.route('/visit/<int:visit_id>/upload_media', methods=['POST'])
def upload_visit_media(visit_id):
    """Upload media files for a visit"""
    db = get_db()
    try:
        visit_cursor = db.execute("SELECT patient_id FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        
        if not visit:
            flash('Visit not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        patient_id = visit['patient_id']
        
        if 'media_files' not in request.files:
            flash('No files selected.', 'warning')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))
        
        files = request.files.getlist('media_files')
        
        for file in files:
            if file and file.filename:
                # Here you would implement the actual file upload logic
                # For now, we'll just save the filename to the database
                db.execute("""
                    INSERT INTO VisitMedia (visit_id, filename, file_type, uploaded_date)
                    VALUES (?, ?, ?, ?)
                """, (visit_id, file.filename, file.content_type, datetime.now().isoformat()))
        
        db.commit()
        flash(f'{len([f for f in files if f.filename])} files uploaded successfully!', 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'Error uploading media: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@visit_bp.route('/visit/<int:visit_id>/media/<int:media_id>/delete', methods=['POST'])
def delete_visit_media(visit_id, media_id):
    """Delete a media file from a visit"""
    db = get_db()
    try:
        # Get the visit to find patient_id
        visit_cursor = db.execute("SELECT patient_id FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        
        if not visit:
            flash('Visit not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        patient_id = visit['patient_id']
        
        # Delete the media record
        db.execute("DELETE FROM VisitMedia WHERE id = ? AND visit_id = ?", (media_id, visit_id))
        db.commit()
        
        flash('Media file deleted successfully!', 'success')
        
    except Exception as e:
        db.rollback()
        flash(f'Error deleting media: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id)) 