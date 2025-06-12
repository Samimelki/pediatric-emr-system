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
from emr_config import USER_MEDIA_FOLDER

# Import unified vaccine system
from utils.vaccine_schedule_engine import get_vaccine_schedule_config

pdf_export_bp = Blueprint('pdf_export', __name__, url_prefix='/patient/<int:patient_id>/export')

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

# --- END OF CENTRALIZED VACCINE CONSTANTS ---

# Global cache for PDF configuration
PDF_CONFIG_CACHE = {}

def load_pdf_config(force_reload=False):
    """Load PDF configuration with caching"""
    global PDF_CONFIG_CACHE
    
    if force_reload or not PDF_CONFIG_CACHE:
        config = load_config()
        PDF_CONFIG_CACHE = config.get('pdf_settings', {})
    
    return PDF_CONFIG_CACHE

def clear_pdf_config_cache():
    """Clear the PDF configuration cache"""
    global PDF_CONFIG_CACHE
    PDF_CONFIG_CACHE = {}

# --- HELPER FUNCTION FOR VACCINE DATA PREPARATION ---
def _consolidate_vaccine_name(vaccine_name):
    """
    Consolidate similar vaccine names to avoid duplicates in PDF export
    """
    # Define consolidation mappings
    consolidation_map = {
        # MMR variants
        'MMR (Measles, Mumps, Rubella)': 'MMR (Measles, Mumps, Rubella)',
        'Measles - Mumps - Rubella (MMR)': 'MMR (Measles, Mumps, Rubella)',
        'Measles': 'MMR (Measles, Mumps, Rubella)',  # Single measles goes to MMR
        'Measles (single)': 'MMR (Measles, Mumps, Rubella)',
        
        # Hib variants
        'Hib (Haemophilus influenzae b)': 'Haemophilus influenzae type b (Hib)',
        'Haemophilus influenzae type b (Hib)': 'Haemophilus influenzae type b (Hib)',
        
        # HPV variants
        'HPV (Human Papillomavirus)': 'HPV (Human Papillomavirus)',
        'Human Papillomavirus (HPV)': 'HPV (Human Papillomavirus)',
        
        # BCG variants
        'BCG (Tuberculosis)': 'BCG (Tuberculosis)',
        'Tuberculosis (BCG)': 'BCG (Tuberculosis)',
        
        # Keep others as-is
    }
    
    return consolidation_map.get(vaccine_name, vaccine_name)

def _prepare_vaccine_table_data_unified(patient_id, language='en'):
    """
    Prepare vaccine table data using the unified Immunizations table and vaccine configuration
    """
    db = get_db()
    
    # Get all immunizations for this patient, ordered by date
    immunizations_cursor = db.execute(
        "SELECT immunization, administered_date, brand_name, dose_number FROM Immunizations WHERE patient_id = ? ORDER BY immunization, administered_date ASC",
        (patient_id,)
    )
    immunizations = immunizations_cursor.fetchall()
    
    # Get vaccine configuration to determine categories
    vaccine_config = get_vaccine_schedule_config()
    
    # Group immunizations by vaccine name and organize by dose
    vaccine_data = {}
    
    # First, group by vaccine name (with consolidation)
    vaccine_groups = {}
    for imm in immunizations:
        original_vaccine_name = imm['immunization']
        consolidated_vaccine_name = _consolidate_vaccine_name(original_vaccine_name)
        date_str = format_date_for_pdf(imm['administered_date'])
        
        if not date_str:
            continue
            
        if consolidated_vaccine_name not in vaccine_groups:
            vaccine_groups[consolidated_vaccine_name] = []
        vaccine_groups[consolidated_vaccine_name].append({
            'date': date_str,
            'dose_number': imm['dose_number'],
            'administered_date': imm['administered_date']
        })
    
    # Now process each vaccine group
    for vaccine_name, doses in vaccine_groups.items():
        if not doses:
            continue
            
        vaccine_data[vaccine_name] = {}
        
        # Sort doses by date to ensure chronological order
        doses.sort(key=lambda x: x['administered_date'] if x['administered_date'] else '1900-01-01')
        
        # Assign dose keys
        for i, dose_info in enumerate(doses):
            # Use actual dose_number if available, otherwise use chronological order
            if dose_info['dose_number'] is not None:
                dose_number = dose_info['dose_number']
            else:
                dose_number = i + 1  # Start from 1 for chronological order
            
            # Create dose key
            if dose_number <= 3:
                dose_key = f"d{dose_number}"
            else:
                dose_key = f"r{dose_number - 3}"
            
            # Avoid overwriting - if key exists, find next available key
            original_dose_key = dose_key
            counter = 1
            while dose_key in vaccine_data[vaccine_name]:
                if dose_number <= 3:
                    new_dose_number = dose_number + counter
                    if new_dose_number <= 3:
                        dose_key = f"d{new_dose_number}"
                    else:
                        dose_key = f"r{new_dose_number - 3}"
                else:
                    dose_key = f"r{dose_number - 3 + counter}"
                counter += 1
                
                # Safety check to avoid infinite loop
                if counter > 10:
                    break
            
            vaccine_data[vaccine_name][dose_key] = dose_info['date']
    
    # Convert to template format and categorize
    mandatory_vaccine_table_data = []
    recommended_vaccine_table_data = []
    
    for vaccine_name, dose_dates in vaccine_data.items():
        if not dose_dates:  # Skip if no doses
            continue
            
        # Get category from configuration
        vaccine_info = vaccine_config.get(vaccine_name, {})
        category = vaccine_info.get('category', 'recommended')
        
        # Format display name with shorter DTaP description
        display_name = vaccine_name
        if vaccine_name == "DTaP - IPV":
            display_name = "DTaP - IPV<br/><small><i>(Diphtheria, Tetanus,<br/>Pertussis, Polio)</i></small>"
        elif vaccine_name == "Haemophilus influenzae type b (Hib)":
            display_name = "Hib<br/><small><i>(Haemophilus<br/>influenzae type b)</i></small>"
        elif vaccine_name == "MMR (Measles, Mumps, Rubella)":
            display_name = "MMR<br/><small><i>(Measles, Mumps,<br/>Rubella)</i></small>"
        elif vaccine_name == "PPD (TB Skin Test)":
            display_name = "PPD<br/><small><i>(TB Skin Test)</i></small>"
        elif vaccine_name == "HPV (Human Papillomavirus)":
            display_name = "HPV<br/><small><i>(Human<br/>Papillomavirus)</i></small>"
        elif vaccine_name == "BCG (Tuberculosis)":
            display_name = "BCG<br/><small><i>(Tuberculosis)</i></small>"
        elif vaccine_name == "RSV Prevention":
            display_name = "RSV<br/><small><i>(Respiratory Syncytial<br/>Virus Prevention)</i></small>"
        
        vaccine_row = {
            'vaccine_display_name': display_name,
            'dose_dates': dose_dates,
            'canonical_name': vaccine_name
        }
        
        if category == 'mandatory':
            mandatory_vaccine_table_data.append(vaccine_row)
        else:
            recommended_vaccine_table_data.append(vaccine_row)
    
    # Sort by display name
    mandatory_vaccine_table_data.sort(key=lambda x: x['vaccine_display_name'])
    recommended_vaccine_table_data.sort(key=lambda x: x['vaccine_display_name'])
    
    # Determine active dose keys (columns to show)
    active_dose_keys = []
    all_vaccine_data = mandatory_vaccine_table_data + recommended_vaccine_table_data
    
    for key in ALL_POSSIBLE_DOSE_KEYS:
        if any(vaccine_row['dose_dates'].get(key) for vaccine_row in all_vaccine_data):
            active_dose_keys.append(key)
    
    return mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys

def _get_pdf_stylesheets():
    """Get PDF stylesheets"""
    try:
        # Try to load custom stylesheet
        css_path = os.path.join(current_app.static_folder, 'css', 'pdf_styles.css')
        if os.path.exists(css_path):
            return [CSS(filename=css_path)]
        else:
            # Fallback to basic styling
            return [CSS(string="""
                body { font-family: Arial, sans-serif; font-size: 12px; }
                .vaccine-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
                .vaccine-table th, .vaccine-table td { border: 1px solid #ccc; padding: 8px; text-align: left; }
                .vaccine-table th { background-color: #f5f5f5; font-weight: bold; }
                .vaccine-name-cell { font-weight: bold; }
                .date-cell { text-align: center; }
                h2, h3 { color: #333; margin-top: 20px; }
                .patient-info { margin-bottom: 20px; }
            """)]
    except Exception as e:
        current_app.logger.error(f"Error loading PDF stylesheets: {e}")
        return []

def get_media_file_path(filename):
    """Get the full path for a media file"""
    if not filename:
        return None
    
    try:
        full_path = os.path.join(current_app.config['USER_MEDIA_FOLDER'], filename)
        if os.path.exists(full_path):
            return f"file://{os.path.abspath(full_path)}"
    except Exception as e:
        current_app.logger.error(f"Error getting media file path for {filename}: {e}")
    
    return None

# --- PDF EXPORT ROUTES ---

@pdf_export_bp.route('/vaccination_record_fr')
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
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data_unified(
        patient_id, language='fr'
    )

    html_out = render_template('vaccination_record_fr.html',
                               patient=patient, 
                               mandatory_vaccine_table_data=mandatory_vaccine_table_data,
                               recommended_vaccine_table_data=recommended_vaccine_table_data,
                               active_dose_keys=active_dose_keys,
                               table_column_labels=TABLE_COLUMN_LABELS_FR, 
                               physician=physician_details,
                               current_date=current_date, 
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note, 
                               signature_image_url_for_pdf=signature_image_url_for_pdf,
                               logo_image_url_for_pdf=logo_image_url_for_pdf)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=vaccination_record_{patient["id"]}_fr.pdf'
    return response

@pdf_export_bp.route('/vaccination_record_en')
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
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data_unified(
        patient_id, language='en'
    )

    html_out = render_template('vaccination_record_en.html',
                               patient=patient, 
                               mandatory_vaccine_table_data=mandatory_vaccine_table_data,
                               recommended_vaccine_table_data=recommended_vaccine_table_data,
                               active_dose_keys=active_dose_keys,
                               table_column_labels=TABLE_COLUMN_LABELS_EN, 
                               physician=physician_details,
                               current_date=current_date_en, 
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note, 
                               signature_image_url_for_pdf=signature_image_url_for_pdf,
                               logo_image_url_for_pdf=logo_image_url_for_pdf)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=vaccination_record_{patient["id"]}_en.pdf'
    return response

@pdf_export_bp.route('/total_history_fr')
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
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data_unified(
        patient_id, language='fr'
    )

    html_out = render_template('total_history_fr.html', 
                               patient=patient, visites=visites, 
                               mandatory_vaccine_table_data=mandatory_vaccine_table_data,
                               recommended_vaccine_table_data=recommended_vaccine_table_data,
                               active_dose_keys=active_dose_keys,
                               table_column_labels=TABLE_COLUMN_LABELS_FR,
                               physician=physician_details, footer_note=footer_note, signature_image_url_for_pdf=signature_image_url_for_pdf,
                               format_date_for_pdf=format_date_for_pdf, current_date=current_date_fr)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=total_history_{patient["id"]}_fr.pdf'
    return response

@pdf_export_bp.route('/total_history_en')
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
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data_unified(
        patient_id, language='en'
    )

    html_out = render_template('total_history_en.html', 
                               patient=patient, visites=visites, 
                               mandatory_vaccine_table_data=mandatory_vaccine_table_data,
                               recommended_vaccine_table_data=recommended_vaccine_table_data,
                               active_dose_keys=active_dose_keys,
                               table_column_labels=TABLE_COLUMN_LABELS_EN, 
                               physician=physician_details, footer_note=footer_note, signature_image_url_for_pdf=signature_image_url_for_pdf,
                               format_date_for_pdf=format_date_for_pdf, current_date=current_date_en)
    
    pdf_stylesheets = _get_pdf_stylesheets()
    
    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=total_history_{patient["id"]}_en.pdf'
    return response

@pdf_export_bp.route('/complete_report')
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

    app_config = load_config()
    pdf_settings_base = CM_DEFAULT_PDF_CONFIG.copy() # Starts with new, simplified defaults
    loaded_pdf_settings = app_config.get('pdf_settings', {})
    pdf_settings_base.update(loaded_pdf_settings)

    physician_details = pdf_settings_base.get('physician_details_en', {})
    footer_note = pdf_settings_base.get('footer_note_en', '')
    signature_filename = pdf_settings_base.get('signature_image_filename')
    logo_filename = pdf_settings_base.get('logo_image_filename')

    signature_image_url_for_pdf = get_media_file_path(signature_filename)
    logo_image_url_for_pdf = get_media_file_path(logo_filename)

    current_date_en = datetime.datetime.now().strftime("%Y-%m-%d")

    # Use unified vaccine data preparation
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data_unified(
        patient_id, language='en'
    )

    html_out = render_template('complete_report.html',
                               patient=patient,
                               visites=visites_processed,
                               mandatory_vaccine_table_data=mandatory_vaccine_table_data,
                               recommended_vaccine_table_data=recommended_vaccine_table_data,
                               active_dose_keys=active_dose_keys,
                               table_column_labels=TABLE_COLUMN_LABELS_EN,
                               physician=physician_details,
                               current_date=current_date_en,
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note,
                               signature_image_url_for_pdf=signature_image_url_for_pdf,
                               logo_image_url_for_pdf=logo_image_url_for_pdf)

    pdf_stylesheets = _get_pdf_stylesheets()

    pdf = HTML(string=html_out).write_pdf(stylesheets=pdf_stylesheets)
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=complete_report_{patient["id"]}.pdf'
    return response