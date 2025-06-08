# =============================================================================
# PATIENT ROUTES MODULE - Organized for Future Refactoring
# 
# STRUCTURE:
# Section 1: Configuration and Constants (Lines 20-50)
# Section 2: Utility Functions (Lines 51-220) 
# Section 3: Patient Core Routes - List, Detail, Demographics (Lines 221-670)
# Section 4: Visit Management Routes (Lines 671-1380)
# Section 5: Media Management Routes (Lines 1381-1430)
# Section 6: Vaccine Management Routes (Lines 1431-1808)
#
# Total Lines: 1808 (Target: Split when ready for production)
# Status: ✅ ORGANIZED ✅ WORKING ✅ READY FOR INCREMENTAL REFACTORING
# =============================================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
import sqlite3
import math
from datetime import datetime, date
from collections import defaultdict
from database import get_db, get_active_custom_demographic_fields
from unified_database import get_patient_unified_data, get_visit_unified_data
from emr_config import emr_config
from dateutil.relativedelta import relativedelta
import json

from word_document_manager import WordDocumentManager
import os
from who_data_loader import who_loader

# Import utility functions
from utils.patient_utils import (
    convert_weight_to_kg,
    calculate_age_at_visit,
    prepare_vaccine_data_for_emr
)
# Form validators moved to demographics_routes.py

# =============================================================================
# SECTION 1: CONFIGURATION AND CONSTANTS
# =============================================================================

# EDITABLE_DEMOGRAPHIC_FIELDS has been moved to routes/demographics_routes.py

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

# Configuration
PER_PAGE = 50

# =============================================================================
# SECTION 2: UTILITY FUNCTIONS - EXTRACTED TO utils/patient_utils.py
# =============================================================================

# All utility functions have been moved to utils/patient_utils.py for better organization
# Functions now available via import: convert_weight_to_kg, convert_kg_to_storage_format, 
# calculate_age_at_visit, prepare_vaccine_data_for_emr



# =============================================================================
# SECTION 3: PATIENT CORE ROUTES (List, Detail, Demographics)  
# =============================================================================



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
                
                # For profiles with pediatric features, add direct measurement fields to vitals if they exist
                if emr_config.is_feature_enabled('weight_tracking') or emr_config.is_feature_enabled('height_tracking'):
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
    
    if emr_config.is_feature_enabled('vaccines'):
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
            all_vaccines_for_emr_table = prepare_vaccine_data_for_emr(patient, autres_vaccins, patient_id)
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

                           emr_config=emr_config,
                           grouped_custom_fields=dict(grouped_custom_fields),
                           # Growth chart data
                           visit_ages_in_months=visit_ages_in_months,
                           weight_data=weight_data,
                           height_data=height_data,
                           hc_data=hc_data,
                           **who_chart_data)

# Demographics routes have been extracted to routes/demographics_routes.py

@patient_bp.route('/<int:patient_id>/edit_history', methods=['GET', 'POST'])
def edit_patient_history(patient_id):
    """Edit patient's medical history"""
    db = get_db()
    
    if request.method == 'POST':
        try:
            # Get form data
            pmh = request.form.get('pmh', '').strip()
            psh = request.form.get('psh', '').strip()
            family_history = request.form.get('family_history', '').strip()
            medications = request.form.get('medications', '').strip()
            allergies = request.form.get('allergies', '').strip()
            
            # Social history fields
            smoker = 1 if request.form.get('smoker') else 0
            smoker_details = request.form.get('smoker_details', '').strip()
            alcohol = 1 if request.form.get('alcohol') else 0
            alcohol_details = request.form.get('alcohol_details', '').strip()
            
            # Update the patient record
            db.execute("""
                UPDATE Patients 
                SET pmh = ?, psh = ?, family_history = ?, medications = ?, allergies = ?,
                    smoker = ?, smoker_details = ?, alcohol = ?, alcohol_details = ?
                WHERE id = ?
            """, (pmh, psh, family_history, medications, allergies, 
                  smoker, smoker_details, alcohol, alcohol_details, patient_id))
            
            db.commit()
            
            # Update Word document
            word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
            word_manager.create_or_update_document(patient_id)
            
            flash('Patient history updated successfully!', 'success')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))
            
        except Exception as e:
            db.rollback()
            flash(f'Error updating patient history: {e}', 'danger')
    
    # GET request - display the form
    try:
        patient_cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
        patient = patient_cursor.fetchone()
        
        if not patient:
            flash('Patient not found.', 'danger')
            return redirect(url_for('patient.list_patients'))
        
        return render_template('edit_patient_history.html', 
                             title='Edit Patient History',
                             patient=dict(patient),
                             history_fields=dict(patient))
                             
    except Exception as e:
        flash(f'Error loading patient history: {e}', 'danger')
        return redirect(url_for('patient.list_patients'))

