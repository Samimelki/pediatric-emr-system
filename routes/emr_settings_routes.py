from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from emr_config import emr_config, AVAILABLE_FEATURES
from database import get_db
from datetime import datetime
import json

emr_settings_bp = Blueprint('emr_settings', __name__, url_prefix='/emr-settings')

@emr_settings_bp.route('/')
def emr_configuration():
    """Legacy EMR configuration page - redirect to profile settings."""
    return redirect(url_for('emr_settings.profile_settings'))

@emr_settings_bp.route('/profile-settings')
def profile_settings():
    """New profile-based settings page"""
    # Get current profile information
    active_profile_name = emr_config.get_active_profile_name()
    current_profile = emr_config.get_active_profile()
    all_profiles = emr_config.get_all_profiles()
    enabled_features = emr_config.get_enabled_features()
    feature_categories = emr_config.get_feature_categories()
    
    # Get practice information
    practice_info = emr_config.get_practice_info()
    
    return render_template('emr_profile_settings.html',
                         active_profile_name=active_profile_name,
                         current_profile=current_profile,
                         profiles=all_profiles,
                         enabled_features=enabled_features,
                         available_features=AVAILABLE_FEATURES,
                         feature_categories=feature_categories,
                         practice_name=practice_info.get('name', 'Medical Practice'))

@emr_settings_bp.route('/switch-profile', methods=['POST'])
def switch_profile():
    """Switch to a different profile"""
    try:
        profile_name = request.form.get('profile_name')
        
        if not profile_name:
            flash('No profile selected', 'danger')
            return redirect(url_for('emr_settings.profile_settings'))
        
        old_profile = emr_config.get_active_profile_name()
        
        if emr_config.set_active_profile(profile_name):
            # Log the change
            _log_configuration_change(old_profile, profile_name, 'profile_switch', 
                                    request.form.get('reason', 'User switched profile'))
            flash(f'Switched to profile: {profile_name}', 'success')
        else:
            flash('Profile not found', 'danger')
            
    except Exception as e:
        print(f"Error switching profile: {e}")
        flash('Error switching profile', 'danger')
    
    return redirect(url_for('emr_settings.profile_settings'))

@emr_settings_bp.route('/update-profile', methods=['POST'])
def update_profile():
    """Update an existing profile"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        features = data.get('features', {})
        
        if not profile_name:
            return jsonify({'success': False, 'message': 'Profile name required'})
        
        # Get current profile and update features
        current_profile = emr_config.get_all_profiles().get(profile_name, {})
        current_profile['features'] = features
        
        if emr_config.update_profile(profile_name, current_profile):
            # Log the change
            enabled_count = sum(1 for enabled in features.values() if enabled)
            _log_configuration_change(None, None, 'profile_update', 
                                    f'Updated {profile_name}: {enabled_count} features enabled')
            return jsonify({'success': True, 'message': 'Profile updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update profile'})
            
    except Exception as e:
        print(f"Error updating profile: {e}")
        return jsonify({'success': False, 'message': str(e)})

@emr_settings_bp.route('/create-profile', methods=['POST'])
def create_profile():
    """Create a new profile"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        
        if not profile_name:
            return jsonify({'success': False, 'message': 'Profile name required'})
            
        # Check if profile already exists
        if profile_name in emr_config.get_all_profiles():
            return jsonify({'success': False, 'message': 'Profile name already exists'})
        
        # Create profile data structure
        profile_data = {
            'name': data.get('name', profile_name),
            'description': data.get('description', 'Custom profile'),
            'features': data.get('features', {}),
            'settings': data.get('settings', {
                'weight_unit_preference': 'auto',
                'language': 'en',
                'show_percentiles': True,
                'require_visit_notes': True
            })
        }
        
        if emr_config.create_profile(profile_name, profile_data):
            # Log the change
            enabled_count = sum(1 for enabled in profile_data['features'].values() if enabled)
            _log_configuration_change(None, None, 'profile_create', 
                                    f'Created {profile_name}: {enabled_count} features enabled')
            return jsonify({'success': True, 'message': 'Profile created successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to create profile'})
            
    except Exception as e:
        print(f"Error creating profile: {e}")
        return jsonify({'success': False, 'message': str(e)})

@emr_settings_bp.route('/delete-profile', methods=['POST'])
def delete_profile():
    """Delete a profile"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        
        if not profile_name:
            return jsonify({'success': False, 'message': 'Profile name required'})
        
        if emr_config.delete_profile(profile_name):
            # Log the change
            _log_configuration_change(None, None, 'profile_delete', 
                                    f'Deleted profile: {profile_name}')
            return jsonify({'success': True, 'message': 'Profile deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Cannot delete default profiles or profile not found'})
            
    except Exception as e:
        print(f"Error deleting profile: {e}")
        return jsonify({'success': False, 'message': str(e)})

@emr_settings_bp.route('/api/profile-statistics')
def profile_statistics():
    """API endpoint for profile usage statistics."""
    try:
        db = get_db()
        
        # Get current profile info
        active_profile = emr_config.get_active_profile_name()
        enabled_features = emr_config.get_enabled_features()
        
        # Patient counts (legacy - we'll maintain for compatibility)
        cursor = db.execute("""
            SELECT 
                COALESCE(emr_mode, 'unknown') as mode,
                COUNT(*) as count 
            FROM Patients 
            GROUP BY emr_mode
        """)
        patient_stats = {row['mode']: row['count'] for row in cursor.fetchall()}
        
        # Visit counts
        cursor = db.execute("""
            SELECT 
                COUNT(*) as total_visits,
                COUNT(DISTINCT patient_id) as unique_patients
            FROM Visits 
            WHERE visit_date >= DATE('now', '-30 days')
        """)
        recent_activity = cursor.fetchone()
        
        return jsonify({
            'success': True,
            'active_profile': active_profile,
            'enabled_features_count': len(enabled_features),
            'patient_stats': patient_stats,
            'recent_activity': {
                'total_visits': recent_activity['total_visits'],
                'unique_patients': recent_activity['unique_patients']
            }
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
        
        # Check for missing visit data where features are enabled
        if emr_config.is_feature_enabled('weight_tracking'):
            cursor = db.execute("""
                SELECT COUNT(*) as count FROM Visits 
                WHERE weight_g IS NULL
            """)
            missing_weights = cursor.fetchone()['count']
            if missing_weights > 0:
                issues.append(f"{missing_weights} visits missing weight data")
        
        return jsonify({
            'success': True,
            'issues': issues,
            'total_issues': len(issues)
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
            'export_date': datetime.now().isoformat(),
            'active_profile': emr_config.get_active_profile_name(),
            'profiles': emr_config.get_all_profiles(),
            'practice_info': emr_config.get_practice_info(),
            'version': '2.0.0'
        }
        
        response = jsonify(config_data)
        response.headers['Content-Disposition'] = 'attachment; filename=emr_config_export.json'
        return response
        
    except Exception as e:
        flash(f'Error exporting configuration: {str(e)}', 'danger')
        return redirect(url_for('emr_settings.profile_settings'))

@emr_settings_bp.route('/import-config', methods=['POST'])
def import_configuration():
    """Import EMR configuration from uploaded file."""
    try:
        if 'config_file' not in request.files:
            flash('No configuration file uploaded.', 'danger')
            return redirect(url_for('emr_settings.profile_settings'))
        
        file = request.files['config_file']
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('emr_settings.profile_settings'))
        
        if not file.filename.endswith('.json'):
            flash('Configuration file must be a JSON file.', 'danger')
            return redirect(url_for('emr_settings.profile_settings'))
        
        # Parse JSON
        try:
            config_data = json.loads(file.read().decode('utf-8'))
        except json.JSONDecodeError as e:
            flash(f'Invalid JSON file: {str(e)}', 'danger')
            return redirect(url_for('emr_settings.profile_settings'))
        
        # Validate required keys
        required_keys = ['active_profile', 'profiles', 'version']
        for key in required_keys:
            if key not in config_data:
                flash(f'Invalid configuration file: missing {key}', 'danger')
                return redirect(url_for('emr_settings.profile_settings'))
        
        # Import profiles
        old_profile = emr_config.get_active_profile_name()
        
        # Import each profile
        for profile_name, profile_data in config_data['profiles'].items():
            if profile_name not in emr_config.get_all_profiles():
                emr_config.create_profile(profile_name, profile_data)
            else:
                emr_config.update_profile(profile_name, profile_data)
        
        # Set active profile
        if config_data['active_profile'] in config_data['profiles']:
            emr_config.set_active_profile(config_data['active_profile'])
        
        # Log the change
        _log_configuration_change(old_profile, config_data['active_profile'], 'config_import', 
                                f"Imported configuration with {len(config_data['profiles'])} profiles")
        
        flash(f'Configuration imported successfully! Imported {len(config_data["profiles"])} profiles.', 'success')
        
    except Exception as e:
        flash(f'Error importing configuration: {str(e)}', 'danger')
    
    return redirect(url_for('emr_settings.profile_settings'))

def _log_configuration_change(old_value, new_value, change_type, reason):
    """Log configuration changes for audit trail."""
    try:
        db = get_db()
        db.execute("""
            INSERT INTO ConfigurationChanges 
            (change_date, old_value, new_value, change_type, changed_by, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            str(old_value) if old_value else None,
            str(new_value) if new_value else None,
            change_type,
            'system',  # Could be enhanced to track actual user
            reason
        ))
        db.commit()
    except Exception as e:
        print(f"Error logging configuration change: {e}")
        # Don't fail the main operation if logging fails 