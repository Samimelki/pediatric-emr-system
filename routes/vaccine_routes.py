from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from database import get_db
from emr_config import emr_config, EMRMode
from statistics_engine.statistics_calculator import calculate_average_vaccines_per_child
import sqlite3

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