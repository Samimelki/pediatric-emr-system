from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import sqlite3
import math
from datetime import datetime, date
from collections import defaultdict
from database import get_db, get_active_custom_demographic_fields
from dateutil.relativedelta import relativedelta
import json
from config_manager import load_config, USER_MEDIA_FOLDER
from word_document_manager import WordDocumentManager
from werkzeug.utils import secure_filename
import mimetypes
import os

# Whitelist of editable standard demographic fields
EDITABLE_DEMOGRAPHIC_FIELDS = {
    'mrn': 'MRN',
    'first_name': 'First Name',
    'last_name': 'Last Name',
    'date_of_birth': 'Date of Birth (YYYY-MM-DD)',
    'sex': 'Sex (M/F/Other)',
    'phone': 'Phone',
    'address': 'Address',
    'email': 'Email',
    'insurance': 'Insurance',
    'primary_physician': 'Primary Physician',
    'pmh': 'Past Medical History',
    'psh': 'Past Surgical History',
    'medications': 'Medications',
    'allergies': 'Allergies',
    'smoker': 'Smoker',
    'smoker_details': 'Smoking Details',
    'alcohol': 'Alcohol Use',
    'alcohol_details': 'Alcohol Use Details'
}

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

# Configuration
PER_PAGE = 50

def calculate_age_at_visit(birth_date_iso: str, visit_date_iso: str) -> str:
    """Calculates age at visit and returns a human-readable string.
       Expects dates in 'YYYY-MM-DD' format.
    """
    if not birth_date_iso or not isinstance(birth_date_iso, str) or not birth_date_iso.strip():
        print(f"Debug: calculate_age_at_visit - Invalid or missing birth_date_iso: '{birth_date_iso}'")
        return "N/A (No DOB)"
    if not visit_date_iso or not isinstance(visit_date_iso, str) or not visit_date_iso.strip():
        print(f"Debug: calculate_age_at_visit - Invalid or missing visit_date_iso: '{visit_date_iso}'")
        return "N/A (No Visit Date)"

    try:
        # Directly parse YYYY-MM-DD format
        birth_date = datetime.strptime(birth_date_iso, '%Y-%m-%d').date()
        visit_date = datetime.strptime(visit_date_iso, '%Y-%m-%d').date()
    except ValueError as e_main:
        # Fallback for full ISO strings if somehow passed (e.g., 'YYYY-MM-DDTHH:MM:SS')
        try:
            birth_date_cleaned = birth_date_iso.split('T')[0]
            visit_date_cleaned = visit_date_iso.split('T')[0]
            birth_date = datetime.strptime(birth_date_cleaned, '%Y-%m-%d').date()
            visit_date = datetime.strptime(visit_date_cleaned, '%Y-%m-%d').date()
        except ValueError as e_fallback:
            print(f"Error: Could not parse dates for age calculation after multiple attempts. ")
            print(f"  Initial Birth ISO: '{birth_date_iso}', Initial Visit ISO: '{visit_date_iso}'")
            print(f"  Main parsing error: {e_main}")
            print(f"  Fallback parsing error: {e_fallback}")
            return "Invalid date format"

    if visit_date < birth_date:
        return "Visit before birth"

    delta = relativedelta(visit_date, birth_date)

    years = delta.years
    months = delta.months
    days = delta.days

    if years > 0:
        age_str = f"{years}y"
        if months > 0:
            age_str += f" {months}m"
        return age_str
    elif months > 0:
        age_str = f"{months}m"
        if days > 0:
            age_str += f" {days}d"
        return age_str
    elif days >= 0:
        return f"{days}d"
    else:
        return "N/A" # Should not happen

@patient_bp.route('s')
def list_patients():
    page = request.args.get('page', 1, type=int)
    search_last_name = request.args.get('last_name', '').strip()
    search_first_name = request.args.get('first_name', '').strip()
    search_date_of_birth = request.args.get('date_of_birth', '').strip()
    search_mrn = request.args.get('mrn', '').strip()

    sort_by = request.args.get('sort_by', 'last_name')
    sort_order = request.args.get('sort_order', 'asc')

    allowed_sort_columns = {'last_name', 'mrn', 'date_of_birth'}
    if sort_by not in allowed_sort_columns:
        sort_by = 'last_name'
    
    if sort_order not in {'asc', 'desc'}:
        sort_order = 'asc'

    db = get_db()
    
    base_query = "FROM Patients"
    count_query = "SELECT COUNT(*) "
    data_query = "SELECT id, mrn, first_name, last_name, date_of_birth "
    
    conditions = []
    params = {}

    if search_last_name:
        conditions.append("last_name LIKE :last_name")
        params['last_name'] = f"%{search_last_name}%"
    if search_first_name:
        conditions.append("first_name LIKE :first_name")
        params['first_name'] = f"%{search_first_name}%"
    if search_date_of_birth:
        conditions.append("date_of_birth = :date_of_birth")
        params['date_of_birth'] = search_date_of_birth
    if search_mrn:
        conditions.append("mrn LIKE :mrn")
        params['mrn'] = f"%{search_mrn}%"

    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        base_query += where_clause
    
    count_query += base_query
    total_patients_cursor = db.execute(count_query, params)
    total_patients = total_patients_cursor.fetchone()[0]
    total_pages = math.ceil(total_patients / PER_PAGE) if total_patients > 0 else 1
    page = min(page, total_pages)
    page = max(1, page)

    offset = (page - 1) * PER_PAGE
    
    if sort_by == 'last_name':
        order_by_clause = f"ORDER BY last_name {sort_order}, first_name {sort_order}"
    elif sort_by == 'mrn':
        order_by_clause = f"ORDER BY CAST(mrn AS INTEGER) {sort_order}"
    else:
        order_by_clause = f"ORDER BY {sort_by} {sort_order}"

    data_query += base_query + f" {order_by_clause} LIMIT :limit OFFSET :offset"
    params['limit'] = PER_PAGE
    params['offset'] = offset
    
    patients_cursor = db.execute(data_query, params)
    patients = patients_cursor.fetchall()
    
    return render_template('patients.html', 
                           patients=patients, 
                           page=page, 
                           total_pages=total_pages,
                           per_page=PER_PAGE,
                           search_last_name=search_last_name,
                           search_first_name=search_first_name,
                           search_date_of_birth=search_date_of_birth,
                           search_mrn=search_mrn, 
                           sort_by=sort_by, 
                           sort_order=sort_order, 
                           title="Patients")

@patient_bp.route('/<int:patient_id>')
def patient_detail(patient_id):
    db = get_db()
    patient = None
    visits_with_addenda = []
    # today_date = date.today().strftime('%Y-%m-%d') # Not directly used in template anymore for age

    active_custom_fields = get_active_custom_demographic_fields()
    grouped_custom_fields = defaultdict(list)
    for field in active_custom_fields:
        grouped_custom_fields[field['display_section']].append(field)

    try:
        cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
        patient_row = cursor.fetchone()

        if patient_row:
            patient = dict(patient_row) # Convert to dict for easier manipulation
            dob_missing = not patient.get('date_of_birth')

            # Add patient_history_text if present in DB, or try to parse from raw_dossier_text as fallback
            if 'patient_history_text' not in patient or not patient['patient_history_text']:
                # Try to parse from raw_dossier_text if available
                raw_text = patient.get('raw_dossier_text') or ''
                # Simple heuristic: extract lines that look like history fields
                history_lines = []
                for line in raw_text.splitlines():
                    l = line.lower()
                    if (
                        'pmh:' in l or 'psh:' in l or 'past medical history' in l or 'past surgical history' in l or
                        l.startswith('meds:') or l.startswith('medications:') or
                        'allergies:' in l or 'allergy:' in l or l.startswith('allerg') or 'nkda' in l or
                        'smoker' in l or 'smoking' in l or 'alcohol' in l or 'drinker' in l or 'drinking' in l or
                        'fh:' in l or 'family history:' in l or l.startswith('tel:') or l.startswith('phone:')
                    ):
                        history_lines.append(line)
                patient['patient_history_text'] = '\n'.join(history_lines).strip() if history_lines else None

            visits_cursor = db.execute("SELECT * FROM Visits WHERE patient_id = ? ORDER BY visit_date DESC", (patient_id,))
            visits_raw = visits_cursor.fetchall()
            
            for visit_row in visits_raw:
                visit_dict = dict(visit_row)
                # Calculate age at visit
                if patient.get('date_of_birth') and visit_dict.get('visit_date'):
                    visit_dict['age_at_visit'] = calculate_age_at_visit(patient['date_of_birth'], visit_dict['visit_date'])
                else:
                    visit_dict['age_at_visit'] = "N/A"
                # Parse vital_signs JSON
                if visit_dict.get('vital_signs'):
                    try:
                        visit_dict['vital_signs'] = json.loads(visit_dict['vital_signs'])
                    except Exception:
                        visit_dict['vital_signs'] = {}
                else:
                    visit_dict['vital_signs'] = {}
                # Fetch addenda for this visit
                addenda_cursor = db.execute("SELECT * FROM VisitAddenda WHERE visit_id = ? ORDER BY addendum_datetime ASC", (visit_dict['id'],))
                visit_dict['addenda'] = [dict(add_row) for add_row in addenda_cursor.fetchall()]
                # Fetch media for this visit
                media_cursor = db.execute("SELECT * FROM VisitMedia WHERE visit_id = ? ORDER BY upload_date DESC", (visit_dict['id'],))
                visit_dict['media'] = [dict(media_row) for media_row in media_cursor.fetchall()]
                visits_with_addenda.append(visit_dict)
        else:
            flash(f'Patient with ID {patient_id} not found.', 'warning')
            return redirect(url_for('patient.list_patients'))

    except sqlite3.Error as e:
        flash(f"Database error fetching patient detail for id {patient_id}: {e}", 'danger')
        return redirect(url_for('patient.list_patients'))
    except Exception as e:
        flash(f"An unexpected error occurred while fetching patient details for id {patient_id}: {e}", 'danger')
        current_app.logger.error(f"Unexpected error in patient_detail for patient {patient_id}: {e}", exc_info=True)
        return redirect(url_for('patient.list_patients'))

    return render_template('patient_detail.html', 
                           title=f"Patient Details - {patient['first_name'] if patient and patient['first_name'] else 'N/A'} {patient['last_name'] if patient and patient['last_name'] else ''}", 
                           patient=patient, 
                           visits=visits_with_addenda,
                           dob_missing=dob_missing, # Pass dob_missing to template
                           # today_date=today_date, # Removed as it's not used for this context
                           grouped_custom_fields=dict(grouped_custom_fields))

@patient_bp.route('/<int:patient_id>/edit_demographics', methods=['GET', 'POST'])
def edit_demographics(patient_id):
    db = get_db()
    patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
    patient = patient_cursor.fetchone()

    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for('patient.list_patients'))

    custom_fields_metadata = get_active_custom_demographic_fields()

    if request.method == 'POST':
        updates = {}
        sql_params_dict = {}

        for field_key, field_label in EDITABLE_DEMOGRAPHIC_FIELDS.items():
            form_value = request.form.get(field_key)
            if field_key.endswith('_date') and form_value == '':
                updates[field_key] = None
            elif form_value is not None:
                updates[field_key] = form_value.strip() if isinstance(form_value, str) else form_value
        
        for field_meta in custom_fields_metadata:
            field_name = field_meta['field_name']
            if field_name in request.form:
                form_value = request.form.get(field_name)
                if field_meta['field_type'] == 'DATE' and form_value == '':
                     updates[field_name] = None
                elif form_value is not None:
                    updates[field_name] = form_value.strip() if isinstance(form_value, str) else form_value

        if not updates.get('last_name') or not updates.get('first_name'):
            flash('Last Name and First Name are required.', 'danger')
            return render_template('edit_patient_demographics.html', 
                                   patient=patient, 
                                   editable_fields=EDITABLE_DEMOGRAPHIC_FIELDS, 
                                   custom_fields_metadata=custom_fields_metadata,
                                   current_values=updates, 
                                   title="Edit Demographics")
        
        set_clauses = []
        for key, value in updates.items():
            if key in EDITABLE_DEMOGRAPHIC_FIELDS or any(field['field_name'] == key for field in custom_fields_metadata):
                set_clauses.append(f"{key} = :{key}")
                sql_params_dict[key] = value
            else:
                print(f"Warning: Attempted to update non-whitelisted field '{key}'. Skipping.")
        
        if not set_clauses:
            flash('No valid fields to update were provided.', 'warning')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        sql_params_dict['patient_id'] = patient_id
        update_sql = f"UPDATE Patients SET { ', '.join(set_clauses) } WHERE id = :patient_id"

        try:
            db.execute(update_sql, sql_params_dict)
            db.commit()
            # Update Word document
            config = load_config()
            word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
            word_manager.create_or_update_document(patient_id)
            flash('Patient demographics updated successfully!', 'success')
        except sqlite3.Error as e:
            db.rollback()
            flash(f'Database error updating demographics: {e}', 'danger')
        
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    patient_data = dict(patient)
    return render_template('edit_patient_demographics.html',
                           title=f"Edit Demographics for {patient['first_name']} {patient['last_name']}",
                           patient=patient_data,
                           patient_id=patient_id,
                           editable_fields=EDITABLE_DEMOGRAPHIC_FIELDS,
                           custom_fields_metadata=custom_fields_metadata)

@patient_bp.route('/new', methods=['GET'])
def add_patient_form():
    return render_template('add_patient.html', title='Add New Patient')

@patient_bp.route('/add', methods=['POST'])
def add_patient_submit():
    db = get_db()
    new_mrn = ""
    try:
        cursor = db.execute("SELECT MAX(CAST(mrn AS INTEGER)) FROM Patients")
        max_mrn_val = cursor.fetchone()[0]
        new_mrn_int = 1 if max_mrn_val is None else int(max_mrn_val) + 1
        new_mrn = str(new_mrn_int).zfill(5)

        form_data = {
            'mrn': new_mrn,
            'first_name': request.form.get('first_name'),
            'last_name': request.form.get('last_name'),
            'date_of_birth': request.form.get('date_of_birth') or None,
            'sex': request.form.get('sex') or None,
            'phone': request.form.get('phone') or None,
            'address': request.form.get('address') or None,
            'email': request.form.get('email') or None,
            'insurance': request.form.get('insurance') or None,
            'primary_physician': request.form.get('primary_physician') or None,
            'pmh': request.form.get('pmh') or None,
            'psh': request.form.get('psh') or None,
            'medications': request.form.get('medications') or None,
            'allergies': request.form.get('allergies') or None,
            'smoker': request.form.get('smoker') == 'true',
            'smoker_details': request.form.get('smoker_details') or None,
            'alcohol': request.form.get('alcohol') == 'true',
            'alcohol_details': request.form.get('alcohol_details') or None,
            'raw_dossier_text': request.form.get('raw_dossier_text') or None
        }

        if not form_data['last_name'] or not form_data['first_name']:
            flash('First name and Last name are required.', 'danger')
            return redirect(url_for('patient.add_patient_form'))

        # Use DatabaseOperations to create the patient and Word document
        from database_operations import DatabaseOperations
        
        config = load_config()
        db_ops = DatabaseOperations(
            db_path=config['database_path'],
            documents_folder=config['word_docs_folder']
        )
        
        # Create patient and Word document
        patient_id, doc_path = db_ops.create_patient(form_data)
        
        # Update Word document
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        
        flash(f"Patient {form_data['first_name']} {form_data['last_name']} (MRN: {new_mrn}) added successfully!", 'success')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    except sqlite3.Error as e:
        db.rollback()
        flash(f"Database error: {e}", 'danger')
        return redirect(url_for('patient.add_patient_form'))
    except Exception as e:
        db.rollback()
        flash(f"An unexpected error occurred: {e}", 'danger')
        return redirect(url_for('patient.add_patient_form'))

@patient_bp.route('/<int:patient_id>/visit/add', methods=['POST'])
def add_visit(patient_id):
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
        # New adult vital fields
        weight_kg = request.form.get('weight_kg')
        bp = request.form.get('bp')
        temperature = request.form.get('temperature')
        hr = request.form.get('hr')
        chief_complaint = request.form.get('chief_complaint', '').strip()
        subjective = request.form.get('subjective', '').strip()
        objective = request.form.get('objective', '').strip()
        assessment = request.form.get('assessment', '').strip()
        plan = request.form.get('plan', '').strip()
        notes = request.form.get('visit_notes', '').strip()

        if not visit_date_str or not notes:
            flash('Visit date and notes are required.', 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        visit_date_iso = visit_date_str

        try:
            visit_date_obj = datetime.strptime(visit_date_iso, '%Y-%m-%d')
            formatted_date_for_raw = visit_date_obj.strftime('%d-%m-%y')
        except ValueError:
            flash('Invalid visit date format submitted.', 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        if patient_birth_date and visit_date_obj.date() < patient_birth_date:
            flash(f"Error: New visit date ({visit_date_str}) cannot be before the patient's birth date ({patient_birth_date.strftime('%Y-%m-%d')}).", 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # Build the vital_signs JSON
        vital_signs = {
            'weight_kg': float(weight_kg) if weight_kg else None,
            'bp': bp if bp else None,
            'temperature': float(temperature) if temperature else None,
            'hr': int(hr) if hr else None
        }
        vital_signs = {k: v for k, v in vital_signs.items() if v is not None}
        vital_signs_json = json.dumps(vital_signs)

        # Compose a readable string for raw_visit_entry
        vs_parts = []
        if weight_kg: vs_parts.append(f"Weight: {weight_kg} kg")
        if bp: vs_parts.append(f"BP: {bp}")
        if temperature: vs_parts.append(f"Temp: {temperature}°C")
        if hr: vs_parts.append(f"HR: {hr}")
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
            (patient_id, visit_date, vital_signs, chief_complaint, subjective, objective, assessment, plan, notes, raw_visit_entry) \
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        db.execute(sql_insert_visit, (
            patient_id, visit_date_iso, vital_signs_json, chief_complaint, subjective, 
            objective, assessment, plan, notes, raw_visit_entry
        ))
        
        patient_cursor = db.execute("SELECT raw_dossier_text FROM Patients WHERE id = ?", (patient_id,))
        patient_data = patient_cursor.fetchone()
        current_dossier_text = patient_data['raw_dossier_text'] if patient_data['raw_dossier_text'] else ''
        updated_dossier_text = (current_dossier_text + '\n' if current_dossier_text and not current_dossier_text.endswith('\n') else current_dossier_text) + raw_visit_entry
        db.execute("UPDATE Patients SET raw_dossier_text = ? WHERE id = ?", (updated_dossier_text, patient_id))
        
        db.commit()
        # Update Word document after adding visit
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
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

@patient_bp.route('/visit/<int:visit_id>/addendum', methods=['POST'])
def add_visit_addendum(visit_id):
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
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
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
        visit_check_cursor = db.execute("SELECT patient_id FROM Visits WHERE id = ?", (visit_id,))
        visit_check = visit_check_cursor.fetchone()
        if visit_check:
            return redirect(url_for('patient.patient_detail', patient_id=visit_check['patient_id']))
        return redirect(url_for('patient.list_patients'))

@patient_bp.route('/<int:patient_id>/edit_history', methods=['GET', 'POST'])
def edit_patient_history(patient_id):
    db = get_db()
    patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
    patient = patient_cursor.fetchone()
    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for('patient.list_patients'))

    patient = dict(patient)
    # Prepare current values for all history fields
    history_fields = {
        'pmh': patient.get('pmh', ''),
        'psh': patient.get('psh', ''),
        'family_history': patient.get('family_history', ''),
        'medications': patient.get('medications', ''),
        'allergies': patient.get('allergies', ''),
        'smoker': patient.get('smoker', ''),
        'smoker_details': patient.get('smoker_details', ''),
        'alcohol': patient.get('alcohol', ''),
        'alcohol_details': patient.get('alcohol_details', ''),
    }

    if request.method == 'POST':
        updates = {}
        for field in history_fields.keys():
            value = request.form.get(field, '').strip()
            if field in ['smoker', 'alcohol']:
                # Checkbox or select: treat 'on'/'true' as True, else False
                updates[field] = value.lower() in ['1', 'true', 'on', 'yes']
            else:
                updates[field] = value
        set_clause = ', '.join([f"{field} = :{field}" for field in updates.keys()])
        updates['patient_id'] = patient_id
        db.execute(f"UPDATE Patients SET {set_clause} WHERE id = :patient_id", updates)
        db.commit()
        # Update Word document after history edit
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        flash('Patient history updated successfully!', 'success')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    return render_template('edit_patient_history.html', patient=patient, patient_id=patient_id, history_fields=history_fields, title="Edit Patient History")

@patient_bp.route('/visit/<int:visit_id>/edit_measurements', methods=['POST'])
def update_visit_measurements(visit_id):
    db = get_db()
    try:
        # Fetch the visit and patient_id
        visit_cursor = db.execute("SELECT patient_id FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        if not visit:
            flash("Visit not found.", "danger")
            return redirect(url_for('patient.list_patients'))
        patient_id = visit['patient_id']

        # Get new measurement values from the form
        weight_kg = request.form.get('weight_kg')
        bp = request.form.get('bp')
        temperature = request.form.get('temperature')
        hr = request.form.get('hr')

        # Build the vital_signs JSON
        vital_signs = {
            'weight_kg': float(weight_kg) if weight_kg else None,
            'bp': bp if bp else None,
            'temperature': float(temperature) if temperature else None,
            'hr': int(hr) if hr else None
        }
        # Remove None values for cleanliness
        vital_signs = {k: v for k, v in vital_signs.items() if v is not None}
        vital_signs_json = json.dumps(vital_signs)

        # Update the visit
        db.execute(
            "UPDATE Visits SET vital_signs = ? WHERE id = ?",
            (vital_signs_json, visit_id)
        )
        db.commit()
        # Update Word document after visit measurements edit
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        flash('Visit measurements updated successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating visit measurements: {e}', 'danger')
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@patient_bp.route('/visit/<int:visit_id>/upload_media', methods=['POST'])
def upload_visit_media(visit_id):
    db = get_db()
    files = request.files.getlist('media_files')
    description = request.form.get('description', '')
    saved_files = []
    visit_media_folder = os.path.join(USER_MEDIA_FOLDER, 'visit_media')
    os.makedirs(visit_media_folder, exist_ok=True)
    for file in files:
        if file and file.filename:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[-1].lower()
            allowed = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp4', 'mov'}
            if ext not in allowed:
                flash(f'File type not allowed: {filename}', 'danger')
                continue
            save_path = os.path.join(visit_media_folder, filename)
            file.save(save_path)
            media_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            db.execute(
                "INSERT INTO VisitMedia (visit_id, filename, media_type, upload_date, description) VALUES (?, ?, ?, datetime('now'), ?)",
                (visit_id, filename, media_type, description)
            )
            saved_files.append(filename)
    db.commit()
    if saved_files:
        flash(f'Uploaded: {", ".join(saved_files)}', 'success')
    return redirect(request.referrer or url_for('patient.patient_detail', patient_id=request.form.get('patient_id')))

@patient_bp.route('/visit/<int:visit_id>/media/<int:media_id>/delete', methods=['POST'])
def delete_visit_media(media_id, visit_id):
    db = get_db()
    # Get filename to delete file from disk
    media_row = db.execute("SELECT filename FROM VisitMedia WHERE id = ?", (media_id,)).fetchone()
    if media_row:
        filename = media_row['filename']
        file_path = os.path.join(USER_MEDIA_FOLDER, 'visit_media', filename)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            flash(f"Error deleting file from disk: {e}", 'danger')
    db.execute("DELETE FROM VisitMedia WHERE id = ?", (media_id,))
    db.commit()
    flash('Media file deleted.', 'success')
    return redirect(request.referrer or url_for('patient.patient_detail', patient_id=visit_id)) 