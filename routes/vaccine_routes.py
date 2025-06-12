from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from database import get_db
from emr_config import emr_config
from statistics_engine.statistics_calculator import calculate_average_vaccines_per_child
import sqlite3
import json
from datetime import datetime
from word_document_manager import WordDocumentManager
from utils.vaccine_schedule_engine import get_patient_vaccine_timeline, vaccine_schedule_engine, get_vaccine_schedule_config, update_vaccine_schedule_config, reset_vaccine_schedule_to_defaults
from utils.vaccine_mapping import get_field_mapping_dict, get_comprehensive_mapping
from dataclasses import asdict

vaccine_bp = Blueprint('vaccine', __name__, url_prefix='/vaccines')

@vaccine_bp.route('/')
def vaccine_tracking():
    """Main vaccine tracking dashboard"""
    current_mode = emr_config.get_emr_mode()
    
    # Check if vaccines are enabled
    if not emr_config.is_feature_enabled('vaccines'):
        flash('Vaccine tracking is not enabled for the current EMR mode.', 'warning')
        return redirect(url_for('index'))
    
    return render_template('vaccine_tracking.html',
                         title='Vaccine Tracking Dashboard',
                         current_mode=current_mode)

# =============================================================================
# STANDARD VACCINE EDITING ROUTES
# =============================================================================

@vaccine_bp.route('/patient/<int:patient_id>/standard/edit', methods=['GET'])
def edit_standard_vaccine_form(patient_id):
    """Edit a standard vaccine field for a patient"""
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

@vaccine_bp.route('/patient/<int:patient_id>/standard/update', methods=['POST'])
def update_standard_vaccine_form(patient_id):
    """Update a standard vaccine field for a patient"""
    db = get_db()
    
    # Check if this is a JSON request (from AJAX) or form request
    if request.is_json:
        data = request.get_json()
        field_name = data.get('field_name')
        vaccine_date_str = data.get('date')
    else:
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
        error_msg = 'Invalid vaccine field specified.'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 400
        flash(error_msg, 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

    vaccine_date = None
    if vaccine_date_str:
        try:
            datetime.strptime(vaccine_date_str, '%Y-%m-%d') # Validate format
            vaccine_date = vaccine_date_str
        except ValueError:
            error_msg = 'Invalid date format. Please use YYYY-MM-DD.'
            if request.is_json:
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            # Redirect back to edit form
            return redirect(url_for('vaccine.edit_standard_vaccine_form', patient_id=patient_id, field_name=field_name))

    try:
        db.execute(f"UPDATE Patients SET {field_name} = ? WHERE id = ?", (vaccine_date, patient_id))
        db.commit()
        
        if request.is_json:
            return jsonify({'success': True})
        
        flash(f'Vaccine updated successfully.', 'success')
    except Exception as e:
        db.rollback()
        error_msg = f'Error updating vaccine: {e}'
        if request.is_json:
            return jsonify({'success': False, 'error': error_msg}), 500
        flash(error_msg, 'danger')
    
    # For form requests, redirect as before
    referrer = request.referrer
    if referrer and 'vaccine_schedule_timeline' in referrer:
        return redirect(url_for('vaccine.vaccine_schedule_timeline', patient_id=patient_id))
    else:
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

# =============================================================================
# NON-STANDARD VACCINE EDITING ROUTES
# =============================================================================

@vaccine_bp.route('/patient/<int:patient_id>/other/add', methods=['GET', 'POST'])
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
        total_doses_planned = request.form.get('total_doses_planned', '1')
        interval_months = request.form.get('interval_months', '')
        
        if not vaccine_name:
            flash('Vaccine name is required.', 'danger')
            return render_template('edit_other_vaccine.html',
                                 title="Add Other Vaccine",
                                 patient=patient,
                                 vaccine={'vaccine_name': vaccine_name, 'vaccine_date': vaccine_date})
        
        try:
            # Convert to integers and validate
            total_doses = int(total_doses_planned) if total_doses_planned else 1
            interval = int(interval_months) if interval_months else None
            
            # Insert new vaccine record
            db.execute("""
                INSERT INTO NonStandardVaccines (patient_id, vaccine_name, vaccine_date, dose_number, total_doses_planned, interval_months, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (patient_id, vaccine_name, vaccine_date if vaccine_date else None, 1, total_doses, interval, datetime.now().isoformat()))
            db.commit()
            
            # Update Word document
            word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
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

@vaccine_bp.route('/other/<int:vaccine_id>/edit', methods=['GET'])
def edit_other_vaccine_form(vaccine_id):
    """Edit a non-standard vaccine record"""
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

@vaccine_bp.route('/other/<int:vaccine_id>/update', methods=['POST'])
def update_other_vaccine_form(vaccine_id):
    """Update a non-standard vaccine record"""
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
            return redirect(url_for('vaccine.edit_other_vaccine_form', vaccine_id=vaccine_id))

    if not vaccine_name:
        flash('Vaccine name cannot be empty.', 'danger')
        return redirect(url_for('vaccine.edit_other_vaccine_form', vaccine_id=vaccine_id))

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

@vaccine_bp.route('/other/<int:vaccine_id>/update', methods=['POST'])
def update_other_vaccine(vaccine_id):
    """Update a non-standard vaccine record (legacy route)"""
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
        return redirect(url_for('vaccine.edit_other_vaccine_form', vaccine_id=vaccine_id))
    
    try:
        # Update vaccine record
        db.execute("""
            UPDATE NonStandardVaccines 
            SET vaccine_name = ?, vaccine_date = ?
            WHERE id = ?
        """, (vaccine_name, vaccine_date if vaccine_date else None, vaccine_id))
        db.commit()
        
        # Update Word document
        word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
        word_manager.create_or_update_document(patient_id)
        
        flash('Vaccine record updated successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating vaccine record: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@vaccine_bp.route('/patient/<int:patient_id>/standard/update', methods=['POST'])
def update_standard_vaccine(patient_id):
    """Update a standard vaccine field for a patient (legacy route)"""
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
        word_manager = WordDocumentManager(db_path=emr_config.get_database_path(), documents_folder=emr_config.get_word_docs_folder())
        word_manager.create_or_update_document(patient_id)
        
        flash('Vaccine record updated successfully!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating vaccine record: {e}', 'danger')
    
    return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@vaccine_bp.route('/schedule/<int:patient_id>')
def vaccine_schedule_timeline(patient_id):
    """Generate and display the vaccine schedule timeline for a patient"""
    try:
        db = get_db()
        # Fetch patient's basic data
        patient = db.execute(
            'SELECT id, nom, prenom, mrn, date_of_birth, naissance_date, raw_autres_vaccins_text FROM Patients WHERE id = ?',
            (patient_id,)
        ).fetchone()
        
        if not patient:
            flash('Patient not found.', 'danger')
            return redirect(url_for('patient.list_patients'))

        patient_dob = patient['date_of_birth'] or patient['naissance_date']
        if not patient_dob:
            flash('Patient has no date of birth, cannot calculate vaccine schedule.', 'warning')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # 1. Fetch from the new unified Immunizations table
        immunizations_cursor = db.execute(
            "SELECT immunization, administered_date, brand_name, dose_number, notes FROM Immunizations WHERE patient_id = ? ORDER BY administered_date ASC",
            (patient_id,)
        )
        unified_immunizations = immunizations_cursor.fetchall()
        
        # 2. Fetch standard vaccine data from Patients table for backward compatibility
        patient_vaccines = dict(patient)

        # 3. Fetch from old NonStandardVaccines table for backward compatibility
        autres_vaccins_cursor = db.execute("SELECT * FROM NonStandardVaccines WHERE patient_id = ?", (patient_id,))
        autres_vaccins = autres_vaccins_cursor.fetchall()

        # Calculate vaccine timeline using the new unified immunizations data
        timeline = get_patient_vaccine_timeline(
            patient_dob=patient_dob,
            administered_immunizations=unified_immunizations
        )
        
        # Get summary statistics
        summary_stats = vaccine_schedule_engine.get_summary_stats(timeline)
        
        # Convert dataclasses to dicts for JSON serialization in template
        timeline_data = []
        for vaccine_item in timeline:
            vaccine_data = asdict(vaccine_item)
            # Convert dose statuses to strings for template
            for dose in vaccine_data['doses']:
                dose['status'] = dose['status'].value if hasattr(dose['status'], 'value') else str(dose['status'])
            if vaccine_data['next_due_dose']:
                vaccine_data['next_due_dose']['status'] = vaccine_data['next_due_dose']['status'].value if hasattr(vaccine_data['next_due_dose']['status'], 'value') else str(vaccine_data['next_due_dose']['status'])
            timeline_data.append(vaccine_data)
        
        return render_template('vaccine_schedule_timeline.html',
                             title=f'Vaccine Schedule - {patient["prenom"]} {patient["nom"]}',
                             patient=patient,
                             timeline=timeline_data,
                             summary_stats=summary_stats,
                             emr_config=emr_config)
            
    except Exception as e:
        current_app.logger.error(f"Error generating vaccine schedule for patient {patient_id}: {e}", exc_info=True)
        flash(f"Error loading vaccine schedule: {str(e)}", 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@vaccine_bp.route('/config')
def vaccine_config():
    """Display vaccine schedule configuration management page"""
    try:
        # Use the centralized function to get the config
        schedule_config = get_vaccine_schedule_config()
        schedule_config_json = json.dumps(schedule_config, indent=2)
        
        return render_template('vaccine_config.html',
                             title='Vaccine Schedule Configuration',
                             schedule_config=schedule_config,
                             schedule_config_json=schedule_config_json,
                             emr_config=emr_config)
    except Exception as e:
        current_app.logger.error(f"Error loading vaccine config page: {e}", exc_info=True)
        flash(f"Error loading vaccine configuration: {str(e)}", 'danger')
        return render_template('vaccine_config.html',
                             title='Vaccine Schedule Configuration',
                             schedule_config={},
                             schedule_config_json="{}",
                             error=str(e),
                             emr_config=emr_config)

@vaccine_bp.route('/config/update', methods=['POST'])
def update_vaccine_config():
    """Update vaccine schedule configuration"""
    if not emr_config.is_feature_enabled('vaccines'):
        return jsonify({'error': 'Vaccines not enabled'}), 400
    
    try:
        config_data = request.get_json()
        if not config_data:
            return jsonify({'success': False, 'message': 'No configuration data provided'}), 400
        
        # Use the centralized update function
        update_vaccine_schedule_config(config_data)
        
        return jsonify({'success': True, 'message': 'Configuration updated successfully'})
        
    except Exception as e:
        current_app.logger.error(f"Error updating vaccine config: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500

@vaccine_bp.route('/config/reset', methods=['POST'])
def reset_vaccine_config():
    """Reset vaccine schedule configuration to defaults"""
    try:
        # This will now correctly reset the main config file
        reset_vaccine_schedule_to_defaults()
        flash('Vaccine schedule configuration reset to defaults successfully!', 'success')
        
    except Exception as e:
        flash(f'Error resetting configuration: {str(e)}', 'danger')
    
    return redirect(url_for('vaccine.vaccine_config'))

@vaccine_bp.route('/patient/<int:patient_id>/additional/update', methods=['POST'])
def update_additional_vaccine(patient_id):
    """Update date for a patient-specific vaccine dose"""
    try:
        data = request.get_json()
        vaccine_id = data.get('vaccine_id')
        dose_number = data.get('dose_number', 1)
        new_date = data.get('date')
        
        db = get_db()
        
        if dose_number == 1:
            # Update the original vaccine record
            db.execute("""
                UPDATE NonStandardVaccines 
                SET vaccine_date = ?
                WHERE id = ? AND patient_id = ?
            """, (new_date, vaccine_id, patient_id))
        else:
            # For subsequent doses, we need to either create a new record or update existing
            # Check if a record exists for this dose
            existing = db.execute("""
                SELECT id FROM NonStandardVaccines 
                WHERE patient_id = ? AND vaccine_name = (
                    SELECT vaccine_name FROM NonStandardVaccines WHERE id = ?
                ) AND dose_number = ?
            """, (patient_id, vaccine_id, dose_number)).fetchone()
            
            if existing:
                # Update existing dose record
                db.execute("""
                    UPDATE NonStandardVaccines 
                    SET vaccine_date = ?
                    WHERE id = ?
                """, (new_date, existing['id']))
            else:
                # Create new dose record
                base_vaccine = db.execute("""
                    SELECT vaccine_name, total_doses_planned, interval_months 
                    FROM NonStandardVaccines WHERE id = ?
                """, (vaccine_id,)).fetchone()
                
                db.execute("""
                    INSERT INTO NonStandardVaccines 
                    (patient_id, vaccine_name, vaccine_date, dose_number, total_doses_planned, interval_months)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (patient_id, base_vaccine['vaccine_name'], new_date, dose_number, 
                      base_vaccine['total_doses_planned'], base_vaccine['interval_months']))
        
        db.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        current_app.logger.error(f"Error updating additional vaccine: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@vaccine_bp.route('/field-mappings/<language>')
def get_vaccine_field_mappings(language='en'):
    """Get vaccine field mappings as JSON for frontend consumption"""
    try:
        mapping = get_field_mapping_dict(language)
        return jsonify({
            'success': True,
            'mappings': mapping,
            'total_vaccines': len(mapping)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

