import os
import json # Add json for handling pdf_config.json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, Response, g as flask_g # Added g as flask_g
from werkzeug.utils import secure_filename
# from db_setup import setup_database # Removed: Schema is initialized in app.py
from datetime import datetime # For timestamp in backup filename
import io # For in-memory zip file for CSV export
import zipfile # For creating zip files for CSV export
import shutil # For database restore
import glob

# Import PDF config functions from pdf_export_routes
from routes.pdf_export_routes import load_pdf_config, clear_pdf_config_cache, DEFAULT_PDF_CONFIG

# Import for XML Export & DB Management
from database import get_all_patient_data_for_export, get_active_custom_demographic_fields, close_connection as close_db_connection_util # Added get_active_custom_demographic_fields for CSV and db close util
from xml_exporter import generate_patient_xml
from csv_exporter import generate_patient_csvs # Added for CSV Export
from word_importer import WordDocumentImporter

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

ALLOWED_DB_EXTENSIONS = {'db', 'sqlite', 'sqlite3'}

def allowed_db_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_DB_EXTENSIONS

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'xml'})

@admin_bp.route('/import_xml', methods=['GET', 'POST'])
def import_xml_data():
    if request.method == 'POST':
        files = request.files.getlist('docxfile')
        confirm_replace = request.form.get('confirm_replace')
        full_replace = request.form.get('full_replace')
        if not confirm_replace:
            flash('You must confirm that you understand the data will be replaced or appended.', 'danger')
            return redirect(request.url)
        docx_paths = []
        if files and any(f.filename for f in files):
            # Ensure UPLOAD_FOLDER exists
            upload_folder = current_app.config['UPLOAD_FOLDER']
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder, exist_ok=True)
            
            for file in files:
                if file and file.filename.lower().endswith('.docx'):
                    filename = secure_filename(file.filename)
                    temp_docx_path = os.path.join(upload_folder, filename)
                    file.save(temp_docx_path)
                    docx_paths.append(temp_docx_path)
        else:
            flash('No Word documents were selected.', 'danger')
            return redirect(request.url)
        if not docx_paths:
            flash('No valid Word documents found.', 'danger')
            return redirect(request.url)
        db_path = current_app.config['DATABASE']
        if full_replace:
            if os.path.exists(db_path):
                os.remove(db_path)
                flash('Existing database file removed for fresh import.', 'info')
            from database import init_db_schema
            with current_app.app_context():
                init_db_schema()

        # Use WordDocumentImporter to parse the documents
        importer = WordDocumentImporter(db_path)
        results = importer.import_batch(docx_paths)
        total_success = sum(1 for _, success, _ in results if success)
        total_fail = sum(1 for _, success, _ in results if not success)
        for filename, success, msg in results:
            flash(f"{filename}: {'Success' if success else 'Failed'} - {msg}", 'info' if success else 'danger')
        flash(f'Import complete: {total_success} succeeded, {total_fail} failed.', 'success' if total_fail == 0 else 'warning')
        
        # Clean up temp files
        for docx_file in docx_paths:
            if os.path.exists(docx_file) and docx_file.startswith(current_app.config['UPLOAD_FOLDER']):
                os.remove(docx_file)
        return redirect(url_for('admin.import_xml_data'))
    return render_template('import_xml.html', current_db_path=current_app.config['DATABASE'], upload_folder=current_app.config['UPLOAD_FOLDER'])

@admin_bp.route('/settings', methods=['GET', 'POST'])
def pdf_settings():
    config_path = os.path.join(current_app.root_path, 'pdf_config.json')

    if request.method == 'POST':
        try:
            current_config = load_pdf_config(force_reload=True) # Load current or default
            
            # Update French details
            current_config['physician_details_fr']['name'] = request.form.get('physician_name_fr', DEFAULT_PDF_CONFIG['physician_details_fr']['name'])
            current_config['physician_details_fr']['specialty'] = request.form.get('physician_specialty_fr', DEFAULT_PDF_CONFIG['physician_details_fr']['specialty'])
            current_config['physician_details_fr']['hospital_name'] = request.form.get('physician_hospital_fr', DEFAULT_PDF_CONFIG['physician_details_fr']['hospital_name'])
            current_config['physician_details_fr']['faculty_name'] = request.form.get('physician_faculty_fr', DEFAULT_PDF_CONFIG['physician_details_fr']['faculty_name'])
            current_config['physician_details_fr']['contact_line1'] = request.form.get('physician_contact1_fr', DEFAULT_PDF_CONFIG['physician_details_fr']['contact_line1'])
            current_config['physician_details_fr']['contact_line2'] = request.form.get('physician_contact2_fr', DEFAULT_PDF_CONFIG['physician_details_fr']['contact_line2'])
            current_config['footer_note_fr'] = request.form.get('footer_note_fr', DEFAULT_PDF_CONFIG['footer_note_fr'])

            # Update English details
            current_config['physician_details_en']['name'] = request.form.get('physician_name_en', DEFAULT_PDF_CONFIG['physician_details_en']['name'])
            current_config['physician_details_en']['specialty'] = request.form.get('physician_specialty_en', DEFAULT_PDF_CONFIG['physician_details_en']['specialty'])
            current_config['physician_details_en']['hospital_name'] = request.form.get('physician_hospital_en', DEFAULT_PDF_CONFIG['physician_details_en']['hospital_name'])
            current_config['physician_details_en']['faculty_name'] = request.form.get('physician_faculty_en', DEFAULT_PDF_CONFIG['physician_details_en']['faculty_name'])
            current_config['physician_details_en']['contact_line1'] = request.form.get('physician_contact1_en', DEFAULT_PDF_CONFIG['physician_details_en']['contact_line1'])
            current_config['physician_details_en']['contact_line2'] = request.form.get('physician_contact2_en', DEFAULT_PDF_CONFIG['physician_details_en']['contact_line2'])
            current_config['footer_note_en'] = request.form.get('footer_note_en', DEFAULT_PDF_CONFIG['footer_note_en'])

            # Update Arabic details
            current_config['physician_details_ar']['name'] = request.form.get('physician_name_ar', DEFAULT_PDF_CONFIG['physician_details_ar']['name'])
            current_config['physician_details_ar']['specialty'] = request.form.get('physician_specialty_ar', DEFAULT_PDF_CONFIG['physician_details_ar']['specialty'])
            current_config['physician_details_ar']['hospital_name'] = request.form.get('physician_hospital_ar', DEFAULT_PDF_CONFIG['physician_details_ar']['hospital_name'])
            current_config['physician_details_ar']['faculty_name'] = request.form.get('physician_faculty_ar', DEFAULT_PDF_CONFIG['physician_details_ar']['faculty_name'])
            current_config['physician_details_ar']['contact_line1'] = request.form.get('physician_contact1_ar', DEFAULT_PDF_CONFIG['physician_details_ar']['contact_line1'])
            current_config['physician_details_ar']['contact_line2'] = request.form.get('physician_contact2_ar', DEFAULT_PDF_CONFIG['physician_details_ar']['contact_line2'])
            current_config['footer_note_ar'] = request.form.get('footer_note_ar', DEFAULT_PDF_CONFIG['footer_note_ar'])

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(current_config, f, indent=4, ensure_ascii=False)
            
            clear_pdf_config_cache() # Clear the cache after saving
            flash('PDF settings saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving PDF settings: {str(e)}', 'danger')
        return redirect(url_for('admin.pdf_settings'))

    # For GET request
    config_data = load_pdf_config(force_reload=True) # Force reload to get latest from file or defaults
    return render_template('settings.html', config=config_data)

@admin_bp.route('/download_db')
def download_db():
    try:
        db_path = current_app.config['DATABASE']
        if not os.path.exists(db_path):
            flash("Database file not found.", "danger")
            return redirect(url_for('main.index')) # Or wherever appropriate
        
        # Generate a filename with a timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"emr_database_backup_{timestamp}.db"
        
        return send_file(db_path, as_attachment=True, download_name=backup_filename, mimetype='application/octet-stream')
    except Exception as e:
        current_app.logger.error(f"Error during database download: {e}")
        flash(f"An error occurred while trying to download the database: {e}", "danger")
        return redirect(url_for('main.index')) # Or admin dashboard or settings page 

@admin_bp.route('/export_xml_data')
def export_xml_data_route():
    try:
        all_data = get_all_patient_data_for_export()
        if not all_data:
            flash("No patient data found to export.", "info")
            # Decide where to redirect: back to referring page or a specific admin/tools page
            return redirect(request.referrer or url_for('main.index')) 

        xml_string = generate_patient_xml(all_data)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        xml_filename = f"pediatric_emr_export_{timestamp}.xml"
        
        return Response(
            xml_string,
            mimetype="application/xml",
            headers={"Content-Disposition": f"attachment;filename={xml_filename}"}
        )
    except Exception as e:
        current_app.logger.error(f"Error during XML export: {e}")
        flash(f"An error occurred while generating the XML export: {e}", "danger")
        return redirect(request.referrer or url_for('main.index')) 

@admin_bp.route('/export_csv_data')
def export_csv_data_route():
    try:
        all_data = get_all_patient_data_for_export()
        active_custom_fields = get_active_custom_demographic_fields()

        if not all_data:
            flash("No patient data found to export as CSV.", "info")
            return redirect(request.referrer or url_for('main.index'))

        csv_files_dict = generate_patient_csvs(all_data, active_custom_fields)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED, False) as zip_file: # Use 'w' for new zip
            for filename, content in csv_files_dict.items():
                zip_file.writestr(filename, content.encode('utf-8'))
        zip_buffer.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"pediatric_emr_csv_export_{timestamp}.zip"

        return Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={"Content-Disposition": f"attachment;filename={zip_filename}"}
        )
    except Exception as e:
        current_app.logger.error(f"Error during CSV export: {e}", exc_info=True)
        flash(f"An error occurred while generating the CSV export: {e}", "danger")
        return redirect(request.referrer or url_for('main.index')) 

@admin_bp.route('/manage_database', methods=['GET', 'POST'])
def manage_database_route():
    if request.method == 'POST':
        if 'restore_db_file' not in request.files:
            flash('No file part for database restore.', 'danger')
            return redirect(request.url)
        file = request.files['restore_db_file']
        if file.filename == '':
            flash('No database file selected for restore.', 'warning')
            return redirect(request.url)
        
        confirm_replace = request.form.get('confirm_replace_db')
        if not confirm_replace:
            flash('You must confirm that you understand the current database will be replaced.', 'danger')
            return redirect(request.url)

        if file and allowed_db_file(file.filename):
            secured_filename = secure_filename(file.filename) # Not used for path, but good for safety checks
            
            current_db_path = current_app.config['DATABASE']
            app_data_dir = os.path.dirname(current_db_path)
            
            # 1. Safety backup of current DB
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup_name = f"emr_database_pre_restore_{timestamp}.db"
            safety_backup_path = os.path.join(app_data_dir, safety_backup_name)
            try:
                if os.path.exists(current_db_path):
                    # Ensure current DB connection for this request context is closed before manipulating file
                    # This is tricky as Flask manages g._database. Forcing close for *this* context.
                    if hasattr(flask_g, '_database') and flask_g._database is not None:
                        flask_g._database.close()
                        flask_g._database = None # Prevent Flask from trying to close it again on teardown
                        current_app.logger.info("Closed g._database for current context before DB file operations.")
                    
                    shutil.copy2(current_db_path, safety_backup_path)
                    flash(f"Safety backup of current database created at {safety_backup_name}", 'info')
            except Exception as e_backup:
                current_app.logger.error(f"Failed to create safety backup: {e_backup}", exc_info=True)
                flash(f"Critical error: Failed to create safety backup of current database. Restore aborted. Error: {e_backup}", 'danger')
                return redirect(request.url)

            # 2. Save uploaded file temporarily
            temp_uploaded_db_name = f"uploaded_backup_{timestamp}.db.tmp"
            temp_uploaded_db_path = os.path.join(app_data_dir, temp_uploaded_db_name)
            try:
                file.save(temp_uploaded_db_path)
            except Exception as e_upload:
                current_app.logger.error(f"Failed to save uploaded DB backup: {e_upload}", exc_info=True)
                flash(f"Error saving uploaded database file. Restore aborted. Error: {e_upload}", 'danger')
                # Clean up safety backup if upload fails early
                if os.path.exists(safety_backup_path):
                     os.remove(safety_backup_path)
                     current_app.logger.info(f"Cleaned up safety backup {safety_backup_name} after upload failure.")
                return redirect(request.url)

            # 3. Replace current DB with the uploaded one
            try:
                # Close DB connection again if it was somehow reopened by another g context reference or utility
                if hasattr(flask_g, '_database') and flask_g._database is not None:
                    flask_g._database.close()
                    flask_g._database = None
                    current_app.logger.info("Re-closed g._database for current context before final DB replacement.")
                
                if os.path.exists(current_db_path):
                    os.remove(current_db_path)
                shutil.move(temp_uploaded_db_path, current_db_path) # move is atomic on same filesystem
                
                # Attempt to re-initialize schema just in case, though a valid backup should have it.
                # This also helps re-establish a connection for the current context if needed by other parts of the app after this.
                # Requires a new app context as the previous one might be stale after DB replacement.
                with current_app.app_context():
                    from database import init_db_schema
                    init_db_schema()

                flash(f"Database successfully restored from {secured_filename}. Please restart the application if using the standalone version.", 'success')
                current_app.logger.info(f"Database restored from {secured_filename}. Original DB backed up to {safety_backup_name}.")
            except Exception as e_replace:
                current_app.logger.error(f"Critical error replacing database: {e_replace}", exc_info=True)
                flash(f"Critical error replacing database: {e_replace}. Attempting to restore safety backup.", 'danger')
                try:
                    if os.path.exists(safety_backup_path):
                        if os.path.exists(current_db_path):
                            os.remove(current_db_path) # remove potentially corrupted current DB
                        shutil.move(safety_backup_path, current_db_path)
                        flash("Safety backup successfully restored.", 'warning')
                    else:
                        flash("Safety backup could not be found to restore. Database may be in an inconsistent state!", 'danger')
                except Exception as e_restore_safety:
                    current_app.logger.error(f"CRITICAL: FAILED TO RESTORE SAFETY BACKUP: {e_restore_safety}", exc_info=True)
                    flash(f"CRITICAL: FAILED TO RESTORE SAFETY BACKUP: {e_restore_safety}. DATABASE IS LIKELY CORRUPTED OR LOST.", 'danger')
                if os.path.exists(temp_uploaded_db_path): # Clean up temp file
                    os.remove(temp_uploaded_db_path)
            finally:
                 # Ensure any temp uploaded file is removed if it still exists (e.g. if shutil.move failed but file wasn't cleaned)
                if os.path.exists(temp_uploaded_db_path):
                    try:
                        os.remove(temp_uploaded_db_path)
                    except Exception as e_cleanup:
                        current_app.logger.error(f"Failed to cleanup temporary uploaded DB file {temp_uploaded_db_name}: {e_cleanup}", exc_info=True)
            
            return redirect(url_for('admin.manage_database_route'))
        else:
            flash('Invalid file type for database restore. Only .db, .sqlite, .sqlite3 files are allowed.', 'danger')
            return redirect(request.url)

    # For GET request, pass the database path to the template
    db_path_for_template = current_app.config.get('DATABASE', 'Not Configured')
    print(f"[DEBUG] db_path_for_template in manage_database_route (GET): '{db_path_for_template}'") # DEBUG PRINT
    return render_template('admin/manage_database.html', title="Manage Database", current_db_path=db_path_for_template) 