from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from database import get_db
from emr_config import emr_config
from statistics_engine.statistics_calculator import calculate_average_vaccines_per_child
import sqlite3
from datetime import datetime
from word_document_manager import WordDocumentManager
from utils.vaccine_schedule_engine import get_patient_vaccine_timeline, vaccine_schedule_engine
from dataclasses import asdict

vaccine_bp = Blueprint('vaccine', __name__, url_prefix='/vaccines')

@vaccine_bp.route('/')
def vaccine_tracking():
    """Main vaccine tracking dashboard"""
    current_mode = emr_config.get_emr_mode()
    
    # Check if vaccines are enabled
    if not emr_config.should_show_vaccines():
        flash('Vaccine tracking is not enabled for the current EMR mode.', 'warning')
        return redirect(url_for('index'))
    
    db = get_db()
    
    try:
        # Get vaccine statistics
        stats = {}
        
        # Count patients with at least one vaccine
        cursor = db.execute("""
            SELECT COUNT(DISTINCT p.id) as patients_with_vaccines
            FROM Patients p
            WHERE p.emr_mode IN ('pediatric', 'mixed')
            AND (p.dtcp1_date IS NOT NULL OR p.dtcp2_date IS NOT NULL OR p.dtcp3_date IS NOT NULL
                 OR p.hep_b1_date IS NOT NULL OR p.hep_b2_date IS NOT NULL OR p.hep_b3_date IS NOT NULL
                 OR p.hib1_date IS NOT NULL OR p.hib2_date IS NOT NULL OR p.hib3_date IS NOT NULL
                 OR p.ror_date IS NOT NULL OR p.rougeole_seule_date IS NOT NULL)
        """)
        stats['patients_with_vaccines'] = cursor.fetchone()['patients_with_vaccines']
        
        # Count total pediatric patients
        cursor = db.execute("SELECT COUNT(*) as total_pediatric FROM Patients WHERE emr_mode IN ('pediatric', 'mixed')")
        stats['total_pediatric_patients'] = cursor.fetchone()['total_pediatric']
        
        # Count non-standard vaccines
        cursor = db.execute("SELECT COUNT(*) as non_standard_vaccines FROM NonStandardVaccines")
        stats['non_standard_vaccines'] = cursor.fetchone()['non_standard_vaccines']
        
        # Calculate average vaccines per child
        try:
            stats['avg_vaccines_per_child'] = calculate_average_vaccines_per_child()
        except Exception as e:
            current_app.logger.error(f"Error calculating average vaccines: {e}")
            stats['avg_vaccines_per_child'] = 0
        
        # Get recent vaccine additions (last 30 days)
        cursor = db.execute("""
            SELECT 
                p.first_name || ' ' || p.last_name as patient_name,
                p.mrn,
                nsv.vaccine_name,
                nsv.vaccine_date,
                nsv.created_date
            FROM NonStandardVaccines nsv
            JOIN Patients p ON nsv.patient_id = p.id
            WHERE DATE(nsv.created_date) >= DATE('now', '-30 days')
            ORDER BY nsv.created_date DESC
            LIMIT 10
        """)
        recent_vaccines = cursor.fetchall()
        
        # Get incomplete vaccination patterns (patients missing core vaccines)
        cursor = db.execute("""
            SELECT 
                p.id,
                p.first_name || ' ' || p.last_name as patient_name,
                p.mrn,
                p.date_of_birth,
                CASE WHEN p.dtcp1_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.dtcp2_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.dtcp3_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.hep_b1_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.hep_b2_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.hep_b3_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.hib1_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.hib2_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.hib3_date IS NULL THEN 1 ELSE 0 END +
                CASE WHEN p.ror_date IS NULL THEN 1 ELSE 0 END as missing_vaccines
            FROM Patients p
            WHERE p.emr_mode IN ('pediatric', 'mixed')
            HAVING missing_vaccines > 5
            ORDER BY missing_vaccines DESC, p.date_of_birth DESC
            LIMIT 20
        """)
        incomplete_vaccinations = cursor.fetchall()
        
        # Get vaccine completion rates by vaccine type
        cursor = db.execute("""
            SELECT 
                'DTCP Series' as vaccine_type,
                COUNT(CASE WHEN dtcp1_date IS NOT NULL AND dtcp2_date IS NOT NULL AND dtcp3_date IS NOT NULL THEN 1 END) as completed,
                COUNT(*) as total
            FROM Patients 
            WHERE emr_mode IN ('pediatric', 'mixed')
            UNION ALL
            SELECT 
                'Hepatitis B Series' as vaccine_type,
                COUNT(CASE WHEN hep_b1_date IS NOT NULL AND hep_b2_date IS NOT NULL AND hep_b3_date IS NOT NULL THEN 1 END) as completed,
                COUNT(*) as total
            FROM Patients 
            WHERE emr_mode IN ('pediatric', 'mixed')
            UNION ALL
            SELECT 
                'Hib Series' as vaccine_type,
                COUNT(CASE WHEN hib1_date IS NOT NULL AND hib2_date IS NOT NULL AND hib3_date IS NOT NULL THEN 1 END) as completed,
                COUNT(*) as total
            FROM Patients 
            WHERE emr_mode IN ('pediatric', 'mixed')
            UNION ALL
            SELECT 
                'MMR' as vaccine_type,
                COUNT(CASE WHEN ror_date IS NOT NULL THEN 1 END) as completed,
                COUNT(*) as total
            FROM Patients 
            WHERE emr_mode IN ('pediatric', 'mixed')
        """)
        completion_rates = cursor.fetchall()
        
        return render_template('vaccine_tracking.html',
                             title='Vaccine Tracking Dashboard',
                             current_mode=current_mode,
                             stats=stats,
                             recent_vaccines=recent_vaccines,
                             incomplete_vaccinations=incomplete_vaccinations,
                             completion_rates=completion_rates)
                             
    except Exception as e:
        current_app.logger.error(f"Error in vaccine tracking dashboard: {e}")
        flash(f'Error loading vaccine tracking data: {str(e)}', 'danger')
        return redirect(url_for('index'))

@vaccine_bp.route('/search')
def vaccine_search():
    """Search for patients by vaccine status"""
    current_mode = emr_config.get_emr_mode()
    
    if not emr_config.should_show_vaccines():
        flash('Vaccine tracking is not enabled for the current EMR mode.', 'warning')
        return redirect(url_for('index'))
    
    search_term = request.args.get('q', '').strip()
    vaccine_type = request.args.get('vaccine_type', 'all')
    status = request.args.get('status', 'all')  # completed, incomplete, missing
    
    db = get_db()
    results = []
    
    if search_term:
        try:
            # Build search query based on parameters
            base_query = """
                SELECT DISTINCT
                    p.id,
                    p.first_name || ' ' || p.last_name as patient_name,
                    p.mrn,
                    p.date_of_birth,
                    p.dtcp1_date, p.dtcp2_date, p.dtcp3_date,
                    p.hep_b1_date, p.hep_b2_date, p.hep_b3_date,
                    p.hib1_date, p.hib2_date, p.hib3_date,
                    p.ror_date, p.rougeole_seule_date
                FROM Patients p
                LEFT JOIN NonStandardVaccines nsv ON p.id = nsv.patient_id
                WHERE p.emr_mode IN ('pediatric', 'mixed')
                AND (p.first_name LIKE ? OR p.last_name LIKE ? OR p.mrn LIKE ? OR nsv.vaccine_name LIKE ?)
            """
            
            search_pattern = f"%{search_term}%"
            params = [search_pattern, search_pattern, search_pattern, search_pattern]
            
            # Add vaccine type filter if specified
            if vaccine_type != 'all':
                if vaccine_type == 'dtcp':
                    base_query += " AND (p.dtcp1_date IS NOT NULL OR p.dtcp2_date IS NOT NULL OR p.dtcp3_date IS NOT NULL)"
                elif vaccine_type == 'hepatitis_b':
                    base_query += " AND (p.hep_b1_date IS NOT NULL OR p.hep_b2_date IS NOT NULL OR p.hep_b3_date IS NOT NULL)"
                elif vaccine_type == 'hib':
                    base_query += " AND (p.hib1_date IS NOT NULL OR p.hib2_date IS NOT NULL OR p.hib3_date IS NOT NULL)"
                elif vaccine_type == 'mmr':
                    base_query += " AND (p.ror_date IS NOT NULL OR p.rougeole_seule_date IS NOT NULL)"
            
            base_query += " ORDER BY p.first_name, p.last_name LIMIT 50"
            
            cursor = db.execute(base_query, params)
            results = cursor.fetchall()
            
        except Exception as e:
            current_app.logger.error(f"Error in vaccine search: {e}")
            flash(f'Error searching vaccines: {str(e)}', 'danger')
    
    return render_template('vaccine_search.html',
                         title='Vaccine Search',
                         current_mode=current_mode,
                         search_term=search_term,
                         vaccine_type=vaccine_type,
                         status=status,
                         results=results)

@vaccine_bp.route('/api/statistics')
def api_vaccine_statistics():
    """API endpoint for vaccine statistics"""
    if not emr_config.should_show_vaccines():
        return jsonify({'error': 'Vaccines not enabled'}), 400
    
    try:
        db = get_db()
        
        # Get monthly vaccine additions for chart
        cursor = db.execute("""
            SELECT 
                strftime('%Y-%m', created_date) as month,
                COUNT(*) as count
            FROM NonStandardVaccines
            WHERE created_date >= DATE('now', '-12 months')
            GROUP BY strftime('%Y-%m', created_date)
            ORDER BY month
        """)
        monthly_data = cursor.fetchall()
        
        # Get vaccine type distribution
        cursor = db.execute("""
            SELECT 
                vaccine_name,
                COUNT(*) as count
            FROM NonStandardVaccines
            GROUP BY vaccine_name
            ORDER BY count DESC
            LIMIT 10
        """)
        vaccine_distribution = cursor.fetchall()
        
        return jsonify({
            'monthly_additions': [dict(row) for row in monthly_data],
            'vaccine_distribution': [dict(row) for row in vaccine_distribution]
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in vaccine statistics API: {e}")
        return jsonify({'error': str(e)}), 500

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
            return redirect(url_for('vaccine.edit_standard_vaccine_form', patient_id=patient_id, field_name=field_name))

    try:
        db.execute(f"UPDATE Patients SET {field_name} = ? WHERE id = ?", (vaccine_date, patient_id))
        db.commit()
        flash(f'Vaccine updated successfully.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating vaccine: {e}', 'danger')
    
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
    """Display color-coded vaccine schedule timeline for a patient"""
    db = get_db()
    
    try:
        # Get patient data
        cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
        patient_row = cursor.fetchone()
        
        if not patient_row:
            flash(f'Patient with ID {patient_id} not found.', 'warning')
            return redirect(url_for('patient.list_patients'))
        
        patient = dict(patient_row)
        
        # Check if patient has date of birth
        patient_dob = patient.get('naissance_date')
        if not patient_dob:
            flash('Patient must have a date of birth to view vaccine schedule.', 'warning')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))
        
        # Get patient's vaccine data (non-standard vaccines)
        vaccine_cursor = db.execute("SELECT * FROM NonStandardVaccines WHERE patient_id = ?", (patient_id,))
        autres_vaccins = vaccine_cursor.fetchall()
        
        # Prepare patient vaccine dictionary for the schedule engine
        patient_vaccines = dict(patient)
        
        # Calculate vaccine timeline with both standard and non-standard vaccine data
        timeline = get_patient_vaccine_timeline(patient_dob, patient_vaccines, autres_vaccins)
        
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

