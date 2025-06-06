from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from emr_config import emr_config, EMRMode
from database import get_db

emr_settings_bp = Blueprint('emr_settings', __name__, url_prefix='/emr-settings')

@emr_settings_bp.route('/')
def emr_configuration():
    """Main EMR configuration page."""
    current_mode = emr_config.get_emr_mode()
    current_features = emr_config.get_enabled_features()
    
    # Get patient counts by mode for statistics
    db = get_db()
    stats = {}
    try:
        cursor = db.execute("SELECT emr_mode, COUNT(*) as count FROM Patients GROUP BY emr_mode")
        for row in cursor.fetchall():
            stats[row['emr_mode']] = row['count']
    except:
        stats = {'adult': 0, 'pediatric': 0, 'mixed': 0}
    
    return render_template('emr_configuration.html',
                         title='EMR Configuration',
                         current_mode=current_mode,
                         current_features=current_features,
                         emr_modes=EMRMode,
                         patient_stats=stats)

@emr_settings_bp.route('/mode', methods=['POST'])
def set_emr_mode():
    """Set the EMR operating mode."""
    try:
        mode_str = request.form.get('emr_mode')
        if not mode_str:
            flash('No EMR mode specified.', 'danger')
            return redirect(url_for('emr_settings.emr_configuration'))
        
        # Validate mode
        try:
            new_mode = EMRMode(mode_str)
        except ValueError:
            flash(f'Invalid EMR mode: {mode_str}', 'danger')
            return redirect(url_for('emr_settings.emr_configuration'))
        
        # Record configuration change
        old_mode = emr_config.get_emr_mode()
        
        # Set new mode
        emr_config.set_emr_mode(new_mode)
        
        # Log the change
        _log_configuration_change(old_mode, new_mode, 'emr_mode', request.form.get('reason', ''))
        
        # Success message
        mode_names = {
            EMRMode.ADULT: 'Adult EMR',
            EMRMode.PEDIATRIC: 'Pediatric EMR',
            EMRMode.MIXED: 'Mixed Mode (Adult + Pediatric)'
        }
        
        flash(f'EMR mode changed to: {mode_names[new_mode]}', 'success')
        
    except Exception as e:
        flash(f'Error changing EMR mode: {str(e)}', 'danger')
    
    return redirect(url_for('emr_settings.emr_configuration'))

@emr_settings_bp.route('/features', methods=['POST'])
def update_features():
    """Update EMR feature toggles."""
    try:
        # Get current features
        current_features = emr_config.get_enabled_features()
        
        # Update features based on form data
        features_data = {}
        
        # Feature toggles
        features_data['vaccines_enabled'] = 'vaccines_enabled' in request.form
        features_data['growth_charts_enabled'] = 'growth_charts_enabled' in request.form
        features_data['vitals_tracking_enabled'] = 'vitals_tracking_enabled' in request.form
        features_data['document_management_enabled'] = 'document_management_enabled' in request.form
        features_data['statistics_reports_enabled'] = 'statistics_reports_enabled' in request.form
        features_data['custom_fields_enabled'] = 'custom_fields_enabled' in request.form
        
        # UI preferences
        features_data['multi_language_support'] = 'multi_language_support' in request.form
        features_data['simplified_interface'] = 'simplified_interface' in request.form
        
        # Update configuration
        emr_config.update_features(features_data)
        
        # Log the change
        changed_features = []
        for key, value in features_data.items():
            if getattr(current_features, key, False) != value:
                changed_features.append(f"{key}: {'enabled' if value else 'disabled'}")
        
        if changed_features:
            _log_configuration_change(None, None, 'features', 
                                    f"Changed: {', '.join(changed_features)}")
        
        flash('EMR features updated successfully!', 'success')
        
    except Exception as e:
        flash(f'Error updating features: {str(e)}', 'danger')
    
    return redirect(url_for('emr_settings.emr_configuration'))

@emr_settings_bp.route('/api/mode-statistics')
def mode_statistics():
    """API endpoint for EMR mode statistics."""
    try:
        db = get_db()
        
        # Patient counts by mode
        cursor = db.execute("""
            SELECT 
                COALESCE(emr_mode, 'unknown') as mode,
                COUNT(*) as count 
            FROM Patients 
            GROUP BY emr_mode
        """)
        patient_stats = {row['mode']: row['count'] for row in cursor.fetchall()}
        
        # Visit counts by mode (via patient)
        cursor = db.execute("""
            SELECT 
                COALESCE(p.emr_mode, 'unknown') as mode,
                COUNT(v.id) as count 
            FROM Visits v
            LEFT JOIN Patients p ON v.patient_id = p.id
            GROUP BY p.emr_mode
        """)
        visit_stats = {row['mode']: row['count'] for row in cursor.fetchall()}
        
        # Recent activity
        cursor = db.execute("""
            SELECT 
                p.emr_mode,
                DATE(v.visit_date) as visit_date,
                COUNT(*) as visits_count
            FROM Visits v
            LEFT JOIN Patients p ON v.patient_id = p.id
            WHERE v.visit_date >= DATE('now', '-30 days')
            GROUP BY p.emr_mode, DATE(v.visit_date)
            ORDER BY visit_date DESC
        """)
        recent_activity = cursor.fetchall()
        
        return jsonify({
            'success': True,
            'patient_stats': patient_stats,
            'visit_stats': visit_stats,
            'recent_activity': [dict(row) for row in recent_activity]
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@emr_settings_bp.route('/validate-migration')
def validate_migration():
    """Validate that data migration was successful."""
    try:
        db = get_db()
        
        # Check for data consistency
        issues = []
        
        # Check for patients with missing core information
        cursor = db.execute("""
            SELECT COUNT(*) as count FROM Patients 
            WHERE (first_name IS NULL OR first_name = '') 
            AND (prenom IS NULL OR prenom = '')
        """)
        missing_names = cursor.fetchone()['count']
        if missing_names > 0:
            issues.append(f"{missing_names} patients missing names")
        
        # Check for orphaned visits
        cursor = db.execute("""
            SELECT COUNT(*) as count FROM Visits v
            LEFT JOIN Patients p ON v.patient_id = p.id
            WHERE p.id IS NULL
        """)
        orphaned_visits = cursor.fetchone()['count']
        if orphaned_visits > 0:
            issues.append(f"{orphaned_visits} orphaned visits found")
        
        # Check for mode mismatches
        cursor = db.execute("""
            SELECT COUNT(*) as count FROM Patients 
            WHERE emr_mode IS NULL OR emr_mode = ''
        """)
        missing_modes = cursor.fetchone()['count']
        if missing_modes > 0:
            issues.append(f"{missing_modes} patients missing EMR mode")
        
        return jsonify({
            'success': True,
            'issues': issues,
            'valid': len(issues) == 0
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@emr_settings_bp.route('/export-config')
def export_configuration():
    """Export current EMR configuration."""
    try:
        config_data = {
            'emr_mode': emr_config.get_emr_mode().value,
            'features': emr_config.get_enabled_features()._asdict(),
            'export_timestamp': emr_config.datetime.now().isoformat(),
            'version': '1.0'
        }
        
        response = jsonify(config_data)
        response.headers['Content-Disposition'] = 'attachment; filename=emr_config_export.json'
        return response
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@emr_settings_bp.route('/import-config', methods=['POST'])
def import_configuration():
    """Import EMR configuration from file."""
    try:
        if 'config_file' not in request.files:
            flash('No configuration file provided.', 'danger')
            return redirect(url_for('emr_settings.emr_configuration'))
        
        file = request.files['config_file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('emr_settings.emr_configuration'))
        
        if not file.filename.endswith('.json'):
            flash('Configuration file must be a JSON file.', 'danger')
            return redirect(url_for('emr_settings.emr_configuration'))
        
        # Parse configuration
        import json
        config_data = json.load(file)
        
        # Validate structure
        required_keys = ['emr_mode', 'features', 'version']
        if not all(key in config_data for key in required_keys):
            flash('Invalid configuration file format.', 'danger')
            return redirect(url_for('emr_settings.emr_configuration'))
        
        # Apply configuration
        old_mode = emr_config.get_emr_mode()
        
        # Set mode
        new_mode = EMRMode(config_data['emr_mode'])
        emr_config.set_emr_mode(new_mode)
        
        # Set features
        emr_config.update_features(config_data['features'])
        
        # Log the change
        _log_configuration_change(old_mode, new_mode, 'import', 
                                f"Imported from file: {file.filename}")
        
        flash('Configuration imported successfully!', 'success')
        
    except Exception as e:
        flash(f'Error importing configuration: {str(e)}', 'danger')
    
    return redirect(url_for('emr_settings.emr_configuration'))

def _log_configuration_change(old_mode, new_mode, change_type, reason):
    """Log configuration changes to the database."""
    try:
        db = get_db()
        
        # Prepare change data
        features_changed = None
        if change_type == 'features':
            features_changed = reason
        elif change_type == 'import':
            features_changed = reason
        
        # Insert audit record
        db.execute("""
            INSERT INTO ConfigurationAudit 
            (change_date, emr_mode_from, emr_mode_to, features_changed, changed_by, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            emr_config.datetime.now().isoformat(),
            old_mode.value if old_mode else None,
            new_mode.value if new_mode else None,
            features_changed,
            'system',  # Could be enhanced to track actual user
            reason
        ))
        
        db.commit()
        
    except Exception as e:
        print(f"Error logging configuration change: {e}")
        # Don't fail the main operation if logging fails
        pass 