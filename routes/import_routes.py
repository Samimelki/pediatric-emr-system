import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
from datetime import datetime
from emr_config import emr_config

# Import XML processing functionality
from xml_parser import parse_excel_xml
from populate_db import populate_database_from_parsed_data

# Import Word document processing functionality  
from word_importer import WordDocumentImporter

import_bp = Blueprint('import', __name__, url_prefix='/import')

ALLOWED_XML_EXTENSIONS = {'xml'}
ALLOWED_DOC_EXTENSIONS = {'docx'}

def allowed_xml_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_XML_EXTENSIONS

def allowed_doc_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_DOC_EXTENSIONS

@import_bp.route('/')
def import_home():
    """Main import page showing available import options based on EMR mode."""
    current_mode = emr_config.get_emr_mode()
    features = emr_config.get_enabled_features()
    
    return render_template('import_home.html',
                         title='Import Medical Records',
                         emr_mode=current_mode,
                         emr_features=features)

@import_bp.route('/xml', methods=['GET', 'POST'])
def import_xml():
    """Import patient data from XML files (pediatric EMR functionality)."""
    current_mode = emr_config.get_emr_mode()
    
    if request.method == 'POST':
        if 'xmlfile' not in request.files:
            flash('No XML file selected', 'danger')
            return redirect(request.url)
        
        file = request.files['xmlfile']
        if file.filename == '':
            flash('No file selected', 'warning')
            return redirect(request.url)
        
        confirm_replace = request.form.get('confirm_replace')
        full_replace = request.form.get('full_replace')
        
        if not confirm_replace:
            flash('You must confirm that you understand the data will be imported.', 'danger')
            return redirect(request.url)

        if file and allowed_xml_file(file.filename):
            filename = secure_filename(file.filename)
            temp_xml_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            try:
                # Ensure upload folder exists
                upload_folder = current_app.config['UPLOAD_FOLDER']
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder, exist_ok=True)
                
                file.save(temp_xml_path)
                
                # Handle full replace if requested
                if full_replace:
                    db_path = current_app.config['DATABASE']
                    if os.path.exists(db_path):
                        os.remove(db_path)
                        flash('Existing database removed for fresh import.', 'info')
                    
                    # Reinitialize database schema
                    from database import init_db_schema
                    with current_app.app_context():
                        init_db_schema()
                    flash('Database schema reinitialized.', 'info')

                # Parse XML data
                parsed_patients = parse_excel_xml(temp_xml_path)
                if not parsed_patients:
                    flash('No patient data found in XML file.', 'warning')
                    return redirect(request.url)
                
                # Import to unified database
                patients_added, visits_added, vaccines_added = populate_database_from_parsed_data(
                    parsed_patients, 
                    target_mode='pediatric' if current_mode == 'pediatric' else 'mixed'
                )
                
                flash(f'XML import completed: {patients_added} patients, {visits_added} visits, {vaccines_added} vaccines imported.', 'success')
            
            except Exception as e:
                flash(f"Error during XML import: {str(e)}", 'danger')
                import traceback
                traceback.print_exc()
            finally:
                # Clean up temporary file
                if os.path.exists(temp_xml_path):
                    os.remove(temp_xml_path)
        else:
            flash('Invalid file type. Only .xml files are allowed.', 'danger')

        return redirect(url_for('import.import_xml'))

    return render_template('import_xml.html',
                         title='Import XML Data',
                         emr_mode=current_mode,
                         current_db_path=current_app.config['DATABASE'],
                         upload_folder=current_app.config['UPLOAD_FOLDER'])

@import_bp.route('/documents', methods=['GET', 'POST'])
def import_documents():
    """Import patient data from Word documents (Word Docs EMR functionality)."""
    current_mode = emr_config.get_emr_mode()
    
    if request.method == 'POST':
        files = request.files.getlist('docxfile')
        confirm_replace = request.form.get('confirm_replace')
        full_replace = request.form.get('full_replace')
        
        if not confirm_replace:
            flash('You must confirm that you understand the data will be imported.', 'danger')
            return redirect(request.url)
        
        docx_paths = []
        if files and any(f.filename for f in files):
            # Ensure upload folder exists
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
        
        try:
            # Handle full replace if requested
            if full_replace:
                db_path = current_app.config['DATABASE']
                if os.path.exists(db_path):
                    os.remove(db_path)
                    flash('Existing database removed for fresh import.', 'info')
                
                # Reinitialize database schema
                from database import init_db_schema
                with current_app.app_context():
                    init_db_schema()

            # Use WordDocumentImporter to parse the documents
            db_path = current_app.config['DATABASE']
            importer = WordDocumentImporter(db_path)
            results = importer.import_batch(docx_paths)
            
            total_success = sum(1 for _, success, _ in results if success)
            total_fail = sum(1 for _, success, _ in results if not success)
            
            for filename, success, msg in results:
                flash(f"{filename}: {'Success' if success else 'Failed'} - {msg}", 
                     'info' if success else 'danger')
            
            flash(f'Document import completed: {total_success} succeeded, {total_fail} failed.', 
                 'success' if total_fail == 0 else 'warning')
            
        except Exception as e:
            flash(f"Error during document import: {str(e)}", 'danger')
            import traceback
            traceback.print_exc()
        finally:
            # Clean up temp files
            for docx_file in docx_paths:
                if os.path.exists(docx_file) and docx_file.startswith(current_app.config['UPLOAD_FOLDER']):
                    os.remove(docx_file)

        return redirect(url_for('import.import_documents'))

    return render_template('import_documents.html',
                         title='Import Word Documents',
                         emr_mode=current_mode,
                         current_db_path=current_app.config['DATABASE'],
                         upload_folder=current_app.config['UPLOAD_FOLDER'])

@import_bp.route('/legacy-databases')
def import_legacy_databases():
    """Import from legacy EMR databases using the migration utility."""
    from migration_utility import detect_emr_databases, EMRDataMigrator
    
    current_mode = emr_config.get_emr_mode()
    
    # Detect available databases
    adult_db_path, pediatric_db_path = detect_emr_databases()
    
    return render_template('import_legacy.html',
                         title='Import Legacy Databases',
                         emr_mode=current_mode,
                         adult_db_available=adult_db_path is not None,
                         pediatric_db_available=pediatric_db_path is not None,
                         adult_db_path=adult_db_path,
                         pediatric_db_path=pediatric_db_path)

@import_bp.route('/migrate-legacy', methods=['POST'])
def migrate_legacy():
    """Execute migration from legacy databases."""
    from migration_utility import EMRDataMigrator
    
    migration_type = request.form.get('migration_type')
    confirm_migration = request.form.get('confirm_migration')
    
    if not confirm_migration:
        flash('You must confirm the migration.', 'danger')
        return redirect(url_for('import.import_legacy_databases'))
    
    try:
        # Initialize migrator
        unified_db_path = current_app.config['DATABASE']
        migrator = EMRDataMigrator(unified_db_path)
        
        if migration_type == 'adult':
            # Migrate adult EMR data
            stats = migrator.migrate_adult_emr()
            flash(f'Adult EMR migration completed: {stats["patients_migrated"]} patients, {stats["visits_migrated"]} visits migrated.', 'success')
        elif migration_type == 'pediatric':
            # Migrate pediatric EMR data  
            stats = migrator.migrate_pediatric_emr()
            flash(f'Pediatric EMR migration completed: {stats["patients_migrated"]} patients, {stats["visits_migrated"]} visits migrated.', 'success')
        elif migration_type == 'both':
            # Migrate both systems
            adult_stats = migrator.migrate_adult_emr()
            pediatric_stats = migrator.migrate_pediatric_emr()
            total_patients = adult_stats["patients_migrated"] + pediatric_stats["patients_migrated"]
            total_visits = adult_stats["visits_migrated"] + pediatric_stats["visits_migrated"]
            flash(f'Complete migration finished: {total_patients} patients, {total_visits} visits migrated from both systems.', 'success')
        else:
            flash('Invalid migration type selected.', 'danger')
    
    except Exception as e:
        flash(f'Migration error: {str(e)}', 'danger')
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('import.import_legacy_databases')) 