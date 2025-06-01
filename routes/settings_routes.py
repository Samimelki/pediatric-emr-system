from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from database import get_custom_demographic_fields, add_custom_demographic_field, set_custom_field_active_status
import os
import json
from werkzeug.utils import secure_filename
from routes.pdf_export_routes import load_pdf_config, clear_pdf_config_cache, DEFAULT_PDF_CONFIG
from datetime import datetime
import shutil
from config_manager import save_config, load_config, USER_MEDIA_FOLDER

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

# Allowed extension for signature image
ALLOWED_SIGNATURE_EXTENSIONS = {'png'}
SIGNATURE_FILENAME = "signature_stamp.png" # Fixed filename for the signature

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@settings_bp.route('/pdf', methods=['GET', 'POST'])
def manage_pdf_settings():
    config_path = os.path.join(current_app.root_path, 'pdf_config.json')
    user_media_folder = current_app.config['USER_MEDIA_FOLDER']

    if request.method == 'POST':
        current_config = load_pdf_config(force_reload=True) # Load fresh before modifying
        
        # Update physician details and footers
        for lang_key in ['fr', 'en']:
            current_config[f'physician_details_{lang_key}'] = {
                "name": request.form.get(f'physician_name_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['name']),
                "specialty": request.form.get(f'physician_specialty_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['specialty']),
                "hospital_name": request.form.get(f'physician_hospital_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['hospital_name']),
                "faculty_name": request.form.get(f'physician_faculty_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['faculty_name']),
                "contact_line1": request.form.get(f'physician_contact1_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['contact_line1']),
                "contact_line2": request.form.get(f'physician_contact2_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['contact_line2'])
            }
            current_config[f'footer_note_{lang_key}'] = request.form.get(f'footer_note_{lang_key}', DEFAULT_PDF_CONFIG[f'footer_note_{lang_key}'])

        # Handle signature image upload
        if 'signature_image' in request.files:
            file = request.files['signature_image']
            if file and file.filename != '' and allowed_file(file.filename, ALLOWED_SIGNATURE_EXTENSIONS):
                # filename = secure_filename(file.filename) # We'll use a fixed name
                save_path = os.path.join(user_media_folder, SIGNATURE_FILENAME)
                try:
                    file.save(save_path)
                    current_config['signature_image_filename'] = SIGNATURE_FILENAME
                    flash('Signature image uploaded successfully.', 'success')
                except Exception as e:
                    flash(f'Error saving signature image: {e}', 'danger')
            elif file.filename != '': # File was selected but not allowed type
                flash(f'Invalid file type for signature. Only PNG is allowed.', 'danger')
        
        # Handle signature image removal
        if request.form.get('remove_signature_image') == '1':
            current_signature_file = current_config.get('signature_image_filename', '')
            if current_signature_file:
                file_to_delete = os.path.join(user_media_folder, current_signature_file)
                if os.path.exists(file_to_delete):
                    try:
                        os.remove(file_to_delete)
                        flash('Signature image removed.', 'success')
                    except Exception as e:
                        flash(f'Error removing signature image file: {e}', 'danger')
                else:
                    flash('Signature image file not found for removal, but config cleared.', 'info')
                current_config['signature_image_filename'] = ''

        # Save updated config
        try:
            with open(config_path, 'w', encoding='utf-8') as f_save:
                json.dump(current_config, f_save, indent=4, ensure_ascii=False)
            clear_pdf_config_cache() # Important to clear cache so next load gets fresh data
            flash('PDF settings updated successfully.', 'success')
        except Exception as e:
            flash(f'Error saving PDF settings: {e}', 'danger')
        
        return redirect(url_for('settings.manage_pdf_settings'))

    # GET request: Load current config and display form
    current_config = load_pdf_config()
    signature_image_url = None
    cache_buster = None # Initialize cache_buster
    if current_config.get('signature_image_filename'):
        user_media_folder = current_app.config['USER_MEDIA_FOLDER'] # Define here for GET path
        potential_path = os.path.join(user_media_folder, current_config['signature_image_filename'])
        if os.path.exists(potential_path):
            signature_image_url = url_for('settings.get_user_media_file', filename=current_config['signature_image_filename'])
            # Use datetime from the standard library for timestamp
            cache_buster = datetime.now().timestamp()

    return render_template('settings/pdf_settings.html', 
                           title='PDF Export Settings', 
                           config=current_config, 
                           default_config=DEFAULT_PDF_CONFIG,
                           signature_image_url=signature_image_url,
                           cache_buster=cache_buster) # Pass cache_buster

# Route to serve files from USER_MEDIA_FOLDER (e.g., signature image for preview on settings page)
@settings_bp.route('/user_media/<path:filename>')
def get_user_media_file(filename):
    return send_from_directory(current_app.config['USER_MEDIA_FOLDER'], filename)

@settings_bp.route('/custom_fields', methods=['GET', 'POST'])
def manage_custom_fields():
    if request.method == 'POST':
        field_label = request.form.get('field_label')
        field_name_suggestion = request.form.get('field_name_suggestion')
        
        selected_section_option = request.form.get('display_section_select')
        raw_display_section = ''

        if selected_section_option == '_other_':
            raw_display_section = request.form.get('other_display_section', '').strip()
            if not raw_display_section: # If other is selected, the text input must not be empty
                flash('Name for \"Other\" section cannot be empty if selected.', 'danger')
                # To repopulate form correctly, ideally pass back current form values
                custom_fields = get_custom_demographic_fields()
                return render_template('settings/custom_fields.html', 
                                       title='Manage Custom Fields', 
                                       custom_fields=custom_fields,
                                       form_error=True, # Indicate error to potentially prefill form
                                       field_label_val=field_label,
                                       field_name_suggestion_val=field_name_suggestion,
                                       display_section_select_val=selected_section_option,
                                       other_display_section_val=raw_display_section)
        else:
            raw_display_section = selected_section_option # This will be one of the predefined like "Demographics", "Additional Information", etc.
        
        # Standardize the section name
        display_section_to_save = ''
        if not raw_display_section: # Should ideally be caught by _other_ check or have a default from select
            display_section_to_save = 'Additional Information' 
        elif raw_display_section.lower() == 'demographics':
            display_section_to_save = 'Demographics'
        elif raw_display_section.lower() == 'birth history':
            display_section_to_save = 'Birth History'
        elif raw_display_section.lower() in ['contact & admin details', 'contact and admin details', 'admin details', 'contact details']:
            display_section_to_save = 'Contact & Admin Details'
        elif raw_display_section == 'Additional Information': # Explicitly from dropdown
             display_section_to_save = 'Additional Information'
        else: # For _other_ or any new direct value not matching above (e.g. if JS disabled and _other_ was submitted directly)
            display_section_to_save = raw_display_section.title()

        if not field_label or not field_name_suggestion:
            flash('Field Label and Field Name Suggestion are required.', 'danger')
        else:
            success, message = add_custom_demographic_field(field_label, field_name_suggestion, display_section=display_section_to_save)
            if success:
                flash(message, 'success')
            else:
                flash(message, 'danger')
        return redirect(url_for('settings.manage_custom_fields'))

    # For GET request
    custom_fields = get_custom_demographic_fields()
    return render_template('settings/custom_fields.html', title='Manage Custom Fields', custom_fields=custom_fields)

@settings_bp.route('/custom_fields/<int:field_id>/toggle_active', methods=['POST'])
def toggle_custom_field_active(field_id):
    # Determine the new status: if current is True, new is False, and vice-versa.
    # We need to fetch the field to see its current status first.
    # This is a bit inefficient. A better way might be to pass the desired new status from the form,
    # or have two separate routes like /activate and /deactivate.
    # For now, let's fetch. We assume get_custom_demographic_fields() returns a list of Row objects.
    all_fields = get_custom_demographic_fields() # This gets all fields, including their active status
    field_to_toggle = None
    for field in all_fields:
        if field['id'] == field_id:
            field_to_toggle = field
            break
    
    if not field_to_toggle:
        flash(f"Custom field with ID {field_id} not found.", 'danger')
        return redirect(url_for('settings.manage_custom_fields'))

    new_status = not field_to_toggle['is_active']
    success, message = set_custom_field_active_status(field_id, new_status)

    if success:
        flash(f"Custom field '{field_to_toggle['field_label']}' has been {'activated' if new_status else 'deactivated'}.", 'success')
    else:
        flash(message, 'danger')
    return redirect(url_for('settings.manage_custom_fields'))

@settings_bp.route('/storage', methods=['GET', 'POST'])
def storage_settings():
    if request.method == 'POST':
        storage_type = request.form.get('storage_type', 'local')
        cloud_path = request.form.get('cloud_path')
        
        # Load current config
        config = load_config()
        
        # If switching to cloud storage, move the database and Word documents
        if storage_type != 'local' and config['storage_type'] == 'local':
            try:
                # Create new paths in cloud storage
                new_db_path = os.path.join(cloud_path, 'word_docs_emr.db')
                new_word_docs_path = os.path.join(cloud_path, 'word_documents')
                
                # Copy database to new location
                shutil.copy2(current_app.config['DATABASE'], new_db_path)
                
                # Copy Word documents to new location
                if os.path.exists(config['word_docs_folder']):
                    if not os.path.exists(new_word_docs_path):
                        os.makedirs(new_word_docs_path)
                    for filename in os.listdir(config['word_docs_folder']):
                        if filename.endswith('.docx'):
                            shutil.copy2(
                                os.path.join(config['word_docs_folder'], filename),
                                os.path.join(new_word_docs_path, filename)
                            )
                
                # Update config
                config['database_path'] = new_db_path
                config['storage_type'] = storage_type
                config['cloud_path'] = cloud_path
                config['word_docs_folder'] = new_word_docs_path
                
                if save_config(config):
                    flash('Successfully moved database and Word documents to cloud storage', 'success')
                else:
                    flash('Failed to save configuration', 'danger')
                    return redirect(url_for('settings.storage_settings'))
                
            except Exception as e:
                flash(f'Error moving files to cloud storage: {str(e)}', 'danger')
                return redirect(url_for('settings.storage_settings'))
        
        # If switching to local storage, move files back
        elif storage_type == 'local' and config['storage_type'] != 'local':
            try:
                # Create new paths in local storage
                new_db_path = os.path.join(os.path.dirname(current_app.config['DATABASE']), 'word_docs_emr.db')
                new_word_docs_path = os.path.join(os.path.dirname(current_app.config['DATABASE']), 'word_documents')
                
                # Copy database to new location
                shutil.copy2(config['database_path'], new_db_path)
                
                # Copy Word documents to new location
                if os.path.exists(config['word_docs_folder']):
                    if not os.path.exists(new_word_docs_path):
                        os.makedirs(new_word_docs_path)
                    for filename in os.listdir(config['word_docs_folder']):
                        if filename.endswith('.docx'):
                            shutil.copy2(
                                os.path.join(config['word_docs_folder'], filename),
                                os.path.join(new_word_docs_path, filename)
                            )
                
                # Update config
                config['database_path'] = new_db_path
                config['storage_type'] = storage_type
                config['cloud_path'] = None
                config['word_docs_folder'] = new_word_docs_path
                
                if save_config(config):
                    flash('Successfully moved database and Word documents to local storage', 'success')
                else:
                    flash('Failed to save configuration', 'danger')
                    return redirect(url_for('settings.storage_settings'))
                
            except Exception as e:
                flash(f'Error moving files to local storage: {str(e)}', 'danger')
                return redirect(url_for('settings.storage_settings'))
        
        # Update storage type and cloud path
        config['storage_type'] = storage_type
        config['cloud_path'] = cloud_path if storage_type != 'local' else None
        
        if save_config(config):
            flash('Storage settings updated successfully', 'success')
        else:
            flash('Failed to save configuration', 'danger')
    
    # Load current config for display
    config = load_config()
    return render_template('settings/storage.html',
                         storage_type=config['storage_type'],
                         cloud_path=config['cloud_path'])

@settings_bp.route('/personalization', methods=['GET', 'POST'])
def personalization_settings():
    config = load_config()
    if request.method == 'POST':
        config['emr_name'] = request.form.get('emr_name', 'GARBIS EMR')

        # Handle background image upload
        file = request.files.get('background_image')
        if file and file.filename:
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext in allowed_extensions:
                filename = f"background_image.{ext}"
                save_path = os.path.join(USER_MEDIA_FOLDER, filename)
                file.save(save_path)
                config['background_image_filename'] = filename
            else:
                flash('Invalid file type for background image. Allowed: png, jpg, jpeg, gif.', 'danger')

        if save_config(config):
            flash('Personalization settings updated successfully', 'success')
        else:
            flash('Failed to save configuration', 'danger')
        return redirect(url_for('settings.personalization_settings'))
    return render_template('settings/personalization.html', title='Personalization Settings', config=config) 