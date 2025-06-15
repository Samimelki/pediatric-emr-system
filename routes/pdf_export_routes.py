from flask import Blueprint, render_template, request, make_response, current_app
import sqlite3
import datetime
import json # Added for loading config
import os # Added for path joining
from weasyprint import HTML, CSS
# from weasyprint.fonts import FontConfiguration # Still commented out
import io
import inspect # ADDED for debugging

from database import get_db # Assuming database.py is in the parent directory
from utils import format_date_for_pdf # Assuming utils.py is in the parent directory
from routes.patient_routes import calculate_age_at_visit # Import the age calculation function
from emr_config import USER_MEDIA_FOLDER, load_config, emr_config

# Import unified vaccine system
from utils.vaccine_schedule_engine import get_vaccine_schedule_config

pdf_export_bp = Blueprint('pdf_export', __name__, url_prefix='/pdf')

# --- START OF CENTRALIZED VACCINE CONSTANTS ---
ALL_POSSIBLE_DOSE_KEYS = ["d1", "d2", "d3", "r1", "r2", "r3", "r4"]

TABLE_COLUMN_LABELS_FR = {
    "vaccine_col": "Vaccin", "d1": "Dose 1", "d2": "Dose 2", "d3": "Dose 3",
    "r1": "Rappel 1", "r2": "Rappel 2", "r3": "Rappel 3", "r4": "Rappel 4"
}

TABLE_COLUMN_LABELS_EN = {
    "vaccine_col": "Vaccine", "d1": "Dose 1", "d2": "Dose 2", "d3": "Dose 3",
    "r1": "Booster 1", "r2": "Booster 2", "r3": "Booster 3", "r4": "Booster 4"
}

# Default PDF configuration
DEFAULT_PDF_CONFIG = {
    'physician_details_en': {
        'name': 'Dr. John Doe',
        'specialty': 'Family Physician',
        'hospital_name': 'Medical Center',
        'faculty_name': 'Medical University',
        'contact_line1': 'Contact Line 1',
        'contact_line2': 'Contact Line 2'
    },
    'physician_details_fr': {
        'name': 'Dr. Jean Dupont',
        'specialty': 'Médecin de Famille',
        'hospital_name': 'Centre Médical',
        'faculty_name': 'Université de Médecine',
        'contact_line1': 'Ligne de contact 1',
        'contact_line2': 'Ligne de contact 2'
    },
    'footer_note_en': 'This is a computer-generated document. No signature is required.',
    'footer_note_fr': 'Ce document est généré par ordinateur. Aucune signature n\'est requise.',
    'signature_image_filename': None,
    'logo_image_filename': None
}

# --- END OF CENTRALIZED VACCINE CONSTANTS ---

def migrate_old_pdf_config():
    """Migrate settings from old pdf_config.json to new emr_config system"""
    old_config_path = 'pdf_config.json'
    if os.path.exists(old_config_path):
        try:
            with open(old_config_path, 'r') as f:
                old_config = json.load(f)
            
            # Get current PDF settings from emr_config
            current_pdf_settings = emr_config.get_pdf_settings()
            
            # Migrate old settings to new format
            if not current_pdf_settings:  # Only migrate if no settings exist
                migrated_settings = {}
                
                # Migrate physician details
                for lang in ['en', 'fr']:
                    if f'physician_details_{lang}' in old_config:
                        migrated_settings[f'physician_details_{lang}'] = old_config[f'physician_details_{lang}']
                
                # Migrate footer notes
                for lang in ['en', 'fr']:
                    if f'footer_note_{lang}' in old_config:
                        migrated_settings[f'footer_note_{lang}'] = old_config[f'footer_note_{lang}']
                
                # Migrate signature filename
                if 'signature_image_filename' in old_config:
                    migrated_settings['signature_image_filename'] = old_config['signature_image_filename']
                
                # Save migrated settings
                emr_config.config['pdf_settings'] = migrated_settings
                emr_config.save_config()
                
                print(f"Migrated PDF settings from {old_config_path} to emr_config")
                
                # Optionally backup the old file
                backup_path = f"{old_config_path}.backup"
                os.rename(old_config_path, backup_path)
                print(f"Backed up old config to {backup_path}")
                
        except Exception as e:
            print(f"Error migrating old PDF config: {e}")

def load_pdf_config(force_reload=False):
    """Load PDF configuration from emr_config system"""
    # Try to migrate old config first
    migrate_old_pdf_config()
    
    # Get PDF settings from emr_config
    pdf_settings = emr_config.get_pdf_settings()
    
    # If no settings exist, use defaults
    if not pdf_settings:
        pdf_settings = DEFAULT_PDF_CONFIG.copy()
        # Save defaults to config
        emr_config.config['pdf_settings'] = pdf_settings
        emr_config.save_config()
    
    return pdf_settings

def clear_pdf_config_cache():
    """Clear the PDF configuration cache"""
    # No longer needed with emr_config system, but kept for compatibility
    pass

def get_media_file_path(filename):
    """Get the full path to a media file for PDF generation"""
    if not filename:
        return None
    full_path = os.path.join(current_app.config['USER_MEDIA_FOLDER'], filename)
    if os.path.exists(full_path):
        return f"file://{os.path.abspath(full_path)}"
    return None

def _get_pdf_stylesheets():
    """Get the CSS stylesheets for PDF generation"""
    stylesheets = []
    
    # Load main weasyprint_styles.css (if it exists)
    main_css_path = os.path.join(current_app.root_path, 'static', 'css', 'weasyprint_styles.css')
    if os.path.exists(main_css_path):
        try:
            with open(main_css_path, 'r', encoding='utf-8') as f_main:
                stylesheets.append(CSS(string=f_main.read()))
        except Exception as e:
            print(f"WARNING: Could not read main CSS file at {main_css_path}: {e}")
            
    # Load new pdf_styles.css
    pdf_specific_css_path = os.path.join(current_app.root_path, 'static', 'css', 'pdf_styles.css')
    if os.path.exists(pdf_specific_css_path):
        try:
            with open(pdf_specific_css_path, 'r', encoding='utf-8') as f_pdf:
                stylesheets.append(CSS(string=f_pdf.read()))
        except Exception as e:
            print(f"WARNING: Could not read PDF specific CSS file at {pdf_specific_css_path}: {e}")
    else:
        print(f"WARNING: PDF specific CSS file not found at {pdf_specific_css_path}. PDFs might not be styled correctly.")
        
    if not stylesheets:
        print("WARNING: No CSS stylesheets loaded for PDF generation. Using WeasyPrint defaults.")
        
    return stylesheets

# --- HELPER FUNCTION FOR VACCINE DATA PREPARATION ---
def _prepare_vaccine_table_data_unified(patient_id, language='en'):
    """
    Prepare vaccine table data using ONLY the Immunizations table
    Categories are determined by the vaccine configuration
    """
    print(f"DEBUG PDF: Starting vaccine preparation for patient {patient_id}")
    db = get_db()
    
    # Get ALL immunizations for this patient from the Immunizations table (single source of truth)
    immunizations_cursor = db.execute(
        "SELECT immunization, administered_date, brand_name, dose_number FROM Immunizations WHERE patient_id = ? ORDER BY immunization, administered_date ASC",
        (patient_id,)
    )
    immunizations = immunizations_cursor.fetchall()
    print(f"DEBUG PDF: Found {len(immunizations)} immunizations in Immunizations table")
    
    if immunizations:
        for i, imm in enumerate(immunizations[:5]):  # Show first 5
            print(f"  {i+1}. {imm['immunization']} on {imm['administered_date']}")
        if len(immunizations) > 5:
            print(f"  ... and {len(immunizations) - 5} more")
    
    # Get vaccine configuration to determine categories
    vaccine_config = get_vaccine_schedule_config()
    
    # Group immunizations by vaccine name and organize by dose
    vaccine_groups = {}
    for imm in immunizations:
        vaccine_name = imm['immunization']  # Use exact name from database - NO consolidation
        date_str = format_date_for_pdf(imm['administered_date'])
        
        if not date_str:
            continue
            
        if vaccine_name not in vaccine_groups:
            vaccine_groups[vaccine_name] = []
        vaccine_groups[vaccine_name].append({
            'date': date_str,
            'dose_number': imm['dose_number'],
            'administered_date': imm['administered_date']
        })
    
    # Convert grouped data to the expected format and categorize
    vaccine_data = {}
    for vaccine_name, doses in vaccine_groups.items():
        # Sort doses by date
        doses.sort(key=lambda x: x['administered_date'] if x['administered_date'] else '9999-12-31')
        
        # Create dose dictionary
        dose_dict = {}
        for i, dose in enumerate(doses):
            dose_key = f"Dose {i+1}"
            dose_dict[dose_key] = dose['date']
        
        # Determine category based on vaccine config
        category = _determine_vaccine_category(vaccine_name, vaccine_config)
        
        vaccine_data[vaccine_name] = {
            'doses': dose_dict,
            'category': category,
            'canonical_name': vaccine_name
        }
    
    # Sort vaccines by name for consistent display
    sorted_vaccines = sorted(vaccine_data.items(), key=lambda x: x[0])
    
    # Separate into categories
    mandatory_vaccines = []
    recommended_vaccines = []
    other_vaccines = []
    
    for vaccine_name, data in sorted_vaccines:
        vaccine_entry = (vaccine_name, data['doses'])
        
        if data['category'] == 'mandatory':
            mandatory_vaccines.append(vaccine_entry)
        elif data['category'] == 'recommended':
            recommended_vaccines.append(vaccine_entry)
        else:
            other_vaccines.append(vaccine_entry)
    
    print(f"DEBUG PDF: Categorized vaccines - Mandatory: {len(mandatory_vaccines)}, Recommended: {len(recommended_vaccines)}, Other: {len(other_vaccines)}")
    
    return {
        'mandatory_vaccines': mandatory_vaccines,
        'recommended_vaccines': recommended_vaccines,
        'other_vaccines': other_vaccines
    }

def _determine_vaccine_category(vaccine_name, vaccine_config):
    """
    Determine if a vaccine is mandatory, recommended, or other based on config
    """
    print(f"DEBUG PDF: Categorizing vaccine '{vaccine_name}'")
    
    # Check if vaccine exists directly in config (top-level keys)
    if vaccine_name in vaccine_config:
        vaccine_info = vaccine_config[vaccine_name]
        if isinstance(vaccine_info, dict) and 'category' in vaccine_info:
            category = vaccine_info['category']
            print(f"DEBUG PDF: Direct match '{vaccine_name}' -> {category}")
            if category == 'mandatory':
                return 'mandatory'
            elif category == 'recommended':
                return 'recommended'
            else:
                return 'other'
    
    # Check name mappings for any legacy names that might still exist
    if 'name_mappings' in vaccine_config:
        name_mappings = vaccine_config['name_mappings']
        for original_name, canonical_name in name_mappings.items():
            if vaccine_name.lower() == original_name.lower():
                print(f"DEBUG PDF: Name mapping match '{vaccine_name}' -> '{canonical_name}'")
                # Look up the canonical name in the config
                if canonical_name in vaccine_config:
                    vaccine_info = vaccine_config[canonical_name]
                    if isinstance(vaccine_info, dict) and 'category' in vaccine_info:
                        category = vaccine_info['category']
                        print(f"DEBUG PDF: Mapped vaccine '{canonical_name}' -> {category}")
                        if category == 'mandatory':
                            return 'mandatory'
                        elif category == 'recommended':
                            return 'recommended'
                        else:
                            return 'other'
    
    # Default to 'other' if not found in config
    print(f"DEBUG PDF: Vaccine '{vaccine_name}' not found in config, defaulting to 'other'")
    return 'other'

# Vaccine display mappings for PDF templates
VACCINE_DISPLAY_MAPPING_EN = {
    'DTaP - IPV': {
        'short_name': 'DTaP - IPV',
        'description': '(Diphtheria, Tetanus,<br>Pertussis, Polio)'
    },
    'MMR (Measles, Mumps, Rubella)': {
        'short_name': 'MMR',
        'description': '(Measles, Mumps,<br>Rubella)'
    },
    'Hib (Haemophilus influenzae b)': {
        'short_name': 'Hib',
        'description': '(Haemophilus<br>influenzae type b)'
    },
    'Hepatitis B': {
        'short_name': 'Hepatitis B',
        'description': ''
    },
    'Hepatitis A': {
        'short_name': 'Hepatitis A',
        'description': ''
    },
    'PPD (TB Skin Test)': {
        'short_name': 'PPD',
        'description': '(TB Skin Test)'
    },
    'Measles (single)': {
        'short_name': 'Measles',
        'description': '(single)'
    },
    'Pneumococcal PCV': {
        'short_name': 'Pneumococcal PCV',
        'description': '(Pneumococcal)'
    },
    'Varicella': {
        'short_name': 'Varicella',
        'description': '(Chickenpox)'
    },
    'Influenza': {
        'short_name': 'Influenza',
        'description': '(Flu)'
    },
    'Meningococcal ACWY': {
        'short_name': 'Meningococcal ACWY',
        'description': '(Meningococcal)'
    },
    'Rotavirus': {
        'short_name': 'Rotavirus',
        'description': ''
    }
}

VACCINE_DISPLAY_MAPPING_FR = {
    'DTaP - IPV': {
        'short_name': 'DTaP - IPV',
        'description': '(Diphtérie, Tétanos,<br>Coqueluche, Polio)'
    },
    'MMR (Measles, Mumps, Rubella)': {
        'short_name': 'ROR',
        'description': '(Rougeole, Oreillons,<br>Rubéole)'
    },
    'Hib (Haemophilus influenzae b)': {
        'short_name': 'Hib',
        'description': '(Haemophilus<br>influenzae type b)'
    },
    'Hepatitis B': {
        'short_name': 'Hépatite B',
        'description': ''
    },
    'Hepatitis A': {
        'short_name': 'Hépatite A',
        'description': ''
    },
    'PPD (TB Skin Test)': {
        'short_name': 'PPD',
        'description': '(Test cutané TB)'
    },
    'Measles (single)': {
        'short_name': 'Rougeole',
        'description': '(seule)'
    },
    'Pneumococcal PCV': {
        'short_name': 'Pneumocoque PCV',
        'description': '(Pneumocoque)'
    },
    'Varicella': {
        'short_name': 'Varicelle',
        'description': ''
    },
    'Influenza': {
        'short_name': 'Grippe',
        'description': ''
    },
    'Meningococcal ACWY': {
        'short_name': 'Méningocoque ACWY',
        'description': '(Méningocoque)'
    },
    'Rotavirus': {
        'short_name': 'Rotavirus',
        'description': ''
    }
}

def get_vaccine_display_info(vaccine_name, language='en'):
    """Get display information for a vaccine name"""
    mapping = VACCINE_DISPLAY_MAPPING_EN if language == 'en' else VACCINE_DISPLAY_MAPPING_FR
    return mapping.get(vaccine_name, {
        'short_name': vaccine_name,
        'description': ''
    })

# --- PDF EXPORT ROUTES ---

@pdf_export_bp.route('/vaccination_record_fr/<int:patient_id>')
def export_vaccination_record_fr(patient_id):
    db = get_db()
    config = load_pdf_config()
    patient = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,)).fetchone()
    if not patient: return "Patient not found", 404

    physician_details = config.get('physician_details_fr', {})
    footer_note = config.get('footer_note_fr', '')
    signature_filename = config.get('signature_image_filename')
    logo_filename = config.get('logo_image_filename')
    
    signature_image_url_for_pdf = get_media_file_path(signature_filename)
    logo_image_url_for_pdf = get_media_file_path(logo_filename)

    current_date = datetime.datetime.now().strftime("%d/%m/%Y")

    # Use unified vaccine data preparation
    vaccine_data = _prepare_vaccine_table_data_unified(patient_id, language='fr')

    html_out = render_template('vaccination_record_fr.html',
                               patient=patient, 
                               vaccine_data=vaccine_data,
                               table_column_labels=TABLE_COLUMN_LABELS_FR, 
                               physician=physician_details,
                               current_date=current_date, 
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note, 
                               signature_image_url_for_pdf=signature_image_url_for_pdf,
                               logo_image_url_for_pdf=logo_image_url_for_pdf,
                               get_vaccine_display_info=get_vaccine_display_info)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=vaccination_record_{patient["id"]}_fr.pdf'
    return response

@pdf_export_bp.route('/vaccination_record_en/<int:patient_id>')
def export_vaccination_record_en(patient_id):
    db = get_db()
    config = load_pdf_config()
    patient = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,)).fetchone()
    if not patient: return "Patient not found", 404

    physician_details = config.get('physician_details_en', {})
    footer_note = config.get('footer_note_en', '')
    signature_filename = config.get('signature_image_filename')
    logo_filename = config.get('logo_image_filename')
    
    signature_image_url_for_pdf = get_media_file_path(signature_filename)
    logo_image_url_for_pdf = get_media_file_path(logo_filename)

    current_date_en = datetime.datetime.now().strftime("%Y-%m-%d")

    # Use unified vaccine data preparation
    vaccine_data = _prepare_vaccine_table_data_unified(patient_id, language='en')

    html_out = render_template('vaccination_record_en.html',
                               patient=patient, 
                               vaccine_data=vaccine_data,
                               table_column_labels=TABLE_COLUMN_LABELS_EN, 
                               physician=physician_details,
                               current_date=current_date_en, 
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note, 
                               signature_image_url_for_pdf=signature_image_url_for_pdf,
                               logo_image_url_for_pdf=logo_image_url_for_pdf,
                               get_vaccine_display_info=get_vaccine_display_info)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=vaccination_record_{patient["id"]}_en.pdf'
    return response

@pdf_export_bp.route('/total_history_fr/<int:patient_id>')
def export_total_history_fr(patient_id):
    db = get_db()
    config = load_pdf_config()
    patient = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,)).fetchone()
    visites = db.execute("SELECT * FROM Visits WHERE patient_id = ? ORDER BY visit_date DESC", (patient_id,)).fetchall()
    if not patient: return "Patient not found", 404

    physician_details = config.get('physician_details_fr', {})
    footer_note = config.get('footer_note_fr', '')
    signature_filename = config.get('signature_image_filename')
    signature_image_url_for_pdf = None
    if signature_filename:
        full_path = os.path.join(current_app.config['USER_MEDIA_FOLDER'], signature_filename)
        if os.path.exists(full_path):
            signature_image_url_for_pdf = f"file://{os.path.abspath(full_path)}"
    
    current_date_fr = datetime.datetime.now().strftime("%d/%m/%Y")

    # Use unified vaccine data preparation
    vaccine_data = _prepare_vaccine_table_data_unified(patient_id, language='fr')

    html_out = render_template('total_history_fr.html', 
                               patient=patient, visites=visites, 
                               vaccine_data=vaccine_data,
                               table_column_labels=TABLE_COLUMN_LABELS_FR,
                               physician=physician_details, footer_note=footer_note, signature_image_url_for_pdf=signature_image_url_for_pdf,
                               format_date_for_pdf=format_date_for_pdf, current_date=current_date_fr,
                               get_vaccine_display_info=get_vaccine_display_info)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=total_history_{patient["id"]}_fr.pdf'
    return response

@pdf_export_bp.route('/total_history_en/<int:patient_id>')
def export_total_history_en(patient_id):
    db = get_db()
    config = load_pdf_config()
    patient = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,)).fetchone()
    visites = db.execute("SELECT * FROM Visits WHERE patient_id = ? ORDER BY visit_date DESC", (patient_id,)).fetchall()
    if not patient: return "Patient not found", 404

    physician_details = config.get('physician_details_en', {})
    footer_note = config.get('footer_note_en', '')
    signature_filename = config.get('signature_image_filename')
    signature_image_url_for_pdf = None
    if signature_filename:
        full_path = os.path.join(current_app.config['USER_MEDIA_FOLDER'], signature_filename)
        if os.path.exists(full_path):
            signature_image_url_for_pdf = f"file://{os.path.abspath(full_path)}"

    current_date_en = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Use unified vaccine data preparation
    vaccine_data = _prepare_vaccine_table_data_unified(patient_id, language='en')

    html_out = render_template('total_history_en.html', 
                               patient=patient, visites=visites, 
                               vaccine_data=vaccine_data,
                               table_column_labels=TABLE_COLUMN_LABELS_EN, 
                               physician=physician_details, footer_note=footer_note, signature_image_url_for_pdf=signature_image_url_for_pdf,
                               format_date_for_pdf=format_date_for_pdf, current_date=current_date_en,
                               get_vaccine_display_info=get_vaccine_display_info)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=total_history_{patient["id"]}_en.pdf'
    return response

@pdf_export_bp.route('/complete_report/<int:patient_id>')
def export_complete_report(patient_id):
    db = get_db()
    patient = db.execute(
        "SELECT p.*, strftime('%Y-%m-%d', p.date_of_birth) as dob "
        'FROM Patients p WHERE p.id = ?',
        (patient_id,)
    ).fetchone()

    if not patient:
        return "Patient not found", 404

    visites_raw = db.execute(
        "SELECT v.*, strftime('%Y-%m-%d %H:%M:%S', v.visit_date) as visit_date, "
        "(SELECT GROUP_CONCAT(a.addendum_text || ' (' || strftime('%Y-%m-%d %H:%M', a.addendum_datetime) || ')') FROM VisitAddenda a WHERE a.visit_id = v.id) as addenda_texts, "
        "(SELECT GROUP_CONCAT(strftime('%Y-%m-%d %H:%M', a.addendum_datetime)) FROM VisitAddenda a WHERE a.visit_id = v.id) as addenda_datetimes "
        'FROM Visits v WHERE v.patient_id = ? ORDER BY v.visit_date DESC',
        (patient_id,)
    ).fetchall()

    visites_processed = []
    for v_row in visites_raw:
        visit_dict = dict(v_row)
        if patient['date_of_birth'] and v_row['visit_date']:
             visit_dict['age_at_visit'] = calculate_age_at_visit(patient['date_of_birth'], v_row['visit_date'])
        else:
             visit_dict['age_at_visit'] = "N/A"
        visit_dict['notes'] = v_row['notes']
        
        if v_row['vital_signs']:
            try:
                visit_dict['vital_signs'] = json.loads(v_row['vital_signs'])
            except json.JSONDecodeError:
                current_app.logger.error(f"Failed to parse vital_signs JSON for visit {v_row['id']}: {v_row['vital_signs']}")
                visit_dict['vital_signs'] = None
        else:
            visit_dict['vital_signs'] = None
        
        visit_dict['addenda_texts'] = v_row['addenda_texts']

        visites_processed.append(visit_dict)

    # Load PDF configuration using the proper emr_config system
    pdf_settings = load_pdf_config()

    physician_details = pdf_settings.get('physician_details_en', {})
    footer_note = pdf_settings.get('footer_note_en', '')
    signature_filename = pdf_settings.get('signature_image_filename')
    logo_filename = pdf_settings.get('logo_image_filename')

    signature_image_url_for_pdf = get_media_file_path(signature_filename)
    logo_image_url_for_pdf = get_media_file_path(logo_filename)

    current_date_en = datetime.datetime.now().strftime("%Y-%m-%d")

    # Use unified vaccine data preparation
    vaccine_data = _prepare_vaccine_table_data_unified(patient_id, language='en')

    html_out = render_template('complete_report.html',
                               patient=patient,
                               visites=visites_processed,
                               vaccine_data=vaccine_data,
                               table_column_labels=TABLE_COLUMN_LABELS_EN,
                               physician=physician_details,
                               current_date=current_date_en,
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note,
                               signature_image_url_for_pdf=signature_image_url_for_pdf,
                               logo_image_url_for_pdf=logo_image_url_for_pdf,
                               get_vaccine_display_info=get_vaccine_display_info)

    pdf_stylesheets = _get_pdf_stylesheets()

    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=complete_report_{patient["id"]}.pdf'
    return response