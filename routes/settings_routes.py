from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from database import get_custom_demographic_fields, add_custom_demographic_field, set_custom_field_active_status
import os
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import shutil
from emr_config import USER_MEDIA_FOLDER

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

# Allowed extension for signature image
ALLOWED_SIGNATURE_EXTENSIONS = {'png'}
SIGNATURE_FILENAME = "signature_stamp.png" # Fixed filename for the signature

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg'} # Combined for logo and signature

def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

@settings_bp.route('/pdf', methods=['GET', 'POST'])
def manage_pdf_settings():
    # Use emr_config instance
    from emr_config import emr_config
    
    pdf_settings = emr_config.get_pdf_settings()
    
    # Default PDF config structure for fallback
    DEFAULT_PDF_CONFIG = {
        "physician_details_fr": {
            "name": "Dr. Votre Nom",
            "specialty": "Votre Spécialité",
            "hospital_name": "Nom de l'Hôpital/Clinique",
            "faculty_name": "Nom de la Faculté/Université",
            "contact_line1": "Ligne de contact 1",
            "contact_line2": "Ligne de contact 2"
        },
        "physician_details_en": {
            "name": "Dr. Your Name",
            "specialty": "Your Specialty",
            "hospital_name": "Hospital/Clinic Name",
            "faculty_name": "Faculty/University Name",
            "contact_line1": "Contact Line 1",
            "contact_line2": "Contact Line 2"
        },
        "footer_note_fr": "Note de bas de page",
        "footer_note_en": "Footer note",
        "signature_image_filename": None,
        "report_title_fr": "Rapport Médical Complet",
        "report_title_en": "Complete Medical Report",
        "logo_image_filename": None,
        "footer_alignment": "center"
    }

    if request.method == 'POST':
        # Update physician details and footers
        for lang_key in ['fr', 'en']:
            pdf_settings[f'physician_details_{lang_key}'] = {
                "name": request.form.get(f'physician_name_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['name']),
                "specialty": request.form.get(f'physician_specialty_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['specialty']),
                "hospital_name": request.form.get(f'physician_hospital_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['hospital_name']),
                "faculty_name": request.form.get(f'physician_faculty_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['faculty_name']),
                "contact_line1": request.form.get(f'physician_contact1_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['contact_line1']),
                "contact_line2": request.form.get(f'physician_contact2_{lang_key}', DEFAULT_PDF_CONFIG[f'physician_details_{lang_key}']['contact_line2'])
            }
            pdf_settings[f'footer_note_{lang_key}'] = request.form.get(f'footer_note_{lang_key}', DEFAULT_PDF_CONFIG[f'footer_note_{lang_key}'])

        # Update Report Titles
        pdf_settings['report_title_en'] = request.form.get('report_title_en', DEFAULT_PDF_CONFIG['report_title_en'])
        pdf_settings['report_title_fr'] = request.form.get('report_title_fr', DEFAULT_PDF_CONFIG['report_title_fr'])

        # Update footer alignment
        pdf_settings['footer_alignment'] = request.form.get('footer_alignment', DEFAULT_PDF_CONFIG.get('footer_alignment', 'center'))

        # Handle Logo Image
        if request.form.get('remove_logo') == 'true':
            old_logo_filename = pdf_settings.get('logo_image_filename')
            if old_logo_filename:
                try:
                    os.remove(os.path.join(USER_MEDIA_FOLDER, old_logo_filename))
                    flash('Logo image removed.', 'success')
                except OSError as e:
                    flash(f'Error removing logo image file: {e}', 'danger')
            pdf_settings['logo_image_filename'] = None
        elif 'logo_image' in request.files:
            file = request.files['logo_image']
            if file and file.filename != '' and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                # Remove old logo if it exists
                old_logo_filename = pdf_settings.get('logo_image_filename')
                if old_logo_filename:
                    try:
                        os.remove(os.path.join(USER_MEDIA_FOLDER, old_logo_filename))
                    except OSError:
                        pass
                
                # Ensure USER_MEDIA_FOLDER exists
                if not os.path.exists(USER_MEDIA_FOLDER):
                    os.makedirs(USER_MEDIA_FOLDER, exist_ok=True)
                
                ext = file.filename.rsplit('.', 1)[1].lower()
                new_logo_filename = f"logo_image.{ext}"
                try:
                    file.save(os.path.join(USER_MEDIA_FOLDER, new_logo_filename))
                    pdf_settings['logo_image_filename'] = new_logo_filename
                    flash('Logo image uploaded successfully.', 'success')
                except Exception as e:
                    flash(f'Error saving logo image: {e}', 'danger')
            elif file.filename != '':
                flash(f'Invalid file type for logo. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}', 'danger')

        # Handle Signature Image
        if request.form.get('remove_signature') == 'true':
            old_sig_filename = pdf_settings.get('signature_image_filename')
            if old_sig_filename:
                try:
                    os.remove(os.path.join(USER_MEDIA_FOLDER, old_sig_filename))
                    flash('Signature image removed.', 'success')
                except OSError as e:
                    flash(f'Error removing signature image file: {e}', 'danger')
            pdf_settings['signature_image_filename'] = None
        elif 'signature_image' in request.files:
            file = request.files['signature_image']
            if file and file.filename != '' and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                old_sig_filename = pdf_settings.get('signature_image_filename')
                if old_sig_filename:
                    try:
                        os.remove(os.path.join(USER_MEDIA_FOLDER, old_sig_filename))
                    except OSError:
                        pass
                
                # Ensure USER_MEDIA_FOLDER exists
                if not os.path.exists(USER_MEDIA_FOLDER):
                    os.makedirs(USER_MEDIA_FOLDER, exist_ok=True)
                
                ext = file.filename.rsplit('.', 1)[1].lower()
                new_sig_filename = f"signature_stamp.{ext}"
                try:
                    file.save(os.path.join(USER_MEDIA_FOLDER, new_sig_filename))
                    pdf_settings['signature_image_filename'] = new_sig_filename
                    flash('Signature image uploaded successfully.', 'success')
                except Exception as e:
                    flash(f'Error saving signature image: {e}', 'danger')
            elif file.filename != '':
                 flash(f'Invalid file type for signature. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}', 'danger')

        # Update the config with new PDF settings
        emr_config.config['pdf_settings'] = pdf_settings
        if emr_config.save_config():
            flash('PDF settings updated successfully.', 'success')
        else:
            flash('Error saving PDF settings.', 'danger')
        
        return redirect(url_for('settings.manage_pdf_settings'))

    # GET request: Load current config and display form
    signature_image_url = None
    logo_image_url = None
    cache_buster = str(datetime.now().timestamp())

    if pdf_settings.get('signature_image_filename'):
        if os.path.exists(os.path.join(USER_MEDIA_FOLDER, pdf_settings['signature_image_filename'])):
            signature_image_url = url_for('settings.get_user_media_file', filename=pdf_settings['signature_image_filename']) + "?v=" + cache_buster

    if pdf_settings.get('logo_image_filename'):
        if os.path.exists(os.path.join(USER_MEDIA_FOLDER, pdf_settings['logo_image_filename'])):
            logo_image_url = url_for('settings.get_user_media_file', filename=pdf_settings['logo_image_filename']) + "?v=" + cache_buster
    
    return render_template('settings/pdf_settings.html', 
                           title='PDF Export Settings', 
                           config=emr_config.config,
                           pdf_settings=pdf_settings,
                           default_pdf_config=DEFAULT_PDF_CONFIG,
                           signature_image_url=signature_image_url,
                           logo_image_url=logo_image_url)

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
    # Use emr_config for both legacy and new functionality
    from emr_config import emr_config
    
    config = load_config()  # Legacy config for backward compatibility
    
    if request.method == 'POST':
        # Update EMR name using new system
        emr_name = request.form.get('emr_name', 'EMR')
        emr_config.set_emr_name(emr_name)
        config['emr_name'] = emr_name  # Also update legacy config

        # Handle background image upload
        file = request.files.get('background_image')
        if file and file.filename:
            print(f"DEBUG: Processing background image upload: {file.filename}")
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext in allowed_extensions:
                # Ensure USER_MEDIA_FOLDER exists
                print(f"DEBUG: USER_MEDIA_FOLDER path: {USER_MEDIA_FOLDER}")
                if not os.path.exists(USER_MEDIA_FOLDER):
                    os.makedirs(USER_MEDIA_FOLDER, exist_ok=True)
                    print(f"DEBUG: Created user media folder: {USER_MEDIA_FOLDER}")
                
                filename = f"background_image.{ext}"
                save_path = os.path.join(USER_MEDIA_FOLDER, filename)
                print(f"DEBUG: Saving background image to: {save_path}")
                try:
                    file.save(save_path)
                    emr_config.set_background_image_filename(filename)  # New system
                    config['background_image_filename'] = filename  # Legacy system
                    print(f"DEBUG: Background image saved successfully: {filename}")
                    flash('Background image uploaded successfully.', 'success')
                except Exception as e:
                    print(f"DEBUG: Error saving background image: {e}")
                    flash(f'Error saving background image: {e}', 'danger')
            else:
                flash('Invalid file type for background image. Allowed: png, jpg, jpeg, gif.', 'danger')

        if save_config(config):
            flash('Personalization settings updated successfully', 'success')
        else:
            flash('Failed to save configuration', 'danger')
        return redirect(url_for('settings.personalization_settings'))
    
    # For GET request, ensure config has current values from new system
    config['emr_name'] = emr_config.get_emr_name()
    config['background_image_filename'] = emr_config.get_background_image_filename()
    
    return render_template('settings/personalization.html', title='Personalization Settings', config=config) 