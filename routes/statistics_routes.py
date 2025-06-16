from flask import Blueprint, render_template, Response, current_app, jsonify, request
import csv
import io
from statistics_engine.statistics_calculator import (
    calculate_percentiles, 
    find_measurement_outliers, 
    calculate_average_vaccines_per_child,
    EXPECTED_PERCENTILES_STATS
)
import emr_config
from database import get_db

statistics_bp = Blueprint('statistics', __name__, template_folder='../templates')

def get_statistics_data():
    """Calculate statistics on demand"""
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    
    try:
        # Calculate average vaccines
        avg_vaccines = calculate_average_vaccines_per_child(db_path=db_path)
        
        # Calculate percentiles
        percentiles = calculate_percentiles(
            db_path=db_path,
            target_percentiles=[3, 15, 50, 85, 97],
            smoothing_window=6,  # Increased from 3 to 6 months for smoother curves
            max_age_months=228,
            outlier_filter_sd_threshold=5.0,
            min_points_for_outlier_filtering=10
        )
        
        # Find outliers
        outliers = find_measurement_outliers(
            db_path=db_path,
            std_dev_threshold=4.0,
            age_limit_months=60
        )
        
        return {
            'avg_vaccines': avg_vaccines,
            'percentiles': percentiles,
            'outliers': outliers,
            'success': True
        }
    except Exception as e:
        current_app.logger.error(f"Error calculating statistics: {e}")
        return {
            'avg_vaccines': 0,
            'percentiles': None,
            'outliers': [],
            'success': False,
            'error': str(e)
        }

@statistics_bp.route('/statistics')
def statistics_overview():
    """Statistics overview page"""
    stats = get_statistics_data()
    return render_template('statistics_overview.html', 
                         stats_ready=stats['success'],
                         avg_vaccines=stats['avg_vaccines'],
                         percentiles=stats['percentiles'],
                         outliers=stats['outliers'])

@statistics_bp.route('/statistics/outliers')
@statistics_bp.route('/statistics/outliers/<int:page>')
def statistics_outliers(page=None):
    """Outliers page showing measurement outliers with pagination and raw text"""
    from flask import request
    
    # Get page from URL parameter or query string
    if page is None:
        page = request.args.get('page', 1, type=int)
    
    stats = get_statistics_data()
    
    if not stats['success']:
        return render_template('statistics_outliers.html', 
                             outliers=[], 
                             stats_ready=False, 
                             error_message=f"Error calculating statistics: {stats.get('error', 'Unknown error')}")

    # Pagination settings
    per_page = 50
    total_outliers = len(stats['outliers'])
    total_pages = (total_outliers + per_page - 1) // per_page  # Ceiling division
    
    # Ensure page is within valid range
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    # Calculate start and end indices
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    # Get outliers for current page
    page_outliers = stats['outliers'][start_idx:end_idx]
    
    # Enhance outliers with raw dossier text and all measurements
    db = get_db()
    enhanced_outliers = []
    
    for outlier in page_outliers:
        # Get raw dossier text for this patient
        cursor = db.execute("SELECT raw_dossier_text FROM Patients WHERE id = ?", (outlier['patient_id'],))
        patient_data = cursor.fetchone()
        
        enhanced_outlier = dict(outlier)
        enhanced_outlier['raw_dossier_text'] = patient_data['raw_dossier_text'] if patient_data else None
        
        # Extract relevant visit text and all measurements for this outlier
        # Always try to extract measurements, regardless of raw_dossier_text
        visit_info = extract_visit_with_all_measurements(
            enhanced_outlier['raw_dossier_text'], 
            outlier['value'], 
            outlier['measurement_type'],
            outlier['patient_id']
        )
        enhanced_outlier['relevant_visit_text'] = visit_info['visit_text']
        enhanced_outlier['parsed_measurements'] = visit_info['measurements']
        enhanced_outlier['visit_date'] = visit_info['visit_date']
            
        enhanced_outliers.append(enhanced_outlier)
    
    # Pagination info
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_outliers,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_num': page - 1 if page > 1 else None,
        'next_num': page + 1 if page < total_pages else None,
        'start_idx': start_idx + 1,  # 1-based for display
        'end_idx': min(end_idx, total_outliers)
    }

    return render_template('statistics_outliers.html', 
                         outliers=enhanced_outliers, 
                         stats_ready=True,
                         pagination=pagination)

def extract_visit_with_all_measurements(raw_dossier_text, target_value, measurement_type, patient_id):
    """Extract the visit text that contains the outlier and show all measurements from that visit"""
    import re
    from database import get_db
    
    # Get the actual stored measurements from the database for this patient
    db = get_db()
    cursor = db.execute("""
        SELECT visit_date, weight_g, height_cm, head_circumference_cm, raw_visit_entry
        FROM Visits 
        WHERE patient_id = ? 
        ORDER BY visit_date
    """, (patient_id,))
    
    stored_visits = cursor.fetchall()
    
    # Find the visit that contains our target outlier value
    target_visit = None
    
    # First pass: Look for exact matches with increased tolerance
    for stored_visit in stored_visits:
        if measurement_type == 'Weight (kg)' and stored_visit['weight_g']:
            weight_kg = stored_visit['weight_g'] / 1000
            # For weights, also check if the raw grams value matches the target kg value
            # This handles cases where 87g is stored but outlier shows as 87kg
            if (abs(weight_kg - target_value) < 0.1 or 
                abs(stored_visit['weight_g'] - target_value) < 1):  # 87g matches 87kg outlier
                target_visit = stored_visit
                break
        elif measurement_type == 'Height (cm)' and stored_visit['height_cm']:
            if abs(stored_visit['height_cm'] - target_value) < 0.5:
                target_visit = stored_visit
                break
        elif measurement_type == 'Head Circ. (cm)' and stored_visit['head_circumference_cm']:
            if abs(stored_visit['head_circumference_cm'] - target_value) < 0.5:
                target_visit = stored_visit
                break
    
    # Second pass: If no exact match, look for the problematic value in any field
    # This handles data entry errors where height was entered as weight, etc.
    if not target_visit:
        for stored_visit in stored_visits:
            # Check if the target value appears in any measurement field
            weight_kg = stored_visit['weight_g'] / 1000 if stored_visit['weight_g'] else 0
            height_cm = stored_visit['height_cm'] if stored_visit['height_cm'] else 0
            hc_cm = stored_visit['head_circumference_cm'] if stored_visit['head_circumference_cm'] else 0
            
            # Check if target value matches any measurement (allowing for unit confusion)
            if (abs(weight_kg - target_value) < 0.1 or  # Normal weight match
                abs(stored_visit['weight_g'] - target_value) < 1 or  # Grams vs kg confusion
                abs(height_cm - target_value) < 0.5 or  # Height match
                abs(hc_cm - target_value) < 0.5):  # HC match
                target_visit = stored_visit
                break
    
    # Third pass: If still no match, look for visits with unusual values that could be data entry errors
    if not target_visit and measurement_type == 'Weight (kg)':
        for stored_visit in stored_visits:
            if stored_visit['weight_g']:
                weight_kg = stored_visit['weight_g'] / 1000
                # Look for weights that are clearly wrong (too high for pediatric patients)
                if weight_kg > 50:  # Clearly wrong for most pediatric patients
                    target_visit = stored_visit
                    break
                # Or very small weights that might be data entry errors
                elif weight_kg < 0.5:  # Less than 500g, likely data entry error
                    target_visit = stored_visit
                    break
    
    if not target_visit:
        # If still no match found, return structure indicating the issue
        return {
            'visit_text': f'Could not locate visit with {measurement_type} = {target_value}',
            'measurements': {
                'weight_kg': None,
                'height_cm': None,
                'head_circumference_cm': None,
                'raw_measurement_string': f'Target value {target_value} not found in any visit'
            },
            'visit_date': None
        }
    
    # Use the raw_visit_entry directly from the target visit
    visit_date = target_visit['visit_date']
    relevant_visit_text = target_visit['raw_visit_entry'] if target_visit['raw_visit_entry'] else None
    
    # If no raw_visit_entry, try to extract from raw_dossier_text as fallback
    if not relevant_visit_text and raw_dossier_text:
        visit_date_obj = None
        try:
            from datetime import datetime
            visit_date_obj = datetime.fromisoformat(visit_date.split('T')[0])
            visit_date_short = visit_date_obj.strftime('%d-%m-%y')
        except:
            visit_date_short = None
        
        # Find the raw text for this visit
        if visit_date_short:
            # Look for this specific date in the raw dossier text
            visit_pattern = rf'\*{re.escape(visit_date_short)}\*\s*([^\*]+?)(?=\*\d{{2}}-\d{{2}}-\d{{2}}\*|$)'
            match = re.search(visit_pattern, raw_dossier_text, re.DOTALL)
            if match:
                relevant_visit_text = f"*{visit_date_short}* {match.group(1).strip()}"
    
    # Prepare the measurements data - always include all fields, use None for missing values
    stored_measurements = {
        'weight_kg': target_visit['weight_g'] / 1000 if target_visit['weight_g'] else None,
        'height_cm': target_visit['height_cm'] if target_visit['height_cm'] else None,
        'head_circumference_cm': target_visit['head_circumference_cm'] if target_visit['head_circumference_cm'] else None,
        'raw_measurement_string': target_visit['raw_visit_entry'] if target_visit['raw_visit_entry'] else 'No raw text available'
    }
    
    return {
        'visit_text': relevant_visit_text if relevant_visit_text else f'Visit on {visit_date.split("T")[0] if visit_date else "unknown date"}',
        'measurements': stored_measurements,
        'visit_date': visit_date.split('T')[0] if visit_date else None
    }

@statistics_bp.route('/statistics/update_measurement', methods=['POST'])
def update_measurement():
    """Update a measurement value for an outlier"""
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        measurement_type = data.get('measurement_type')
        old_value = float(data.get('old_value'))
        new_value = float(data.get('new_value'))
        
        if not all([patient_id, measurement_type, old_value is not None, new_value is not None]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        db = get_db()
        
        # First, update the visit record
        if measurement_type == 'Weight (kg)':
            # Convert kg back to grams for storage
            old_value_g = int(old_value * 1000)
            new_value_g = int(new_value * 1000)
            
            cursor = db.execute("""
                UPDATE Visits 
                SET weight_g = ? 
                WHERE patient_id = ? AND weight_g = ?
            """, (new_value_g, patient_id, old_value_g))
            
        elif measurement_type == 'Height (cm)':
            cursor = db.execute("""
                UPDATE Visits 
                SET height_cm = ? 
                WHERE patient_id = ? AND height_cm = ?
            """, (new_value, patient_id, old_value))
            
        elif measurement_type == 'Head Circ. (cm)':
            cursor = db.execute("""
                UPDATE Visits 
                SET head_circumference_cm = ? 
                WHERE patient_id = ? AND head_circumference_cm = ?
            """, (new_value, patient_id, old_value))
        else:
            return jsonify({'success': False, 'error': 'Unknown measurement type'})
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'error': 'No matching record found to update'})
        
        # Also update the raw dossier text to reflect the change
        try:
            update_raw_dossier_text(db, patient_id, measurement_type, old_value, new_value)
        except Exception as e:
            current_app.logger.warning(f"Could not update raw dossier text: {e}")
            # Don't fail the whole operation if raw text update fails
        
        db.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Updated {measurement_type} from {old_value} to {new_value} for patient {patient_id}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error updating measurement: {e}")
        return jsonify({'success': False, 'error': str(e)})

def update_raw_dossier_text(db, patient_id, measurement_type, old_value, new_value):
    """Update the raw dossier text to reflect the measurement change"""
    import re
    
    # Get current raw dossier text
    cursor = db.execute("SELECT raw_dossier_text FROM Patients WHERE id = ?", (patient_id,))
    patient_data = cursor.fetchone()
    
    if not patient_data or not patient_data['raw_dossier_text']:
        return
    
    raw_text = patient_data['raw_dossier_text']
    
    # Find and replace the measurement in the raw text
    # This is a best-effort approach - we'll look for measurement patterns
    visit_pattern = r'(\*\d{2}-\d{2}-\d{2}\*\s*)([^\*]+?)(?=\*\d{2}-\d{2}-\d{2}\*|$)'
    
    def replace_measurement_in_visit(match):
        date_part = match.group(1)
        visit_content = match.group(2)
        
        # Look for measurement patterns like "5500/58/39.3"
        measurement_pattern = r'(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*(?:/\d+(?:\.\d+)?)*)'
        measurements = re.findall(measurement_pattern, visit_content)
        
        for measurement in measurements:
            parts = measurement.split('/')
            
            # Check if this measurement contains our target value and update it
            if measurement_type == 'Weight (kg)' and len(parts) >= 1:
                try:
                    weight_value = float(parts[0])
                    # Check if this matches our old value (in grams)
                    if abs(weight_value - old_value * 1000) < 1:  # Allow for rounding
                        new_measurement = measurement.replace(parts[0], str(int(new_value * 1000)), 1)
                        visit_content = visit_content.replace(measurement, new_measurement, 1)
                        break
                except ValueError:
                    continue
                    
            elif measurement_type == 'Height (cm)' and len(parts) >= 2:
                try:
                    height_value = float(parts[1])
                    if abs(height_value - old_value) < 0.01:
                        new_measurement = measurement.replace(parts[1], str(new_value), 1)
                        visit_content = visit_content.replace(measurement, new_measurement, 1)
                        break
                except ValueError:
                    continue
                    
            elif measurement_type == 'Head Circ. (cm)' and len(parts) >= 3:
                try:
                    hc_value = float(parts[2])
                    if abs(hc_value - old_value) < 0.01:
                        new_measurement = measurement.replace(parts[2], str(new_value), 1)
                        visit_content = visit_content.replace(measurement, new_measurement, 1)
                        break
                except ValueError:
                    continue
        
        return date_part + visit_content
    
    # Apply the replacement
    updated_text = re.sub(visit_pattern, replace_measurement_in_visit, raw_text, flags=re.DOTALL)
    
    # Update the database
    db.execute("UPDATE Patients SET raw_dossier_text = ? WHERE id = ?", (updated_text, patient_id))

@statistics_bp.route('/statistics/download_csv')
def download_csv():
    """Download statistics as CSV with UTF-8 BOM for proper French character display"""
    stats = get_statistics_data()
    
    if not stats['success'] or not stats['percentiles']:
        return "Statistics not available", 404
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(['Measurement', 'Sex', 'Age_Months', 'P3', 'P15', 'P50', 'P85', 'P97'])
    
    # Write data for each measurement type
    for measurement_name, measurement_data in stats['percentiles'].items():
        if measurement_data:
            for sex in ['boys', 'girls']:
                if sex in measurement_data:
                    sex_data = measurement_data[sex]
                    if 'Month' in sex_data:
                        for i, age_months in enumerate(sex_data['Month']):
                            row = [measurement_name, sex, age_months]
                            for percentile in ['P3', 'P15', 'P50', 'P85', 'P97']:
                                if percentile in sex_data and i < len(sex_data[percentile]):
                                    row.append(sex_data[percentile][i])
                                else:
                                    row.append('')
                            writer.writerow(row)
    
    # Add UTF-8 BOM for proper French character display in Excel
    csv_content = '\ufeff' + output.getvalue()
    output.close()
    
    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=growth_statistics.csv'}
    )

@statistics_bp.route('/statistics/get_percentiles_csv_data/<measurement_type>/<sex>')
def get_percentiles_csv_data(measurement_type, sex):
    """Generate CSV data for percentiles with UTF-8 BOM for proper French character display"""
    if measurement_type not in ['wfa', 'lhfa', 'hcfa'] or sex not in ['boys', 'girls']:
        return jsonify({"error": "Invalid parameters"}), 400

    stats = get_statistics_data()
    
    if not stats['success'] or not stats['percentiles']:
        return jsonify({"error": "Could not calculate statistics"}), 503

    local_percentiles_all = stats['percentiles']
    
    if not local_percentiles_all or \
       measurement_type not in local_percentiles_all or \
       sex not in local_percentiles_all[measurement_type]:
        return jsonify({"error": "Data not found for the selection."}), 404

    data_to_process = local_percentiles_all[measurement_type][sex]

    if not data_to_process or 'Month' not in data_to_process or not data_to_process['Month']:
        return jsonify({"error": "No percentile data available for this selection."}), 404

    output = io.StringIO()
    writer = csv.writer(output)
    percentile_keys = [f"P{p}" for p in EXPECTED_PERCENTILES_STATS]
    header = ['Month'] + percentile_keys
    writer.writerow(header)
    
    num_months = len(data_to_process['Month'])
    for i in range(num_months):
        row = [data_to_process['Month'][i]]
        for p_key in percentile_keys:
            row.append(data_to_process.get(p_key, [])[i] if i < len(data_to_process.get(p_key, [])) else 'N/A')
        writer.writerow(row)
    
    # Add UTF-8 BOM for proper French character display in Excel
    csv_string = '\ufeff' + output.getvalue()
    output.close()
    
    filename = f"local_percentiles_{measurement_type}_{sex}.csv"
    return jsonify({"filename": filename, "csv_data": csv_string})

@statistics_bp.route('/statistics/get_percentile_data/<measurement_type>/<sex>')
def get_percentile_chart_data(measurement_type, sex):
    """Get percentile data for chart rendering"""
    if measurement_type not in ['wfa', 'lhfa', 'hcfa'] or sex not in ['boys', 'girls']:
        return jsonify({"error": "Invalid parameters"}), 400

    stats = get_statistics_data()
    
    if not stats['success'] or not stats['percentiles']:
        return jsonify({"error": "Could not calculate statistics"}), 503

    local_percentiles_all = stats['percentiles']
    
    if not local_percentiles_all or \
       measurement_type not in local_percentiles_all or \
       sex not in local_percentiles_all[measurement_type] or \
       not local_percentiles_all[measurement_type][sex].get('Month'):
        return jsonify({"error": "Data not found for the selection."}), 404

    data_for_chart = local_percentiles_all[measurement_type][sex]
    return jsonify(data_for_chart)

@statistics_bp.route('/statistics/debug')
def debug_statistics():
    """Debug endpoint to check statistics cache"""
    from flask import current_app
    
    with current_app.statistics_lock:
        cache_info = {
            'calculating': current_app.statistics_cache['calculating'],
            'has_percentiles': bool(current_app.statistics_cache['percentiles']),
            'percentiles_type': str(type(current_app.statistics_cache['percentiles'])),
            'percentiles_keys': list(current_app.statistics_cache['percentiles'].keys()) if current_app.statistics_cache['percentiles'] else None,
            'has_outliers': bool(current_app.statistics_cache['outliers']),
            'last_updated': str(current_app.statistics_cache['last_updated'])
        }
    
    return jsonify(cache_info)

@statistics_bp.route('/statistics/update_all_measurements', methods=['POST'])
def update_all_measurements():
    """Update all measurements for a specific visit"""
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        visit_date = data.get('visit_date')
        weight_kg = data.get('weight_kg')
        height_cm = data.get('height_cm')
        head_circumference_cm = data.get('head_circumference_cm')
        
        if not all([patient_id, visit_date]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        db = get_db()
        
        # Convert weight from kg to grams for storage
        weight_g = int(weight_kg * 1000) if weight_kg is not None else None
        
        # Update the visit record
        cursor = db.execute("""
            UPDATE Visits 
            SET weight_g = ?, height_cm = ?, head_circumference_cm = ?
            WHERE patient_id = ? AND visit_date LIKE ?
        """, (weight_g, height_cm, head_circumference_cm, patient_id, f"{visit_date}%"))
        
        if cursor.rowcount == 0:
            return jsonify({'success': False, 'error': 'No matching visit found to update'})
        
        # Also update the raw dossier text to reflect the changes
        try:
            update_raw_dossier_text_all_measurements(db, patient_id, visit_date, weight_kg, height_cm, head_circumference_cm)
        except Exception as e:
            current_app.logger.warning(f"Could not update raw dossier text: {e}")
            # Don't fail the whole operation if raw text update fails
        
        db.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Updated all measurements for patient {patient_id} on {visit_date}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Error updating all measurements: {e}")
        return jsonify({'success': False, 'error': str(e)})

def update_raw_dossier_text_all_measurements(db, patient_id, visit_date, weight_kg, height_cm, head_circumference_cm):
    """Update the raw dossier text to reflect all measurement changes"""
    import re
    
    # Get current raw dossier text
    cursor = db.execute("SELECT raw_dossier_text FROM Patients WHERE id = ?", (patient_id,))
    patient_data = cursor.fetchone()
    
    if not patient_data or not patient_data['raw_dossier_text']:
        return
    
    raw_text = patient_data['raw_dossier_text']
    
    # Convert visit date to the format used in raw text (dd-mm-yy)
    from datetime import datetime
    visit_dt = datetime.strptime(visit_date, '%Y-%m-%d')
    visit_date_short = visit_dt.strftime('%d-%m-%y')
    
    # Find and replace the measurement in the raw text for this specific date
    visit_pattern = rf'(\*{re.escape(visit_date_short)}\*\s*)([^\*]+?)(?=\*\d{{2}}-\d{{2}}-\d{{2}}\*|$)'
    
    def replace_visit_measurements(match):
        date_part = match.group(1)
        visit_content = match.group(2)
        
        # Look for measurement patterns like "5500/58/39.3"
        measurement_pattern = r'(\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*(?:/\d+(?:\.\d+)?)*)'
        
        # Build new measurement string
        new_measurements = []
        if weight_kg is not None:
            new_measurements.append(str(int(weight_kg * 1000)))  # Convert to grams
        if height_cm is not None:
            new_measurements.append(str(height_cm))
        if head_circumference_cm is not None:
            new_measurements.append(str(head_circumference_cm))
        
        if new_measurements:
            new_measurement_string = '/'.join(new_measurements)
            
            # Replace the first measurement pattern in the visit
            new_visit_content = re.sub(measurement_pattern, new_measurement_string, visit_content, count=1)
            return date_part + new_visit_content
        
        return match.group(0)  # Return unchanged if no measurements
    
    # Apply the replacement
    updated_text = re.sub(visit_pattern, replace_visit_measurements, raw_text, flags=re.DOTALL)
    
    # Update the database
    db.execute("UPDATE Patients SET raw_dossier_text = ? WHERE id = ?", (updated_text, patient_id)) 