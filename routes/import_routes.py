import os
import json
import zipfile
import tempfile
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, send_file
from werkzeug.utils import secure_filename
from datetime import datetime
from emr_config import emr_config

# Import XML processing functionality
from xml_parser import parse_excel_xml
from populate_db import populate_database_from_parsed_data

# Import Word document processing functionality  
from word_importer import WordDocumentImporter
from csv_importer import CSVImporter

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
                
                # Get format choice from form
                document_format = request.form.get('document_format', 'md')
                
                # Import to unified database
                patients_added, visits_added, vaccines_added = populate_database_from_parsed_data(
                    parsed_patients, 
                    target_mode='pediatric' if current_mode == 'pediatric' else 'mixed',
                    document_format=document_format
                )
                
                if document_format == 'none':
                    flash(f'XML import completed: {patients_added} patients, {visits_added} visits, {vaccines_added} vaccines imported. No files created.', 'success')
                else:
                    format_name = "Word documents" if document_format == 'docx' else "Markdown documents"
                    flash(f'XML import completed: {patients_added} patients, {visits_added} visits, {vaccines_added} vaccines imported. {format_name} created in Documents/UnifiedEMR/word_documents/', 'success')
            
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

            # Get format choice from form
            document_format = request.form.get('document_format', 'md')
            
            # Use WordDocumentImporter to parse the documents
            db_path = current_app.config['DATABASE']
            importer = WordDocumentImporter(db_path)
            results = importer.import_batch(docx_paths, document_format)
            
            total_success = sum(1 for _, success, _ in results if success)
            total_fail = sum(1 for _, success, _ in results if not success)
            
            for filename, success, msg in results:
                flash(f"{filename}: {'Success' if success else 'Failed'} - {msg}", 
                     'info' if success else 'danger')
            
            if total_success > 0:
                if document_format == 'none':
                    flash(f'Document import completed: {total_success} succeeded, {total_fail} failed. No files created.', 
                         'success' if total_fail == 0 else 'warning')
                else:
                    format_name = "Word documents" if document_format == 'docx' else "Markdown documents"
                    flash(f'Document import completed: {total_success} succeeded, {total_fail} failed. {format_name} created in Documents/UnifiedEMR/word_documents/', 
                         'success' if total_fail == 0 else 'warning')
            else:
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

@import_bp.route('/import_csv', methods=['GET', 'POST'])
def import_csv():
    """Handle CSV file imports"""
    if request.method == 'GET':
        return render_template('import_csv.html')
    
    if request.method == 'POST':
        try:
            # Check if files were uploaded
            if 'csv_files' not in request.files:
                flash('No files selected', 'error')
                return redirect(request.url)
            
            files = request.files.getlist('csv_files')
            if not files or all(f.filename == '' for f in files):
                flash('No files selected', 'error')
                return redirect(request.url)
            
            # Check confirmation
            confirm_import = request.form.get('confirm_import')
            if not confirm_import:
                flash('You must confirm that you understand the data will be imported.', 'danger')
                return redirect(request.url)
            
            # Get import options
            update_existing = request.form.get('update_existing') == 'on'
            full_replace = request.form.get('full_replace') == 'on'
            document_format = request.form.get('document_format', 'md')
            
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
            
            # Create temporary directory for uploaded files
            with tempfile.TemporaryDirectory() as temp_dir:
                uploaded_files = {}
                
                # Save uploaded files
                for file in files:
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        if filename.endswith('.csv'):
                            file_path = os.path.join(temp_dir, filename)
                            file.save(file_path)
                            uploaded_files[filename] = file_path
                
                if not uploaded_files:
                    flash('No valid CSV files uploaded', 'error')
                    return redirect(request.url)
                
                # Initialize CSV importer
                db_path = emr_config.get_database_path()
                importer = CSVImporter(db_path)
                
                # Import files
                results = {}
                total_imported = 0
                total_updated = 0
                total_errors = 0
                
                # Check if this is a bundle import (directory with multiple files)
                if len(uploaded_files) > 1:
                    # Bundle import
                    results = importer.import_csv_bundle(temp_dir, update_existing)
                    
                    for file_type, stats in results.items():
                        if 'error' not in stats:
                            total_imported += stats.get('imported', 0)
                            total_updated += stats.get('updated', 0)
                            total_errors += stats.get('errors', 0)
                else:
                    # Single file import
                    filename, file_path = list(uploaded_files.items())[0]
                    
                    try:
                        if 'patients' in filename.lower():
                            stats = importer.import_patients_csv(file_path, update_existing)
                            results['patients'] = stats
                        elif 'visits' in filename.lower():
                            stats = importer.import_visits_csv(file_path, update_existing)
                            results['visits'] = stats
                        elif 'immunizations' in filename.lower():
                            stats = importer.import_immunizations_csv(file_path, update_existing)
                            results['immunizations'] = stats
                        else:
                            # Try to auto-detect based on content
                            flash(f'Could not determine file type for {filename}. Please ensure filename contains "patients", "visits", or "immunizations".', 'error')
                            return redirect(request.url)
                        
                        total_imported = stats.get('imported', 0)
                        total_updated = stats.get('updated', 0)
                        total_errors = stats.get('errors', 0)
                        
                    except Exception as e:
                        flash(f'Error importing {filename}: {str(e)}', 'error')
                        return redirect(request.url)
                
                # Generate documents if requested and import was successful
                if document_format != 'none' and (total_imported > 0 or total_updated > 0):
                    try:
                        from word_document_manager import WordDocumentManager
                        
                        # Get database and documents paths
                        db_path = emr_config.get_database_path()
                        documents_folder = os.path.expanduser("~/Documents/UnifiedEMR/word_documents")
                        
                        # Initialize document manager with required arguments
                        doc_manager = WordDocumentManager(db_path, documents_folder)
                        
                        # Get all patients to generate documents for
                        import sqlite3
                        conn = sqlite3.connect(db_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM patients")
                        patient_ids = [row[0] for row in cursor.fetchall()]
                        conn.close()
                        
                        # Generate documents for all patients
                        docs_generated = 0
                        for patient_id in patient_ids:
                            try:
                                if document_format == 'docx':
                                    doc_manager._create_docx_document(patient_id)
                                else:  # markdown
                                    doc_manager._create_markdown_document(patient_id)
                                docs_generated += 1
                            except Exception as e:
                                current_app.logger.warning(f"Failed to generate document for patient {patient_id}: {e}")
                        
                        if docs_generated > 0:
                            format_name = "Word documents" if document_format == 'docx' else "Markdown documents"
                            flash(f'{docs_generated} {format_name} generated in Documents/UnifiedEMR/word_documents/', 'info')
                    
                    except Exception as e:
                        flash(f'Document generation failed: {str(e)}', 'warning')
                
                # Generate success message
                success_parts = []
                if total_imported > 0:
                    success_parts.append(f'{total_imported} records imported')
                if total_updated > 0:
                    success_parts.append(f'{total_updated} records updated')
                
                if success_parts:
                    flash(f'CSV import completed: {", ".join(success_parts)}', 'success')
                
                if total_errors > 0:
                    flash(f'{total_errors} errors occurred during import', 'warning')
                    
                    # Show sample of detailed errors
                    detailed_errors = importer.get_detailed_errors(limit=5)
                    if detailed_errors:
                        flash('Sample errors:', 'info')
                        for error in detailed_errors:
                            flash(f'• {error}', 'warning')
                        if len(importer.detailed_errors) > 5:
                            flash(f'... and {len(importer.detailed_errors) - 5} more errors', 'info')
                
                # Show detailed results
                for file_type, stats in results.items():
                    if 'error' in stats:
                        flash(f'{file_type.title()}: {stats["error"]}', 'error')
                    else:
                        details = []
                        if stats.get('imported', 0) > 0:
                            details.append(f"{stats['imported']} imported")
                        if stats.get('updated', 0) > 0:
                            details.append(f"{stats['updated']} updated")
                        if stats.get('skipped', 0) > 0:
                            details.append(f"{stats['skipped']} skipped")
                        if stats.get('errors', 0) > 0:
                            details.append(f"{stats['errors']} errors")
                        
                        if details:
                            flash(f'{file_type.title()}: {", ".join(details)}', 'info')
                
                return redirect(url_for('import.import_csv'))
                
        except Exception as e:
            current_app.logger.error(f"CSV import error: {e}")
            flash(f'Import failed: {str(e)}', 'error')
            return redirect(request.url) 