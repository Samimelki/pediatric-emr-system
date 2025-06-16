"""
Patient Demographics Management Routes

This module handles:
- Patient creation (add new patients)
- Demographics editing 
- Duplicate detection during patient creation
- Custom demographic fields support
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
from database import get_db, get_active_custom_demographic_fields
from unified_database import save_patient_unified
from emr_config import emr_config
from word_document_manager import WordDocumentManager
from utils.form_validators import parse_user_date_input

# Blueprint configuration
demographics_bp = Blueprint('demographics', __name__, url_prefix='/patient')

# Whitelist of editable standard demographic fields (using French field names like foxpro2025)
EDITABLE_DEMOGRAPHIC_FIELDS = {
    'mrn': 'MRN',
    'nom': 'Last Name (Nom)',
    'prenom': 'First Name (Prénom)',
    'naissance_date': 'Date of Birth (YYYY-MM-DD)',
    'sexe': 'Sex (M/F/Other)',
    'mere_nom': "Mother's Name (Nom de la mère)",
    'pere_nom': "Father's Name (Nom du père)",
    'pediatre_initiales': 'Pediatrician Initials (Initiales du pédiatre)',
    'domicile': 'Address (Domicile)',
    'telephone': 'Telephone',
    'third_party_payer': 'Third Party Payer (Tiers Payant/CAT)',
    'hopital': 'Birth Hospital/Country (Hôpital/Pays de naissance)',
    'diag1': 'Diagnosis 1 (Diagnostic 1)',
    'diag2': 'Diagnosis 2 (Diagnostic 2)',
    'obstetrical_history': 'Obstetrical History (Antécédents Obstétricaux)'
}


@demographics_bp.route('/<int:patient_id>/edit_demographics', methods=['GET', 'POST'])
def edit_demographics(patient_id):
    """Edit patient demographics and custom fields"""
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

        # Process standard demographic fields
        for field_key, field_label in EDITABLE_DEMOGRAPHIC_FIELDS.items():
            form_value = request.form.get(field_key)
            if field_key.endswith('_date') and form_value == '':
                updates[field_key] = None
            elif form_value is not None:
                updates[field_key] = form_value.strip() if isinstance(form_value, str) else form_value
        
        # Process custom demographic fields
        for field_meta in custom_fields_metadata:
            field_name = field_meta['field_name']
            if field_name in request.form:
                form_value = request.form.get(field_name)
                if field_meta['field_type'] == 'DATE' and form_value == '':
                     updates[field_name] = None
                elif form_value is not None:
                    updates[field_name] = form_value.strip() if isinstance(form_value, str) else form_value

        # Handle dual name fields - update both French and English versions
        if 'nom' in updates:
            updates['last_name'] = updates['nom']
        if 'prenom' in updates:
            updates['first_name'] = updates['prenom']
        
        # Handle dual date fields
        if 'naissance_date' in updates:
            updates['date_of_birth'] = updates['naissance_date']
        
        # Handle dual sex fields
        if 'sexe' in updates:
            updates['sex'] = updates['sexe']
            
        # Handle dual contact fields
        if 'telephone' in updates:
            updates['phone'] = updates['telephone']
        if 'domicile' in updates:
            updates['address'] = updates['domicile']

        # Validate required fields
        if not updates.get('nom') or not updates.get('prenom'):
            flash('Last Name and First Name are required.', 'danger')
            return render_template('edit_patient_demographics.html', 
                                   patient=patient, 
                                   editable_fields=EDITABLE_DEMOGRAPHIC_FIELDS, 
                                   custom_fields_metadata=custom_fields_metadata,
                                   current_values=updates, 
                                   title="Edit Demographics")
        
        # Build SQL update statement - include both French and English fields
        all_updatable_fields = list(EDITABLE_DEMOGRAPHIC_FIELDS.keys()) + ['first_name', 'last_name', 'date_of_birth', 'sex', 'phone', 'address']
        set_clauses = []
        for key, value in updates.items():
            if key in all_updatable_fields or any(field['field_name'] == key for field in custom_fields_metadata):
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
            word_manager = WordDocumentManager(
                db_path=emr_config.get_database_path(), 
                documents_folder=emr_config.get_word_docs_folder()
            )
            word_manager.create_or_update_document(patient_id)
            
            flash('Patient demographics updated successfully!', 'success')
        except sqlite3.Error as e:
            db.rollback()
            flash(f'Database error updating demographics: {e}', 'danger')
        
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    # GET request - display the form
    patient_data = dict(patient)
    
    # Ensure French fields are populated from English fields if missing
    if not patient_data.get('prenom') and patient_data.get('first_name'):
        patient_data['prenom'] = patient_data['first_name']
    if not patient_data.get('nom') and patient_data.get('last_name'):
        patient_data['nom'] = patient_data['last_name']
    if not patient_data.get('naissance_date') and patient_data.get('date_of_birth'):
        patient_data['naissance_date'] = patient_data['date_of_birth']
    if not patient_data.get('sexe') and patient_data.get('sex'):
        patient_data['sexe'] = patient_data['sex']
    if not patient_data.get('telephone') and patient_data.get('phone'):
        patient_data['telephone'] = patient_data['phone']
    if not patient_data.get('domicile') and patient_data.get('address'):
        patient_data['domicile'] = patient_data['address']
    
    return render_template('edit_patient_demographics.html',
                           title=f"Edit Demographics for {patient_data.get('prenom') or patient_data.get('first_name') or 'Unknown'} {patient_data.get('nom') or patient_data.get('last_name') or 'Unknown'}",
                           patient=patient_data,
                           patient_id=patient_id,
                           editable_fields=EDITABLE_DEMOGRAPHIC_FIELDS,
                           custom_fields_metadata=custom_fields_metadata)


@demographics_bp.route('/new', methods=['GET'])
def add_patient_form():
    """Display form to add new patient"""
    # Get current EMR configuration using profile system
    enabled_features = emr_config.get_enabled_features()
    
    # Create compatibility object for template
    emr_features = type('EMRFeatures', (), {
        'vaccines_enabled': 'vaccines' in enabled_features,
        'birth_measurements_enabled': 'birth_measurements' in enabled_features,
        'growth_charts_enabled': 'growth_charts' in enabled_features,
        'parental_info_enabled': 'parental_info' in enabled_features,
        'blood_pressure_enabled': 'blood_pressure' in enabled_features,
    })()
    
    # Get custom fields
    custom_fields = get_active_custom_demographic_fields()
    
    return render_template('unified_add_patient.html', 
                         title='Add New Patient',
                         emr_features=emr_features,
                         custom_fields=custom_fields)


@demographics_bp.route('/add', methods=['POST'])
def add_patient_submit():
    """Process new patient submission with duplicate detection"""
    db = get_db()
    new_mrn = ""
    
    try:
        # Generate new MRN
        cursor = db.execute("SELECT MAX(CAST(mrn AS INTEGER)) FROM Patients")
        max_mrn_val = cursor.fetchone()[0]
        new_mrn_int = 1 if max_mrn_val is None else int(max_mrn_val) + 1
        new_mrn = str(new_mrn_int).zfill(5)

        # Build form data with unified field mapping using profile system
        form_data = {
            'mrn': new_mrn,
            'created_date': datetime.now().isoformat(),
            'modified_date': datetime.now().isoformat(),
            'raw_dossier_text': request.form.get('raw_dossier_text') or None,  # For XML import compatibility
            'notes': request.form.get('notes') or None  # General notes field
        }
        
        # Core demographic fields - accept both French and English field names
        # Get names from either French or English form fields
        prenom = request.form.get('prenom') or request.form.get('first_name')
        nom = request.form.get('nom') or request.form.get('last_name')
        
        form_data.update({
            'prenom': prenom,
            'nom': nom,
            'first_name': prenom,  # Store both formats for compatibility
            'last_name': nom,
            # Date fields - accept both formats
            'naissance_date': request.form.get('naissance_date') or request.form.get('date_of_birth') or None,
            'date_of_birth': request.form.get('date_of_birth') or request.form.get('naissance_date') or None,
            # Sex fields - accept both formats
            'sexe': request.form.get('sexe') or request.form.get('sex') or None,
            'sex': request.form.get('sex') or request.form.get('sexe') or None,
            # Phone fields - accept both formats
            'telephone': request.form.get('telephone') or request.form.get('phone') or None,
            'phone': request.form.get('phone') or request.form.get('telephone') or None,
            # Address fields - accept both formats
            'domicile': request.form.get('domicile') or request.form.get('address') or None,
            'address': request.form.get('address') or request.form.get('domicile') or None,
            'email': request.form.get('email') or None
        })
        
        # Validate required fields
        if not nom or not prenom:
            flash('First name and Last name are required.', 'danger')
            return redirect(url_for('demographics.add_patient_form'))
        
        # Extract parent names early for duplicate checking
        mother_name = request.form.get('mere_nom', '').strip()
        father_name = request.form.get('pere_nom', '').strip()
        
        # Check for override parameter (if user confirmed to proceed despite duplicate)
        force_create = request.form.get('force_create') == 'true' or request.args.get('force') == 'true'
        
        # Check for duplicate patients (same name and DOB)
        duplicate_check_db = get_db()
        birth_date_for_check = form_data.get('date_of_birth') or form_data.get('naissance_date')
        if birth_date_for_check and not force_create:
            # Standardize date format to YYYY-MM-DD using extracted utility
            date_result = parse_user_date_input(birth_date_for_check, "birth date")
            if not date_result['success']:
                flash(date_result['error_message'], 'danger')
                return redirect(url_for('demographics.add_patient_form'))
            
            standardized_birth_date = date_result['iso_date']
            # Update both date fields with standardized format
            form_data['date_of_birth'] = standardized_birth_date
            form_data['naissance_date'] = standardized_birth_date
                
            if standardized_birth_date:
                duplicate_query = """
                SELECT id, prenom, nom, first_name, last_name, mere_nom, pere_nom, mrn 
                FROM Patients 
                WHERE (
                    (LOWER(COALESCE(prenom, first_name, '')) = LOWER(?) OR 
                     LOWER(COALESCE(first_name, prenom, '')) = LOWER(?)) AND 
                    (LOWER(COALESCE(nom, last_name, '')) = LOWER(?) OR 
                     LOWER(COALESCE(last_name, nom, '')) = LOWER(?)) AND
                    (date_of_birth = ? OR naissance_date = ?)
                )
                """
                duplicates = duplicate_check_db.execute(duplicate_query, (
                    prenom, prenom, nom, nom, standardized_birth_date, standardized_birth_date
                )).fetchall()
                
                if duplicates:
                    # Check if parent names differ to confirm it's truly a different patient
                    confirmed_duplicate = False
                    duplicate_info = None
                    
                    for dup in duplicates:
                        existing_mother = (dup['mere_nom'] or '').strip()
                        existing_father = (dup['pere_nom'] or '').strip()
                        
                        # Check if we can distinguish based on parent names
                        parent_names_differ = False
                        
                        # Debug: Print the parent name comparison
                        print(f"DEBUG: Comparing parent names:")
                        print(f"  New: Mother='{mother_name}', Father='{father_name}'")
                        print(f"  Existing: Mother='{existing_mother}', Father='{existing_father}'")
                        print(f"  Mother name check: new='{mother_name}' existing='{existing_mother}' both_present={bool(mother_name and existing_mother)} different={mother_name.lower() != existing_mother.lower() if mother_name and existing_mother else 'N/A'}")
                        print(f"  Father name check: new='{father_name}' existing='{existing_father}' both_present={bool(father_name and existing_father)} different={father_name.lower() != existing_father.lower() if father_name and existing_father else 'N/A'}")
                        
                        # If we have mother names for both, and they differ
                        if mother_name and existing_mother and mother_name.lower() != existing_mother.lower():
                            parent_names_differ = True
                            print(f"  -> Mother names differ: '{mother_name}' != '{existing_mother}'")
                        
                        # If we have father names for both, and they differ
                        if father_name and existing_father and father_name.lower() != existing_father.lower():
                            parent_names_differ = True
                            print(f"  -> Father names differ: '{father_name}' != '{existing_father}'")
                        
                        print(f"  -> parent_names_differ = {parent_names_differ}")
                        
                        # If parent names clearly differ, this is likely a sibling, not a duplicate
                        if parent_names_differ:
                            continue  # Skip this one, it's probably a different patient
                        
                        # If we get here, we either have matching parent names or missing parent info
                        # This could be a real duplicate
                        confirmed_duplicate = True
                        duplicate_info = dup
                        break  # Found a potential duplicate
                    
                    if confirmed_duplicate and duplicate_info:
                        existing_first = duplicate_info['prenom'] or duplicate_info['first_name'] or 'Unknown'
                        existing_last = duplicate_info['nom'] or duplicate_info['last_name'] or 'Unknown'
                        existing_name = f"{existing_first} {existing_last}"
                        existing_mother = (duplicate_info['mere_nom'] or '').strip()
                        existing_father = (duplicate_info['pere_nom'] or '').strip()
                        
                        # Create detailed warning message and preserve form data
                        warning_msg = f"""⚠️ Potential duplicate patient detected! 
A patient with the same name "{existing_name}" and birth date "{standardized_birth_date}" already exists (MRN: {duplicate_info["mrn"]}).

COMPARISON:
New patient: Mother="{mother_name or 'Not provided'}", Father="{father_name or 'Not provided'}"
Existing patient: Mother="{existing_mother or 'Not provided'}", Father="{existing_father or 'Not provided'}"

If this is a different patient (sibling), click "Add Anyway" below."""
                        
                        flash(warning_msg, 'warning')
                        
                        # Preserve all form data for re-display
                        form_data_preserved = dict(request.form)
                        
                        # Get current EMR configuration
                        custom_fields = get_active_custom_demographic_fields()
                        user_date_format = emr_config.get_date_format()
                        
                        return render_template('unified_add_patient.html',
                                             custom_fields=custom_fields,
                                             date_format=user_date_format,
                                             form_data=form_data_preserved,
                                             show_duplicate_override=True,
                                             duplicate_detected=True)
        
        # Core demographic fields - always collected
        form_data.update({
            'middle_name': request.form.get('middle_name') or None,
            'mere_nom': request.form.get('mere_nom') or None,
            'pere_nom': request.form.get('pere_nom') or None,
            'notes': request.form.get('notes') or None
        })
        
        # Keep legacy fields for XML import compatibility
        form_data.update({
            'diag1': request.form.get('diag1') or None,  # For XML import compatibility
            'diag2': request.form.get('diag2') or None,  # For XML import compatibility
            'third_party_payer': request.form.get('third_party_payer') or None,
            'pediatre_initiales': request.form.get('pediatre_initiales') or None,
            'birth_weight_g': request.form.get('birth_weight_g') or None,
            'birth_height_cm': request.form.get('birth_height_cm') or None,
            'birth_head_circumference_cm': request.form.get('birth_head_circumference_cm') or None,
            'birth_notes': request.form.get('birth_notes') or None,
            'obstetrical_history': request.form.get('obstetrical_history') or None,
            'hopital': request.form.get('hopital') or None,
            'insurance': request.form.get('insurance') or None,
            'primary_physician': request.form.get('primary_physician') or None,
            'pmh': request.form.get('pmh') or None,
            'psh': request.form.get('psh') or None,
            'family_history': request.form.get('family_history') or None,
            'medications': request.form.get('medications') or None,
            'allergies': request.form.get('allergies') or None,
            'smoker': 1 if request.form.get('smoker') else 0,
            'smoker_details': request.form.get('smoker_details') or None,
            'alcohol': 1 if request.form.get('alcohol') else 0,
            'alcohol_details': request.form.get('alcohol_details') or None
        })
        
        # Vaccine fields for XML import compatibility
        if emr_config.is_feature_enabled('vaccines'):
            vaccine_fields = [
                'dtcp1_date', 'dtcp2_date', 'dtcp3_date',
                'dtcp_rappel1_date', 'dtcp_rappel2_date', 'dtcp_rappel3_date', 'dtcp_rappel4_date',
                'hep_b1_date', 'hep_b2_date', 'hep_b3_date',
                'hib1_date', 'hib2_date', 'hib3_date', 'hib_rappel_date',
                'ror_date', 'rougeole_seule_date',
                'monotest1', 'monotest2', 'monotest3',
                'raw_autres_vaccins_text'
            ]
            for field in vaccine_fields:
                form_data[field] = request.form.get(field) or None
        
        # Custom demographic fields
        custom_fields = get_active_custom_demographic_fields()
        for field in custom_fields:
            field_value = request.form.get(field['field_name'])
            if field_value:
                form_data[field['field_name']] = field_value

        # Use unified database system to create the patient
        patient_id = save_patient_unified(form_data)
        
        # Create document in the selected format
        document_format = request.form.get('document_format', 'md')  # Default to markdown
        word_manager = WordDocumentManager(
            db_path=emr_config.get_database_path(), 
            documents_folder=emr_config.get_word_docs_folder()
        )
        word_manager.create_or_update_document(patient_id, format_type=document_format)
        
        # Create success message using the captured name values
        name = f"{prenom} {nom}"
        format_name = "Word document" if document_format == 'docx' else "Markdown document"
        flash(f"Patient {name} (MRN: {new_mrn}) added successfully! {format_name} created.", 'success')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    except sqlite3.Error as e:
        db.rollback()
        flash(f"Database error: {e}", 'danger')
        return redirect(url_for('demographics.add_patient_form'))
    except Exception as e:
        db.rollback()
        flash(f"An unexpected error occurred: {e}", 'danger')
        return redirect(url_for('demographics.add_patient_form')) 