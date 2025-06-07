from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import sqlite3
import math
from datetime import datetime, date
from collections import defaultdict
from database import get_db, get_active_custom_demographic_fields
from unified_database import get_patient_unified_data, save_patient_unified, get_visit_unified_data
from emr_config import emr_config, EMRMode
from dateutil.relativedelta import relativedelta
import json
from config_manager import load_config, USER_MEDIA_FOLDER
from word_document_manager import WordDocumentManager
from werkzeug.utils import secure_filename
import mimetypes
import os
from who_data_loader import who_loader

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

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

# Configuration
PER_PAGE = 50

def convert_weight_to_kg(weight_raw):
    """
    Convert weight value to kg according to the storage format rules:
    - 2 digits (10-99): Already in kg, display as-is
    - 500-9999: In grams, divide by 1000 to display as kg
    - 10000+: Would be stored as kg value (e.g., 10 for 10kg), display as-is
    """
    if weight_raw is None:
        return None
    
    try:
        weight_val = float(weight_raw)
        
        # 2 digits (10-99): already in kg
        if 10 <= weight_val <= 99:
            return weight_val
        
        # 500-9999: stored in grams, convert to kg
        elif 500 <= weight_val <= 9999:
            return weight_val / 1000.0
        
        # 10000+: this shouldn't happen as per user, but if it does, treat as kg
        elif weight_val >= 10000:
            return weight_val / 1000.0
        
        # Less than 10: assume kg (edge case)
        else:
            return weight_val
            
    except (ValueError, TypeError):
        return None

def convert_kg_to_storage_format(weight_kg):
    """
    Convert weight from kg input to storage format according to rules:
    - If weight is very low (likely infant/baby): store in grams (multiply by 1000)
    - If weight is normal child/adult range: store as kg (2 digits)
    """
    if weight_kg is None:
        return None
    
    try:
        weight_kg_val = float(weight_kg)
        
        # For very small weights (newborns/infants), store in grams
        if weight_kg_val < 10:
            return int(weight_kg_val * 1000)
        
        # For normal weights (children/adults), keep as kg but ensure integer if possible
        else:
            return int(weight_kg_val) if weight_kg_val == int(weight_kg_val) else weight_kg_val
            
    except (ValueError, TypeError):
        return None

# --- HELPER FUNCTION FOR EMR VACCINE DATA PREPARATION ---
def _prepare_vaccine_data_for_emr(patient_data_row, autres_vaccins_query_results, patient_id_for_urls):
    """Prepare vaccine data for EMR display (adapted from foxpro2025)"""
    from routes.pdf_export_routes import (
        PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN,
        VACCINE_ALIAS_MAP_EN,
        ALL_POSSIBLE_DOSE_KEYS
    )
    
    all_vaccine_data_by_display_name = defaultdict(lambda: {
        'dose_dates': {},
        'edit_urls': {},
        'canonical_name_for_check': '', 
        'sort_key_brand': '' # For secondary sort: brand name or empty string
    })

    # 1. Process defined patient fields (Standard Vaccines)
    for canonical_name, patient_field_key, dose_key in PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN:
        # Handle both dict and Row objects
        try:
            if hasattr(patient_data_row, 'keys'):
                # It's a Row object
                date_val = patient_data_row[patient_field_key] if patient_field_key in patient_data_row.keys() else None
            else:
                # It's a dict or dict-like
                date_val = patient_data_row.get(patient_field_key) if patient_data_row else None
        except (KeyError, TypeError):
            date_val = None
            
        display_name = canonical_name # Standard vaccines usually don't have a separate brand name in this context
        
        if date_val: # Only process if there's a date
            data_entry = all_vaccine_data_by_display_name[display_name]
            data_entry['dose_dates'][dose_key] = date_val
            data_entry['edit_urls'][dose_key] = url_for('patient.edit_standard_vaccine_form', patient_id=patient_id_for_urls, field_name=patient_field_key)
            data_entry['canonical_name_for_check'] = canonical_name # Store the base canonical name for mandatory check
            # 'sort_key_brand' remains empty for these as display_name is canonical

    # 2. Process non-standard vaccine entries ("autres_vaccins")
    # These are often brand names, try to map to canonical and format as "Canonical (Brand)"
    dose_keys_for_filling = ALL_POSSIBLE_DOSE_KEYS # Use the global list for filling order

    for v_row in autres_vaccins_query_results:
        original_brand_name = v_row['vaccine_name']
        date_val = v_row['vaccine_date']
        original_edit_url = url_for('patient.edit_other_vaccine_form', vaccine_id=v_row['id'])

        if not date_val: # Skip if no date
            continue

        # Try to find a canonical name using the alias map (case-insensitive key check)
        canonical_name_from_alias = None
        for alias_key, mapped_canonical in VACCINE_ALIAS_MAP_EN.items():
            if alias_key.upper() == original_brand_name.upper():
                canonical_name_from_alias = mapped_canonical
                break
        
        final_canonical_name = canonical_name_from_alias if canonical_name_from_alias else original_brand_name
        sort_key_brand_val = ''

        if canonical_name_from_alias and canonical_name_from_alias.upper() != original_brand_name.upper():
            # We found an alias, and it's different from the original name (implying original was a brand)
            display_name = f"{final_canonical_name} ({original_brand_name})"
            sort_key_brand_val = original_brand_name # For sorting by brand name after canonical
        else:
            # No alias found, or alias is same as original (treat original as canonical or unmapped brand)
            display_name = final_canonical_name
            # If final_canonical_name IS original_brand_name, this might be an unmapped brand or already canonical.
            # If we want to distinguish for sorting, this could be refined.

        data_entry = all_vaccine_data_by_display_name[display_name]
        if not data_entry['canonical_name_for_check']: # Set if not already (e.g. by standard vaccine processing)
             data_entry['canonical_name_for_check'] = final_canonical_name # Important for mandatory check
        if not data_entry['sort_key_brand'] and sort_key_brand_val: # Set sort key if available
            data_entry['sort_key_brand'] = sort_key_brand_val

        # Find first available dose slot to place this non-standard vaccine instance
        assigned_to_slot = False
        for dose_key_to_fill in dose_keys_for_filling:
            if dose_key_to_fill not in data_entry['dose_dates'] or data_entry['dose_dates'][dose_key_to_fill] is None:
                # Check if this specific date is already recorded for this vaccine group from another source (unlikely but safeguard)
                is_duplicate_date_in_group = False
                for existing_dose, existing_date in data_entry['dose_dates'].items():
                    if existing_date == date_val:
                        # Potentially also check edit_urls[existing_dose] to see if it's the same source
                        # For now, if date matches, assume it's a duplicate entry for this group for simplicity
                        is_duplicate_date_in_group = True 
                        break
                if not is_duplicate_date_in_group:
                    data_entry['dose_dates'][dose_key_to_fill] = date_val
                    data_entry['edit_urls'][dose_key_to_fill] = original_edit_url
                    assigned_to_slot = True
                    break
        # If not assigned (e.g. all slots full or duplicate dates), it's currently skipped.
        # This matches PDF logic where additional doses beyond available slots or duplicate dates are not repeatedly shown.

    # 3. Convert to list format for template
    final_table_data = []
    for dn, data_dict in all_vaccine_data_by_display_name.items():
        if data_dict['dose_dates']: # Only include if there are any doses
            final_table_data.append({
                'vaccine_display_name': dn,
                'dose_dates': data_dict['dose_dates'],
                'edit_urls': data_dict['edit_urls'],
                'canonical_name_for_check': data_dict['canonical_name_for_check'],
                'sort_key_brand': data_dict['sort_key_brand']
            })
    
    # Sort: Primary by canonical name part of display name, secondary by brand name part
    final_table_data.sort(key=lambda x: (x['canonical_name_for_check'].lower(), x['sort_key_brand'].lower()))

    return final_table_data

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

    active_custom_fields = get_active_custom_demographic_fields()
    grouped_custom_fields = defaultdict(list)
    for field in active_custom_fields:
        grouped_custom_fields[field['display_section']].append(field)

    try:
        cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
        patient_row = cursor.fetchone()

        if patient_row:
            patient = dict(patient_row) # Convert to dict for easier manipulation
            
            # Use French field names directly - no need for field mapping complexity
            dob_missing = not patient.get('naissance_date')

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
                # Calculate age at visit using French field names
                birth_date_for_age = patient.get('naissance_date')
                if birth_date_for_age and visit_dict.get('visit_date'):
                    visit_dict['age_at_visit'] = calculate_age_at_visit(birth_date_for_age, visit_dict['visit_date'])
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
                
                # For pediatric EMR, add direct measurement fields to vitals if they exist
                if emr_config.get_emr_mode() == EMRMode.PEDIATRIC or emr_config.get_emr_mode() == EMRMode.MIXED:
                    if visit_dict.get('weight_g') and not visit_dict['vital_signs'].get('weight_kg'):
                        visit_dict['vital_signs']['weight_kg'] = convert_weight_to_kg(visit_dict['weight_g'])
                    if visit_dict.get('height_cm') and not visit_dict['vital_signs'].get('height_cm'):
                        visit_dict['vital_signs']['height_cm'] = visit_dict['height_cm']
                    if visit_dict.get('head_circumference_cm') and not visit_dict['vital_signs'].get('head_circumference_cm'):
                        visit_dict['vital_signs']['head_circumference_cm'] = visit_dict['head_circumference_cm']
                        
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

    # Get vaccine data for the patient if vaccines are enabled
    mandatory_vaccines_emr = []
    recommended_vaccines_emr = []
    active_dose_keys_emr = []
    table_column_labels_emr = {}
    
    if emr_config.should_show_vaccines():
        try:
            # Import vaccine constants
            from routes.pdf_export_routes import (
                PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN,
                VACCINE_ALIAS_MAP_EN,
                MANDATORY_CANONICAL_VACCINE_NAMES_EN,
                ALL_POSSIBLE_DOSE_KEYS,
                TABLE_COLUMN_LABELS_EN
            )
            
            print(f"DEBUG: Processing vaccines for patient {patient_id}")
            print(f"DEBUG: Patient data keys: {list(patient.keys())}")
            print(f"DEBUG: Sample vaccine fields: dtcp1_date={patient.get('dtcp1_date')}, hep_b1_date={patient.get('hep_b1_date')}")
            
            # Get other vaccines data
            vaccine_cursor = db.execute("SELECT * FROM NonStandardVaccines WHERE patient_id = ? ORDER BY vaccine_date DESC", (patient_id,))
            autres_vaccins = vaccine_cursor.fetchall()
            print(f"DEBUG: Found {len(autres_vaccins)} non-standard vaccines")
            
            # Prepare vaccine data using the same logic as foxpro2025
            # Pass the patient dict directly - the helper function handles both dict and Row access
            all_vaccines_for_emr_table = _prepare_vaccine_data_for_emr(patient, autres_vaccins, patient_id)
            print(f"DEBUG: Prepared {len(all_vaccines_for_emr_table)} total vaccines for EMR table")
            
            # Separate mandatory and recommended vaccines
            for vaccine_row in all_vaccines_for_emr_table:
                print(f"DEBUG: Vaccine {vaccine_row['vaccine_display_name']} - canonical: {vaccine_row['canonical_name_for_check']}")
                if vaccine_row['canonical_name_for_check'] in MANDATORY_CANONICAL_VACCINE_NAMES_EN:
                    mandatory_vaccines_emr.append(vaccine_row)
                    print(f"DEBUG: Added to mandatory: {vaccine_row['vaccine_display_name']}")
                else:
                    recommended_vaccines_emr.append(vaccine_row)
                    print(f"DEBUG: Added to recommended: {vaccine_row['vaccine_display_name']}")
            
            # Determine active dose keys for EMR table
            for key in ALL_POSSIBLE_DOSE_KEYS:
                if any(vaccine_row['dose_dates'].get(key) for vaccine_row in all_vaccines_for_emr_table):
                    active_dose_keys_emr.append(key)
            
            table_column_labels_emr = TABLE_COLUMN_LABELS_EN
            print(f"DEBUG: Final counts - Mandatory: {len(mandatory_vaccines_emr)}, Recommended: {len(recommended_vaccines_emr)}")
            print(f"DEBUG: Active dose keys: {active_dose_keys_emr}")
            
        except Exception as e:
            current_app.logger.error(f"Error preparing vaccine data for patient {patient_id}: {e}", exc_info=True)
            flash(f"Error loading vaccine data: {str(e)}", 'warning')
            print(f"ERROR preparing vaccine data: {e}")
            import traceback
            traceback.print_exc()

    # Prepare growth chart data for pediatric patients
    visit_ages_in_months = []
    weight_data = []
    height_data = []
    hc_data = []
    who_chart_data = {}
    
    if not dob_missing and patient and visits_with_addenda:
        # Calculate age at each visit in months and extract measurements
        patient_dob = patient.get('naissance_date')
        if patient_dob:
            for visit in visits_with_addenda:
                visit_date = visit.get('visit_date')
                if visit_date and patient_dob:
                    try:
                        # Calculate age in months at visit
                        dob_obj = datetime.strptime(patient_dob, '%Y-%m-%d')
                        visit_obj = datetime.strptime(visit_date, '%Y-%m-%d')
                        age_delta = relativedelta(visit_obj, dob_obj)
                        age_in_months = age_delta.years * 12 + age_delta.months
                        
                        # Get measurements (prioritize direct fields for pediatric data)
                        weight_val = None
                        if visit.get('weight_g'):
                            weight_val = convert_weight_to_kg(visit['weight_g'])
                        elif visit.get('vital_signs', {}).get('weight_kg'):
                            weight_val = visit['vital_signs']['weight_kg']
                            
                        height_val = visit.get('height_cm') or visit.get('vital_signs', {}).get('height_cm')
                        hc_val = visit.get('head_circumference_cm') or visit.get('vital_signs', {}).get('head_circumference_cm')
                        
                        # Only add if we have at least one measurement
                        if weight_val is not None or height_val is not None or hc_val is not None:
                            visit_ages_in_months.append(age_in_months)
                            weight_data.append(weight_val)
                            height_data.append(height_val)
                            hc_data.append(hc_val)
                            
                    except (ValueError, TypeError) as e:
                        print(f"Error calculating age for visit {visit.get('id')}: {e}")
                        continue
        
        # Load WHO standards data if patient sex is available
        patient_sex = patient.get('sexe') or patient.get('sex')
        if patient_sex:
            who_chart_data = who_loader.prepare_chart_data_for_patient(patient_sex)

    return render_template('patient_detail.html', 
                           title=f"Patient Details - {patient['prenom'] if patient and patient['prenom'] else 'N/A'} {patient['nom'] if patient and patient['nom'] else ''}", 
                           patient=patient, 
                           visits=visits_with_addenda,
                           dob_missing=dob_missing, # Pass dob_missing to template
                           mandatory_vaccines_emr=mandatory_vaccines_emr,
                           recommended_vaccines_emr=recommended_vaccines_emr,
                           active_dose_keys_emr=active_dose_keys_emr,
                           table_column_labels_emr=table_column_labels_emr,
                           emr_mode=emr_config.get_emr_mode(),
                           emr_config=emr_config,
                           grouped_custom_fields=dict(grouped_custom_fields),
                           # Growth chart data
                           visit_ages_in_months=visit_ages_in_months,
                           weight_data=weight_data,
                           height_data=height_data,
                           hc_data=hc_data,
                           **who_chart_data)

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

        if not updates.get('nom') or not updates.get('prenom'):
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
    # Get current EMR configuration
    emr_mode = emr_config.get_emr_mode()
    emr_features = emr_config.get_enabled_features()
    
    # Get custom fields for the current mode
    custom_fields = get_active_custom_demographic_fields()
    
    return render_template('unified_add_patient.html', 
                         title='Add New Patient',
                         emr_mode=emr_mode,
                         emr_features=emr_features,
                         custom_fields=custom_fields)

@patient_bp.route('/add', methods=['POST'])
def add_patient_submit():
    db = get_db()
    new_mrn = ""
    try:
        cursor = db.execute("SELECT MAX(CAST(mrn AS INTEGER)) FROM Patients")
        max_mrn_val = cursor.fetchone()[0]
        new_mrn_int = 1 if max_mrn_val is None else int(max_mrn_val) + 1
        new_mrn = str(new_mrn_int).zfill(5)

        # Get current EMR mode to determine field mapping
        emr_mode = emr_config.get_emr_mode()
        
        # Build form data with unified field mapping
        form_data = {
            'mrn': new_mrn,
            'emr_mode': emr_mode.value,
            'created_date': datetime.now().isoformat(),
            'modified_date': datetime.now().isoformat(),
            'raw_dossier_text': request.form.get('raw_dossier_text') or None
        }
        
        # Core demographic fields (adapt based on mode)
        if emr_mode == EMRMode.PEDIATRIC:
            form_data.update({
                'prenom': request.form.get('prenom'),
                'nom': request.form.get('nom'),
                'naissance_date': request.form.get('naissance_date') or None,
                'sexe': request.form.get('sexe') or None,
                'telephone': request.form.get('telephone') or None,
                'domicile': request.form.get('domicile') or None
            })
            # Validate required pediatric fields
            if not form_data['nom'] or not form_data['prenom']:
                flash('Nom et prénom sont obligatoires.', 'danger')
                return redirect(url_for('patient.add_patient_form'))
        else:
            # Adult or mixed mode
            form_data.update({
                'first_name': request.form.get('first_name'),
                'last_name': request.form.get('last_name'),
                'date_of_birth': request.form.get('date_of_birth') or None,
                'sex': request.form.get('sex') or None,
                'phone': request.form.get('phone') or None,
                'address': request.form.get('address') or None,
                'email': request.form.get('email') or None
            })
            # Validate required adult fields
            if not form_data['last_name'] or not form_data['first_name']:
                flash('First name and Last name are required.', 'danger')
                return redirect(url_for('patient.add_patient_form'))
        
        # Adult-specific medical fields
        if emr_mode in [EMRMode.ADULT, EMRMode.MIXED]:
            form_data.update({
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
        
        # Pediatric-specific fields
        if emr_mode in [EMRMode.PEDIATRIC, EMRMode.MIXED]:
            form_data.update({
                'mere_nom': request.form.get('mere_nom') or None,
                'pere_nom': request.form.get('pere_nom') or None,
                'third_party_payer': request.form.get('third_party_payer') or None,
                'pediatre_initiales': request.form.get('pediatre_initiales') or None,
                'birth_weight_g': request.form.get('birth_weight_g') or None,
                'birth_height_cm': request.form.get('birth_height_cm') or None,
                'birth_head_circumference_cm': request.form.get('birth_head_circumference_cm') or None,
                'birth_notes': request.form.get('birth_notes') or None,
                'obstetrical_history': request.form.get('obstetrical_history') or None,
                'hopital': request.form.get('hopital') or None,
                'diag1': request.form.get('diag1') or None,
                'diag2': request.form.get('diag2') or None
            })
            
            # Vaccine fields (if vaccines are enabled)
            if emr_config.get_enabled_features().vaccines_enabled:
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
        patient_id = save_patient_unified(form_data, emr_mode)
        
        # Update Word document
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        
        # Create success message based on mode
        if emr_mode == EMRMode.PEDIATRIC:
            name = f"{form_data.get('prenom', '')} {form_data.get('nom', '')}"
        else:
            name = f"{form_data.get('first_name', '')} {form_data.get('last_name', '')}"
            
        flash(f"Patient {name} (MRN: {new_mrn}) added successfully!", 'success')
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
        # Adult vital fields
        weight_kg = request.form.get('weight_kg')
        bp = request.form.get('bp')
        temperature = request.form.get('temperature')
        hr = request.form.get('hr')
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
            'height_cm': float(height_cm) if height_cm else None,
            'head_circumference_cm': float(head_circumference_cm) if head_circumference_cm else None,
            'bp': bp if bp else None,
            'temperature': float(temperature) if temperature else None,
            'hr': int(hr) if hr else None
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

@patient_bp.route('/visit/<int:visit_id>/edit_measurements', methods=['GET'])
def edit_visit_measurements(visit_id):
    """Display form to edit visit measurements"""
    db = get_db()
    try:
        # Fetch the visit and patient info
        visit_cursor = db.execute("SELECT * FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        if not visit:
            flash("Visit not found.", "danger")
            return redirect(url_for('patient.list_patients'))
        
        patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (visit['patient_id'],))
        patient = patient_cursor.fetchone()
        if not patient:
            flash("Patient not found.", "danger")
            return redirect(url_for('patient.list_patients'))
        
        return render_template('edit_visit_measurements.html',
                             title=f"Edit Measurements - {visit['visit_date']}",
                             visit=dict(visit),
                             patient=dict(patient))
    except Exception as e:
        flash(f'Error loading edit form: {e}', 'danger')
        return redirect(url_for('patient.list_patients'))

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
        weight_g = request.form.get('weight_g')
        height_cm = request.form.get('height_cm')
        head_circumference_cm = request.form.get('head_circumference_cm')
        bp = request.form.get('bp')
        temperature = request.form.get('temperature')
        hr = request.form.get('hr')

        # Convert and prepare values
        weight_g_val = float(weight_g) if weight_g else None
        height_cm_val = float(height_cm) if height_cm else None
        head_circumference_cm_val = float(head_circumference_cm) if head_circumference_cm else None
        
        # Build the vital_signs JSON for compatibility
        vital_signs = {
            'weight_kg': convert_weight_to_kg(weight_g_val) if weight_g_val else None,
            'height_cm': height_cm_val,
            'head_circumference_cm': head_circumference_cm_val,
            'bp': bp if bp else None,
            'temperature': float(temperature) if temperature else None,
            'hr': int(hr) if hr else None
        }
        # Remove None values for cleanliness
        vital_signs = {k: v for k, v in vital_signs.items() if v is not None}
        vital_signs_json = json.dumps(vital_signs)

        # Update the visit with both direct fields and vital_signs JSON
        db.execute(
            "UPDATE Visits SET weight_g = ?, height_cm = ?, head_circumference_cm = ?, vital_signs = ? WHERE id = ?",
            (weight_g_val, height_cm_val, head_circumference_cm_val, vital_signs_json, visit_id)
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

@patient_bp.route('/visit/<int:visit_id>/edit_date', methods=['GET'])
def edit_visit_date(visit_id):
    """Display form to edit visit date"""
    db = get_db()
    try:
        # Fetch the visit and patient info
        visit_cursor = db.execute("""
            SELECT v.*, p.prenom, p.nom, p.mrn, p.naissance_date 
            FROM Visits v 
            JOIN Patients p ON v.patient_id = p.id 
            WHERE v.id = ?
        """, (visit_id,))
        visit = visit_cursor.fetchone()
        if not visit:
            flash("Visit not found.", "danger")
            return redirect(url_for('patient.list_patients'))
        
        # Format current date
        current_date_val = visit['visit_date'].split('T')[0] if visit['visit_date'] else ''
        patient_birth_date_str = visit['naissance_date'] if visit['naissance_date'] else None
        
        return render_template('edit_visit_date.html',
                             title=f"Edit Visit Date",
                             visit=dict(visit),
                             current_date_val=current_date_val,
                             patient_birth_date_str=patient_birth_date_str)
    except Exception as e:
        flash(f'Error loading edit date form: {e}', 'danger')
        return redirect(url_for('patient.list_patients'))

@patient_bp.route('/visit/<int:visit_id>/edit_date', methods=['POST'])
def edit_single_visit_date(visit_id):
    """Update visit date"""
    db = get_db()
    try:
        # Fetch the visit
        visit_cursor = db.execute("SELECT patient_id, visit_date FROM Visits WHERE id = ?", (visit_id,))
        visit = visit_cursor.fetchone()
        if not visit:
            flash("Visit not found.", "danger")
            return redirect(url_for('patient.list_patients'))
        
        patient_id = visit['patient_id']
        new_visit_date = request.form.get('visit_date')
        
        if not new_visit_date:
            flash('Visit date is required.', 'danger')
            return redirect(url_for('patient.edit_visit_date', visit_id=visit_id))
        
        # Validate date format and check against patient DOB
        try:
            visit_date_obj = datetime.strptime(new_visit_date, '%Y-%m-%d')
            
            # Check against patient birth date
            patient_cursor = db.execute("SELECT naissance_date FROM Patients WHERE id = ?", (patient_id,))
            patient_data = patient_cursor.fetchone()
            if patient_data and patient_data['naissance_date']:
                birth_date_obj = datetime.strptime(patient_data['naissance_date'], '%Y-%m-%d')
                if visit_date_obj.date() < birth_date_obj.date():
                    flash(f"Visit date cannot be before patient's birth date ({patient_data['naissance_date']}).", 'danger')
                    return redirect(url_for('patient.edit_visit_date', visit_id=visit_id))
        except ValueError:
            flash('Invalid date format.', 'danger')
            return redirect(url_for('patient.edit_visit_date', visit_id=visit_id))
        
        # Update the visit date
        db.execute("UPDATE Visits SET visit_date = ? WHERE id = ?", (new_visit_date, visit_id))
        db.commit()
        
        # Update Word document
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        
        flash('Visit date updated successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating visit date: {e}', 'danger')
    
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

# Vaccine editing routes
@patient_bp.route('/<int:patient_id>/edit_standard_vaccine/<field_name>')
def edit_standard_vaccine(patient_id, field_name):
    """Edit a standard vaccine field for a patient"""
    db = get_db()
    patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
    patient = patient_cursor.fetchone()
    
    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for('patient.list_patients'))
    
    # Define valid vaccine fields and their labels
    vaccine_fields = {
        'dtcp1_date': 'DTCP Dose 1',
        'dtcp2_date': 'DTCP Dose 2', 
        'dtcp3_date': 'DTCP Dose 3',
        'dtcp_rappel1_date': 'DTCP Booster 1',
        'dtcp_rappel2_date': 'DTCP Booster 2',
        'dtcp_rappel3_date': 'DTCP Booster 3',
        'dtcp_rappel4_date': 'DTCP Booster 4',
        'hep_b1_date': 'Hepatitis B Dose 1',
        'hep_b2_date': 'Hepatitis B Dose 2',
        'hep_b3_date': 'Hepatitis B Dose 3',
        'hib1_date': 'Hib Dose 1',
        'hib2_date': 'Hib Dose 2',
        'hib3_date': 'Hib Dose 3',
        'hib_rappel_date': 'Hib Booster',
        'ror_date': 'MMR',
        'rougeole_seule_date': 'Measles (single)'
    }
    
    if field_name not in vaccine_fields:
        flash("Invalid vaccine field.", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    
    field_label = vaccine_fields[field_name]
    current_value = patient[field_name] if patient[field_name] else ''
    
    return render_template('edit_standard_vaccine.html',
                         title=f"Edit {field_label}",
                         patient=patient,
                         field_name=field_name,
                         field_label=field_label,
                         current_value=current_value)

@patient_bp.route('/<int:patient_id>/update_standard_vaccine', methods=['POST'])
def update_standard_vaccine(patient_id):
    """Update a standard vaccine field for a patient"""
    db = get_db()
    patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
    patient = patient_cursor.fetchone()
    
    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for('patient.list_patients'))
    
    field_name = request.form.get('vaccine_field_name')
    vaccine_date = request.form.get('vaccine_date')
    
    # Validate field name
    vaccine_fields = [
        'dtcp1_date', 'dtcp2_date', 'dtcp3_date',
        'dtcp_rappel1_date', 'dtcp_rappel2_date', 'dtcp_rappel3_date', 'dtcp_rappel4_date',
        'hep_b1_date', 'hep_b2_date', 'hep_b3_date',
        'hib1_date', 'hib2_date', 'hib3_date', 'hib_rappel_date',
        'ror_date', 'rougeole_seule_date'
    ]
    
    if field_name not in vaccine_fields:
        flash("Invalid vaccine field.", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    
    try:
        # Update the vaccine field
        if vaccine_date == '':
            vaccine_date = None
        
        db.execute(f"UPDATE Patients SET {field_name} = ? WHERE id = ?", (vaccine_date, patient_id))
        db.commit()
        
        # Update Word document
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        
        flash('Vaccine record updated successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating vaccine record: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@patient_bp.route('/<int:patient_id>/add_other_vaccine', methods=['GET', 'POST'])
def add_other_vaccine(patient_id):
    """Add a new non-standard vaccine for a patient"""
    db = get_db()
    patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
    patient = patient_cursor.fetchone()
    
    if not patient:
        flash("Patient not found.", "danger")
        return redirect(url_for('patient.list_patients'))
    
    if request.method == 'POST':
        vaccine_name = request.form.get('other_vaccine_name', '').strip()
        vaccine_date = request.form.get('other_vaccine_date', '').strip()
        
        if not vaccine_name:
            flash('Vaccine name is required.', 'danger')
            return render_template('edit_other_vaccine.html',
                                 title="Add Other Vaccine",
                                 patient=patient,
                                 vaccine={'vaccine_name': vaccine_name, 'vaccine_date': vaccine_date})
        
        try:
            # Insert new vaccine record
            db.execute("""
                INSERT INTO NonStandardVaccines (patient_id, vaccine_name, vaccine_date, created_date)
                VALUES (?, ?, ?, ?)
            """, (patient_id, vaccine_name, vaccine_date if vaccine_date else None, datetime.now().isoformat()))
            db.commit()
            
            # Update Word document
            config = load_config()
            word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
            word_manager.create_or_update_document(patient_id)
            
            flash('Vaccine added successfully!', 'success')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))
        except Exception as e:
            db.rollback()
            flash(f'Error adding vaccine: {e}', 'danger')
    
    # GET request - show form
    return render_template('edit_other_vaccine.html',
                         title="Add Other Vaccine",
                         patient=patient,
                         vaccine={'vaccine_name': '', 'vaccine_date': ''})

@patient_bp.route('/edit_other_vaccine/<int:vaccine_id>')
def edit_other_vaccine(vaccine_id):
    """Edit a non-standard vaccine record"""
    db = get_db()
    vaccine_cursor = db.execute("""
        SELECT nsv.*, p.* FROM NonStandardVaccines nsv
        JOIN Patients p ON nsv.patient_id = p.id
        WHERE nsv.id = ?
    """, (vaccine_id,))
    result = vaccine_cursor.fetchone()
    
    if not result:
        flash("Vaccine record not found.", "danger")
        return redirect(url_for('patient.list_patients'))
    
    # Split the result into vaccine and patient data
    vaccine = {
        'id': result['id'],
        'vaccine_name': result['vaccine_name'],
        'vaccine_date': result['vaccine_date'],
        'patient_id': result['patient_id']
    }
    patient = dict(result)  # Contains all patient fields
    
    return render_template('edit_other_vaccine.html',
                         title="Edit Other Vaccine",
                         patient=patient,
                         vaccine=vaccine)

@patient_bp.route('/update_other_vaccine/<int:vaccine_id>', methods=['POST'])
def update_other_vaccine(vaccine_id):
    """Update a non-standard vaccine record"""
    db = get_db()
    vaccine_cursor = db.execute("SELECT patient_id FROM NonStandardVaccines WHERE id = ?", (vaccine_id,))
    vaccine_record = vaccine_cursor.fetchone()
    
    if not vaccine_record:
        flash("Vaccine record not found.", "danger")
        return redirect(url_for('patient.list_patients'))
    
    patient_id = vaccine_record['patient_id']
    vaccine_name = request.form.get('vaccine_name', '').strip()
    vaccine_date = request.form.get('vaccine_date', '').strip()
    
    if not vaccine_name:
        flash('Vaccine name is required.', 'danger')
        return redirect(url_for('patient.edit_other_vaccine', vaccine_id=vaccine_id))
    
    try:
        # Update vaccine record
        db.execute("""
            UPDATE NonStandardVaccines 
            SET vaccine_name = ?, vaccine_date = ?
            WHERE id = ?
        """, (vaccine_name, vaccine_date if vaccine_date else None, vaccine_id))
        db.commit()
        
        # Update Word document
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        
        flash('Vaccine record updated successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating vaccine record: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@patient_bp.route('/delete_other_vaccine/<int:vaccine_id>')
def delete_other_vaccine(vaccine_id):
    """Delete a non-standard vaccine record"""
    db = get_db()
    vaccine_cursor = db.execute("SELECT patient_id FROM NonStandardVaccines WHERE id = ?", (vaccine_id,))
    vaccine_record = vaccine_cursor.fetchone()
    
    if not vaccine_record:
        flash("Vaccine record not found.", "danger")
        return redirect(url_for('patient.list_patients'))
    
    patient_id = vaccine_record['patient_id']
    
    try:
        # Delete vaccine record
        db.execute("DELETE FROM NonStandardVaccines WHERE id = ?", (vaccine_id,))
        db.commit()
        
        # Update Word document
        config = load_config()
        word_manager = WordDocumentManager(db_path=config['database_path'], documents_folder=config['word_docs_folder'])
        word_manager.create_or_update_document(patient_id)
        
        flash('Vaccine record deleted successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting vaccine record: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

# Vaccine editing routes - matching foxpro2025 implementation
@patient_bp.route('/<int:patient_id>/vaccine/standard/edit', methods=['GET'])
def edit_standard_vaccine_form(patient_id):
    db = get_db()
    field_name = request.args.get('field_name')
    
    # Basic validation for allowed field names to prevent arbitrary column updates
    allowed_vaccine_fields = [
        'dtcp1_date', 'dtcp2_date', 'dtcp3_date', 
        'dtcp_rappel1_date', 'dtcp_rappel2_date', 'dtcp_rappel3_date', 'dtcp_rappel4_date',
        'hep_b1_date', 'hep_b2_date', 'hep_b3_date',
        'hib1_date', 'hib2_date', 'hib3_date', 'hib_rappel_date',
        'ror_date', 'rougeole_seule_date',
        'monotest1', 'monotest2', 'monotest3' # Monotest fields are also often dates
    ]
    if not field_name or field_name not in allowed_vaccine_fields:
        flash('Invalid or missing vaccine field specified for editing.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    try:
        # Fetch only the required field and basic patient identifiers
        # Using f-string for column name is generally risky, but here field_name is validated against a whitelist
        patient_data_cursor = db.execute(f"SELECT id, mrn, nom, prenom, {field_name} FROM Patients WHERE id = ?", (patient_id,))
        patient = patient_data_cursor.fetchone()

        if not patient:
            flash('Patient not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        current_value = patient[field_name]
        
        # Create a more human-readable label for the field
        field_label = field_name.replace('_', ' ').replace('date', 'Date').title()
        if 'Monotest' in field_label and not field_label.endswith("Date"):
            field_label += " Date"

        return render_template('edit_standard_vaccine.html',
                               patient=patient,
                               field_name=field_name,
                               field_label=field_label,
                               current_value=current_value,
                               title=f"Edit {field_label}")

    except sqlite3.Error as e:
        flash(f"Database error fetching patient data for vaccine edit: {e}", 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@patient_bp.route('/<int:patient_id>/vaccine/standard/update', methods=['POST'])
def update_standard_vaccine_form(patient_id):
    db = get_db()
    field_name = request.form.get('vaccine_field_name')
    vaccine_date_str = request.form.get('vaccine_date')

    # Use the same allowed fields list
    allowed_vaccine_fields = [
        'dtcp1_date', 'dtcp2_date', 'dtcp3_date', 
        'dtcp_rappel1_date', 'dtcp_rappel2_date', 'dtcp_rappel3_date', 'dtcp_rappel4_date',
        'hep_b1_date', 'hep_b2_date', 'hep_b3_date',
        'hib1_date', 'hib2_date', 'hib3_date', 'hib_rappel_date',
        'ror_date', 'rougeole_seule_date',
        'monotest1', 'monotest2', 'monotest3'
    ]

    if field_name not in allowed_vaccine_fields:
        flash('Invalid vaccine field specified.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    vaccine_date = None
    if vaccine_date_str:
        try:
            datetime.strptime(vaccine_date_str, '%Y-%m-%d') # Validate format
            vaccine_date = vaccine_date_str
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            # Redirect back to edit form
            return redirect(url_for('patient.edit_standard_vaccine_form', patient_id=patient_id, field_name=field_name))

    try:
        db.execute(f"UPDATE Patients SET {field_name} = ? WHERE id = ?", (vaccine_date, patient_id))
        db.commit()
        flash(f'Vaccine updated successfully.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating vaccine: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@patient_bp.route('/vaccine/other/<int:vaccine_id>/edit', methods=['GET'])
def edit_other_vaccine_form(vaccine_id):
    db = get_db()
    vaccine = db.execute(
        'SELECT nsv.*, p.id as patient_id, p.nom, p.prenom, p.mrn FROM NonStandardVaccines nsv JOIN Patients p ON nsv.patient_id = p.id WHERE nsv.id = ?',
        (vaccine_id,)
    ).fetchone()

    if not vaccine:
        flash('Non-standard vaccine not found.', 'danger')
        return redirect(url_for('patient.list_patients')) 

    patient_data = {
        'id': vaccine['patient_id'],
        'nom': vaccine['nom'],
        'prenom': vaccine['prenom'],
        'mrn': vaccine['mrn']
    }
    
    return render_template('edit_other_vaccine.html', vaccine=vaccine, patient=patient_data, title="Edit Other Vaccine")

@patient_bp.route('/vaccine/other/<int:vaccine_id>/update', methods=['POST'])
def update_other_vaccine_form(vaccine_id):
    db = get_db()
    patient_id = request.form.get('patient_id') # Or fetch from DB if not passed
    vaccine_name = request.form.get('vaccine_name')
    vaccine_date_str = request.form.get('vaccine_date')

    if not patient_id:
        flash('Patient ID missing.', 'danger')
        return redirect(url_for('patient.list_patients'))

    vaccine_date = None
    if vaccine_date_str:
        try:
            datetime.strptime(vaccine_date_str, '%Y-%m-%d') # Validate format
            vaccine_date = vaccine_date_str
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
            return redirect(url_for('patient.edit_other_vaccine_form', vaccine_id=vaccine_id))

    if not vaccine_name:
        flash('Vaccine name cannot be empty.', 'danger')
        return redirect(url_for('patient.edit_other_vaccine_form', vaccine_id=vaccine_id))

    try:
        # Update the NonStandardVaccines table
        db.execute(
            'UPDATE NonStandardVaccines SET vaccine_name = ?, vaccine_date = ? WHERE id = ?',
            (vaccine_name, vaccine_date, vaccine_id)
        )
        db.commit()
        flash('Non-standard vaccine updated successfully.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating non-standard vaccine: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id)) 