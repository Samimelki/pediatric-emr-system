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
    search_father_name = request.args.get('father_name', '').strip()
    search_mother_name = request.args.get('mother_name', '').strip()

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
    if search_father_name:
        conditions.append("pere_nom LIKE :father_name")
        params['father_name'] = f"%{search_father_name}%"
    if search_mother_name:
        conditions.append("mere_nom LIKE :mother_name")
        params['mother_name'] = f"%{search_mother_name}%"

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
                           search_father_name=search_father_name,
                           search_mother_name=search_mother_name,
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
            print(f"DEBUG: Processing vaccines for patient {patient_id}")
            print(f"DEBUG: Patient data keys: {list(patient.keys())}")
            
            # Get other vaccines data - group by vaccine name to handle multi-dose vaccines
            vaccine_cursor = db.execute("""
                SELECT * FROM Immunizations 
                WHERE patient_id = ? 
                ORDER BY immunization, dose_number ASC
            """, (patient_id,))
            all_vaccine_records = vaccine_cursor.fetchall()
            
            # Group vaccines by name to handle multi-dose series
            vaccine_groups = {}
            for record in all_vaccine_records:
                vaccine_name = record['immunization']
                if vaccine_name not in vaccine_groups:
                    vaccine_groups[vaccine_name] = []
                vaccine_groups[vaccine_name].append(dict(record))
            
            # Convert to the format expected by the template
            additional_vaccines = []
            for vaccine_name, doses in vaccine_groups.items():
                # Use the first dose as the base record
                base_vaccine = doses[0]
                base_vaccine['all_doses'] = doses
                additional_vaccines.append(base_vaccine)
            
            # Use shared vaccine name utilities for consistent behavior
            from utils.vaccine_name_utils import get_canonical_vaccine_name, is_vaccine_in_standard_schedule
            
            # Calculate due dates for patient-specific vaccines
            from datetime import datetime, timedelta
            from dateutil.relativedelta import relativedelta
            
            additional_vaccines_with_schedule = []
            for vaccine in additional_vaccines:
                # Check if this vaccine is in the standard vaccine schedule
                vaccine_name = vaccine['immunization'] if 'immunization' in vaccine.keys() else ''
                
                # Use shared utility to check if vaccine is in standard schedule
                is_standard = is_vaccine_in_standard_schedule(vaccine_name)
                if is_standard:
                    continue  # Skip vaccines that are in the standard schedule (they'll appear in timeline)
                vaccine_dict = dict(vaccine)
                vaccine_dict['doses_schedule'] = []
                vaccine_dict['next_due_dose'] = None
                

                
                # For Immunizations table, we don't have total_doses_planned or interval_months
                # Just show the doses that were actually given
                total_doses = len(vaccine.get('all_doses', [vaccine])) if 'all_doses' in vaccine else 1
                interval_months = None  # Not available in Immunizations table
                
                # First dose (always exists if there's a date)
                if vaccine['administered_date']:
                    try:
                        first_dose_date = datetime.strptime(vaccine['administered_date'], '%Y-%m-%d')
                        current_date = datetime.now()
                        
                        # Generate schedule for all doses
                        for dose_num in range(1, total_doses + 1):
                            if dose_num == 1:
                                # First dose (already given)
                                dose_info = {
                                    'dose_number': dose_num,
                                    'due_date': first_dose_date.strftime('%Y-%m-%d'),
                                    'completed_date': first_dose_date.strftime('%Y-%m-%d'),
                                    'status': 'completed',
                                    'label': f'Dose {dose_num}',
                                    'vaccine_id': vaccine['id'],
                                    'is_editable': True
                                }
                            else:
                                # Calculate due date for subsequent doses
                                if interval_months:
                                    due_date = first_dose_date + relativedelta(months=(dose_num - 1) * interval_months)
                                    days_diff = (due_date - current_date).days
                                    
                                    if days_diff <= 0:
                                        status = 'overdue' if days_diff < -30 else 'due'  # 30 day grace period
                                    elif days_diff <= 30:
                                        status = 'due'
                                    else:
                                        status = 'upcoming'
                                    
                                    dose_info = {
                                        'dose_number': dose_num,
                                        'due_date': due_date.strftime('%Y-%m-%d'),
                                        'completed_date': None,
                                        'status': status,
                                        'label': f'Dose {dose_num}',
                                        'days_until_due': days_diff,
                                        'vaccine_id': vaccine['id'],
                                        'is_editable': True
                                    }
                                    
                                    # Set next due dose (first non-completed dose)
                                    if not vaccine_dict['next_due_dose'] and status in ['due', 'overdue']:
                                        vaccine_dict['next_due_dose'] = dose_info
                                else:
                                    # No interval specified, just mark as pending
                                    dose_info = {
                                        'dose_number': dose_num,
                                        'due_date': 'TBD',
                                        'completed_date': None,
                                        'status': 'pending',
                                        'label': f'Dose {dose_num}',
                                        'vaccine_id': vaccine['id'],
                                        'is_editable': True
                                    }
                            
                            vaccine_dict['doses_schedule'].append(dose_info)
                    
                    except (ValueError, TypeError) as e:
                        vaccine_name = vaccine.get('immunization') or vaccine.get('vaccine_name', 'Unknown')
                        print(f"Error calculating schedule for vaccine {vaccine_name}: {e}")
                else:
                    # No date given yet, just show the planned doses
                    for dose_num in range(1, total_doses + 1):
                        dose_info = {
                            'dose_number': dose_num,
                            'due_date': 'Not scheduled',
                            'completed_date': None,
                            'status': 'pending',
                            'label': f'Dose {dose_num}',
                            'vaccine_id': vaccine['id'],
                            'is_editable': True
                        }
                        vaccine_dict['doses_schedule'].append(dose_info)
                
                additional_vaccines_with_schedule.append(vaccine_dict)
            
            # Additional vaccines processed successfully
            
        except Exception as e:
            current_app.logger.error(f"Error preparing vaccine data for patient {patient_id}: {e}", exc_info=True)
            # Don't flash error to user, just log it and continue with empty vaccine data
            additional_vaccines_with_schedule = []

    # Get vaccine timeline data for the patient if vaccines are enabled and patient has DOB
    timeline = []
    summary_stats = {}
    patient_dob = patient.get('date_of_birth') or patient.get('naissance_date') if patient else None
    
    if emr_config.is_feature_enabled('vaccines') and patient_dob:
        try:
            from utils.vaccine_schedule_engine import get_patient_vaccine_timeline, vaccine_schedule_engine
            from dataclasses import asdict
            
            # Fetch from the new unified Immunizations table
            immunizations_cursor = db.execute(
                "SELECT immunization, administered_date, brand_name, dose_number FROM Immunizations WHERE patient_id = ? ORDER BY administered_date ASC",
                (patient_id,)
            )
            unified_immunizations = immunizations_cursor.fetchall()
            
            print(f"DEBUG TIMELINE: Found {len(unified_immunizations)} immunizations in database")
            for i, imm in enumerate(unified_immunizations[:5]):  # Show first 5
                print(f"  {i+1}. {imm['immunization']} on {imm['administered_date']}")
            if len(unified_immunizations) > 5:
                print(f"  ... and {len(unified_immunizations) - 5} more")
            
            # Check if vaccine schedule configuration exists and is appropriate for current profile
            try:
                # Get vaccine timeline using the new unified data source
                timeline_items = get_patient_vaccine_timeline(
                    patient_dob=patient_dob,
                    administered_immunizations=unified_immunizations
                )
                
                print(f"DEBUG TIMELINE: Generated {len(timeline_items)} timeline items")
                
                summary_stats = vaccine_schedule_engine.get_summary_stats(timeline_items)
                
                # Convert dataclasses to dicts for JSON serialization in template
                for vaccine_item in timeline_items:
                    vaccine_data = asdict(vaccine_item)
                    # Convert dose statuses to strings for template
                    for dose in vaccine_data['doses']:
                        dose['status'] = dose['status'].value if hasattr(dose['status'], 'value') else str(dose['status'])
                    if vaccine_data['next_due_dose']:
                        vaccine_data['next_due_dose']['status'] = vaccine_data['next_due_dose']['status'].value if hasattr(vaccine_data['next_due_dose']['status'], 'value') else str(vaccine_data['next_due_dose']['status'])
                    timeline.append(vaccine_data)
                    
            except Exception as timeline_error:
                print(f"DEBUG TIMELINE: Error generating timeline: {timeline_error}")
                # If timeline generation fails, just show empty timeline but don't crash
                timeline = []
                summary_stats = {}
            
        except Exception as e:
            current_app.logger.error(f"Error processing vaccine data for patient {patient_id}: {e}", exc_info=True)
            # Don't let vaccine processing errors crash the entire patient view
            timeline = []
            summary_stats = {}

    # Prepare growth chart data for pediatric patients (only if growth charts are enabled)
    visit_ages_in_months = []
    weight_data = []
    height_data = []
    hc_data = []
    who_chart_data = {}
    
    if emr_config.is_feature_enabled('growth_charts') and not dob_missing and patient and visits_with_addenda:
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

    # Get patient name safely - try French fields first, then English fields
    patient_first_name = ''
    patient_last_name = ''
    if patient:
        patient_first_name = patient.get('prenom') or patient.get('first_name') or 'N/A'
        patient_last_name = patient.get('nom') or patient.get('last_name') or ''
    
    return render_template('patient_detail.html', 
                           title=f"Patient Details - {patient_first_name} {patient_last_name}", 
                           patient=patient, 
                           visits=visits_with_addenda,
                           dob_missing=dob_missing, # Pass dob_missing to template
                           mandatory_vaccines_emr=mandatory_vaccines_emr,
                           recommended_vaccines_emr=recommended_vaccines_emr,
                           active_dose_keys_emr=active_dose_keys_emr,
                           table_column_labels_emr=table_column_labels_emr,
                           # Patient-specific vaccines
                           additional_vaccines=additional_vaccines_with_schedule if 'additional_vaccines_with_schedule' in locals() else [],
                           # Vaccine timeline data
                           timeline=timeline,
                           summary_stats=summary_stats,
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

