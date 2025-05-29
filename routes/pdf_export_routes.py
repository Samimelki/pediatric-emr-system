from flask import Blueprint, render_template, request, make_response, current_app
import sqlite3
import datetime
import json # Added for loading config
import os # Added for path joining
from weasyprint import HTML, CSS
# from weasyprint.fonts import FontConfiguration # Still commented out

from database import get_db # Assuming database.py is in the parent directory
from utils import format_date_for_pdf # Assuming utils.py is in the parent directory

pdf_export_bp = Blueprint('pdf_export', __name__, url_prefix='/patient/<int:patient_id>/export')

# --- START OF CENTRALIZED VACCINE CONSTANTS ---
ALL_POSSIBLE_DOSE_KEYS = ["d1", "d2", "d3", "r1", "r2", "r3", "r4"]

TABLE_COLUMN_LABELS_FR = {
    "vaccine_col": "Vaccin", "d1": "Dose 1", "d2": "Dose 2", "d3": "Dose 3",
    "r1": "Rappel 1", "r2": "Rappel 2", "r3": "Rappel 3", "r4": "Rappel 4"
}
VACCINE_ALIAS_MAP_FR = {
    "VARILRIX": "Varicelle", "VARIVAX": "Varicelle",
    "ROTATEQ": "Rotavirus", "ROTARIX": "Rotavirus",
    "PREVENAR 13": "Pneumocoque PCV", "PREVENAR": "Pneumocoque PCV", "SYNFLORIX": "Pneumocoque PCV",
    "MMR": "ROR (Rougeole, Oreillons, Rubéole)", "ROR": "ROR (Rougeole, Oreillons, Rubéole)",
    "MENACTRA": "Méningocoque ACWY", "VAXIGRIP": "Grippe", "VAXIGRIPTETRA": "Grippe",
    "FLUENZ TETRA": "Grippe", "INFLUVAC": "Grippe",
    "HAVRIX": "Hépatite A", "VAQTA": "Hépatite A", "HEPATITE A": "Hépatite A", "AVAXIM": "Hépatite A",
    "ENGERIX B": "Hépatite B", "RECOMBIVAX HB": "Hépatite B",
    "BEXSERO": "Méningocoque B", "TRUMENBA": "Méningocoque B",
    "GARDASIL": "HPV (Papillomavirus humain)", "GARDASIL 9": "HPV (Papillomavirus humain)", "CERVARIX": "HPV (Papillomavirus humain)",
    "NEISVAC": "Méningocoque C", "NEISSVAC": "Méningocoque C"
}
PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_FR = [ # Renamed for clarity (was PATIENT_FIELD_TO_CANONICAL_DOSE_MAP)
    ("DTCP (Diphtérie,Tétanos,Polio,Coqueluche)", 'dtcp1_date', 'd1'),
    ("DTCP (Diphtérie,Tétanos,Polio,Coqueluche)", 'dtcp2_date', 'd2'),
    ("DTCP (Diphtérie,Tétanos,Polio,Coqueluche)", 'dtcp3_date', 'd3'),
    ("DTCP (Diphtérie,Tétanos,Polio,Coqueluche)", 'dtcp_rappel1_date', 'r1'),
    ("DTCP (Diphtérie,Tétanos,Polio,Coqueluche)", 'dtcp_rappel2_date', 'r2'),
    ("DTCP (Diphtérie,Tétanos,Polio,Coqueluche)", 'dtcp_rappel3_date', 'r3'),
    ("DTCP (Diphtérie,Tétanos,Polio,Coqueluche)", 'dtcp_rappel4_date', 'r4'),
    ("Hib (Hæmophilus influenzæ b)", 'hib1_date', 'd1'),
    ("Hib (Hæmophilus influenzæ b)", 'hib2_date', 'd2'),
    ("Hib (Hæmophilus influenzæ b)", 'hib3_date', 'd3'),
    ("Hib (Hæmophilus influenzæ b)", 'hib_rappel_date', 'r1'),
    ("Hépatite B", 'hep_b1_date', 'd1'), ("Hépatite B", 'hep_b2_date', 'd2'), ("Hépatite B", 'hep_b3_date', 'd3'),
    ("ROR (Rougeole, Oreillons, Rubéole)", 'ror_date', 'd1'),
    ("Anti-Rougeole (seule)", 'rougeole_seule_date', 'd1'),
    ("IDR (Test Tuberculinique)", 'monotest1', 'd1'),
    ("IDR (Test Tuberculinique)", 'monotest2', 'd2'),
    ("IDR (Test Tuberculinique)", 'monotest3', 'd3'),
]

TABLE_COLUMN_LABELS_EN = {
    "vaccine_col": "Vaccine", "d1": "Dose 1", "d2": "Dose 2", "d3": "Dose 3",
    "r1": "Booster 1", "r2": "Booster 2", "r3": "Booster 3", "r4": "Booster 4"
}
VACCINE_ALIAS_MAP_EN = {
    "VARILRIX": "Varicella", "VARIVAX": "Varicella",
    "ROTATEQ": "Rotavirus", "ROTARIX": "Rotavirus",
    "PREVENAR 13": "Pneumococcal PCV", "PREVENAR": "Pneumococcal PCV", "SYNFLORIX": "Pneumococcal PCV",
    "MMR": "MMR (Measles, Mumps, Rubella)", "ROR": "MMR (Measles, Mumps, Rubella)",
    "MENACTRA": "Meningococcal ACWY", "VAXIGRIP": "Influenza", "VAXIGRIPTETRA": "Influenza",
    "FLUENZ TETRA": "Influenza", "INFLUVAC": "Influenza",
    "HAVRIX": "Hepatitis A", "VAQTA": "Hepatitis A", "HEPATITE A": "Hepatitis A", "AVAXIM": "Hepatitis A",
    "ENGERIX-B": "Hepatitis B", "RECOMBIVAX HB": "Hepatitis B",
    "BEXSERO": "Meningococcal B", "TRUMENBA": "Meningococcal B",
    "GARDASIL": "HPV (Human Papillomavirus)", "GARDASIL 9": "HPV (Human Papillomavirus)", "CERVARIX": "HPV (Human Papillomavirus)",
    "NEISVAC": "Meningococcal C", "NEISSVAC": "Meningococcal C"
}
PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN = [
    ("DTaP - IPV", 'dtcp1_date', 'd1'),
    ("DTaP - IPV", 'dtcp2_date', 'd2'),
    ("DTaP - IPV", 'dtcp3_date', 'd3'),
    ("DTaP - IPV", 'dtcp_rappel1_date', 'r1'),
    ("DTaP - IPV", 'dtcp_rappel2_date', 'r2'),
    ("DTaP - IPV", 'dtcp_rappel3_date', 'r3'),
    ("DTaP - IPV", 'dtcp_rappel4_date', 'r4'),
    ("Hib (Haemophilus influenzae b)", 'hib1_date', 'd1'),
    ("Hib (Haemophilus influenzae b)", 'hib2_date', 'd2'),
    ("Hib (Haemophilus influenzae b)", 'hib3_date', 'd3'),
    ("Hib (Haemophilus influenzae b)", 'hib_rappel_date', 'r1'),
    ("Hepatitis B", 'hep_b1_date', 'd1'),
    ("Hepatitis B", 'hep_b2_date', 'd2'),
    ("Hepatitis B", 'hep_b3_date', 'd3'),
    ("MMR (Measles, Mumps, Rubella)", 'ror_date', 'd1'),
    ("Measles (single)", 'rougeole_seule_date', 'd1'),
    ("PPD (TB Skin Test)", 'monotest1', 'd1'),
    ("PPD (TB Skin Test)", 'monotest2', 'd2'),
    ("PPD (TB Skin Test)", 'monotest3', 'd3'),
]

# Define which canonical vaccine names are considered "Mandatory"
# These are typically the ones mapped directly from patient record fields.
MANDATORY_CANONICAL_VACCINE_NAMES_FR = list(set([item[0] for item in PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_FR]))
MANDATORY_CANONICAL_VACCINE_NAMES_EN = list(set([item[0] for item in PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN]))

# --- END OF CENTRALIZED VACCINE CONSTANTS ---

# Global cache for PDF configuration
PDF_CONFIG_CACHE = {}

# Default configuration (used if file is missing or corrupt)
# REMOVING ARABIC physician_details_ar and footer_note_ar
DEFAULT_PDF_CONFIG = {
    "physician_details_fr": {
        "name": "Dr. Prénom Nom (Défaut)", 
        "specialty": "Pédiatre (Défaut)", 
        "hospital_name": "Hôpital/Clinique (Défaut)",
        "faculty_name": "Faculté/Université (Défaut)",
        "contact_line1": "Contact 1 (Défaut)", 
        "contact_line2": "Contact 2 (Défaut)"
    },
    "physician_details_en": {
        "name": "Dr. Firstname Lastname (Default)", 
        "specialty": "Pediatrician (Default)", 
        "hospital_name": "Hospital/Clinic (Default)",
        "faculty_name": "Faculty/University (Default)",
        "contact_line1": "Contact 1 (Default)", 
        "contact_line2": "Contact 2 (Default)"
    },
    "footer_note_fr": "Note de bas de page (Défaut)",
    "footer_note_en": "Footer note (Default)",
    "signature_image_filename": ""
}

def load_pdf_config(force_reload=False):
    global PDF_CONFIG_CACHE, DEFAULT_PDF_CONFIG
    if not force_reload and PDF_CONFIG_CACHE:
        return PDF_CONFIG_CACHE

    config_path = os.path.join(current_app.root_path, 'pdf_config.json')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
            
            # Ensure all keys from DEFAULT_PDF_CONFIG are present
            # and remove Arabic specific keys if they exist in the loaded file
            # to align with the new DEFAULT_PDF_CONFIG
            final_config = {}
            for key, default_value in DEFAULT_PDF_CONFIG.items():
                if key in config_data:
                    # If default value is a dict, ensure loaded value is also a dict and merge missing sub-keys
                    if isinstance(default_value, dict):
                        if isinstance(config_data[key], dict):
                            final_config[key] = default_value.copy()
                            final_config[key].update(config_data[key])
                        else: # type mismatch, use default
                            final_config[key] = default_value.copy()
                    else: # Not a dict, just use the loaded value
                        final_config[key] = config_data[key]
                else: # Key not in loaded_config, use default
                    final_config[key] = default_value.copy() if isinstance(default_value, dict) else default_value
            
            PDF_CONFIG_CACHE = final_config
            return PDF_CONFIG_CACHE
    except FileNotFoundError:
        print(f"WARNING: pdf_config.json not found at {config_path}. Using default PDF details and creating the file.")
        try:
            with open(config_path, 'w', encoding='utf-8') as f_create:
                json.dump(DEFAULT_PDF_CONFIG, f_create, indent=4, ensure_ascii=False)
            PDF_CONFIG_CACHE = DEFAULT_PDF_CONFIG.copy() # Use a copy
        except Exception as e_create:
            print(f"ERROR: Could not create pdf_config.json at {config_path}: {e_create}. Using in-memory defaults.")
            PDF_CONFIG_CACHE = DEFAULT_PDF_CONFIG.copy()
        return PDF_CONFIG_CACHE
    except json.JSONDecodeError:
        print(f"WARNING: pdf_config.json is not valid JSON. Using default PDF details.")
        PDF_CONFIG_CACHE = DEFAULT_PDF_CONFIG.copy()
        return PDF_CONFIG_CACHE
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while loading pdf_config.json: {e}. Using default PDF details.")
        PDF_CONFIG_CACHE = DEFAULT_PDF_CONFIG.copy()
        return PDF_CONFIG_CACHE

def clear_pdf_config_cache():
    global PDF_CONFIG_CACHE
    PDF_CONFIG_CACHE = {}
    print("PDF Config Cache Cleared")

# --- HELPER FUNCTION FOR VACCINE DATA PREPARATION ---
def _prepare_vaccine_table_data(patient_data_row, autres_vaccins_query_results, 
                                patient_field_map, vaccine_alias_map, mandatory_canonical_names,
                                non_standard_date_format=None):
    all_vaccine_doses_by_canonical_name = {}

    # 1. Process defined patient fields
    for canonical_name, patient_field, dose_key in patient_field_map:
        date_val = format_date_for_pdf(patient_data_row[patient_field])
        if date_val:
            if canonical_name not in all_vaccine_doses_by_canonical_name:
                all_vaccine_doses_by_canonical_name[canonical_name] = {}
            if dose_key not in all_vaccine_doses_by_canonical_name[canonical_name]:
                 all_vaccine_doses_by_canonical_name[canonical_name][dose_key] = date_val

    # 2. Process non-standard vaccine entries
    dose_keys_for_filling = ['d1', 'd2', 'd3', 'r1', 'r2', 'r3', 'r4'] # Order for filling general doses
    temp_non_standard_dates = {}
    for v_row in autres_vaccins_query_results:
        original_name = v_row['vaccine_name']
        # Use .upper() for robust alias matching
        canonical_name = vaccine_alias_map.get(original_name.upper(), original_name) 
        
        date_val = format_date_for_pdf(v_row['vaccine_date'], non_standard_date_format) if non_standard_date_format else format_date_for_pdf(v_row['vaccine_date'])
        
        if date_val:
            if canonical_name not in temp_non_standard_dates:
                temp_non_standard_dates[canonical_name] = []
            # Avoid adding duplicate dates from the non-standard source for the same canonical vaccine
            if date_val not in temp_non_standard_dates[canonical_name]:
                temp_non_standard_dates[canonical_name].append(date_val)
    
    for canonical_name, dates_list in temp_non_standard_dates.items():
        if canonical_name not in all_vaccine_doses_by_canonical_name:
            all_vaccine_doses_by_canonical_name[canonical_name] = {}
        
        current_doses_for_vaccine = all_vaccine_doses_by_canonical_name[canonical_name]
        existing_dates_for_this_vaccine = set(current_doses_for_vaccine.values())

        for date_to_add in dates_list:
            if date_to_add in existing_dates_for_this_vaccine:
                continue 

            assigned_to_slot = False
            for dose_key_to_fill in dose_keys_for_filling:
                if dose_key_to_fill not in current_doses_for_vaccine:
                    current_doses_for_vaccine[dose_key_to_fill] = date_to_add
                    existing_dates_for_this_vaccine.add(date_to_add) # Track added date
                    assigned_to_slot = True
                    break
    
    # 3. Convert to template format
    final_table_data = []
    for canonical_name, dose_dates_dict in all_vaccine_doses_by_canonical_name.items():
        if dose_dates_dict: 
            display_name = canonical_name
            if canonical_name == "DTCP (Diphtérie,Tétanos,Polio,Coqueluche)":
                display_name = "DTCP <small><i>(Diphtérie,Tétanos,Polio,Coqueluche)</i></small>"
            elif canonical_name == "DTaP - IPV":
                # Assuming DTaP - IPV is the English equivalent and should be treated similarly if too long
                # Or find the full English expansion if needed for the parenthetical part
                # For now, let's assume it's okay, or apply a similar logic if its full form is problematic.
                # Example if it also had a long form in parentheses:
                # display_name = "DTaP - IPV <small><i>(Diphtheria, Tetanus, acellular Pertussis, Inactivated Polio Vaccine)</i></small>"
                pass # No change for DTaP - IPV for now, unless specified it's too long
            elif canonical_name == "Hib (Hæmophilus influenzæ b)":
                 display_name = "Hib <small><i>(Hæmophilus influenzæ b)</i></small>"
            elif canonical_name == "ROR (Rougeole, Oreillons, Rubéole)":
                 display_name = "ROR <small><i>(Rougeole, Oreillons, Rubéole)</i></small>"
            elif canonical_name == "MMR (Measles, Mumps, Rubella)":
                 display_name = "MMR <small><i>(Measles, Mumps, Rubella)</i></small>"

            final_table_data.append({
                'vaccine_display_name': display_name,
                'dose_dates': dose_dates_dict,
                'canonical_name': canonical_name
            })
    
    # Optional: Sort by display name
    final_table_data.sort(key=lambda x: x['vaccine_display_name'])

    # 4. Categorize into Mandatory and Recommended
    mandatory_vaccine_table_data = []
    recommended_vaccine_table_data = []
    for vaccine_row in final_table_data:
        if vaccine_row['canonical_name'] in mandatory_canonical_names:
            mandatory_vaccine_table_data.append(vaccine_row)
        else:
            recommended_vaccine_table_data.append(vaccine_row)

    # 5. Determine active dose keys (based on all vaccines, so columns are consistent if both tables shown)
    active_dose_keys = []
    for key in ALL_POSSIBLE_DOSE_KEYS: # ALL_POSSIBLE_DOSE_KEYS is now global
        if any(vaccine_row['dose_dates'].get(key) for vaccine_row in final_table_data):
            active_dose_keys.append(key)
            
    return mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys
# --- END OF HELPER FUNCTION ---

# --- NEW HELPER FUNCTION TO LOAD PDF STYLESHEETS ---
def _get_pdf_stylesheets():
    stylesheets = []
    
    # Load main weasyprint_styles.css (if it exists - it might be phased out or be empty)
    # This path seems to be what was intended before, but might be legacy.
    # For now, let's assume it could exist for base styling.
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
        # Optionally, add a very basic default CSS string here if pdf_styles.css is critical and missing
        # default_minimal_css = "body { font-family: sans-serif; margin: 1cm; } table { border-collapse: collapse; width: 100%; } td, th { border: 1px solid black; padding: 0.5em; }"
        # stylesheets.append(CSS(string=default_minimal_css))
        
    return stylesheets

# --- COMMON PDF CSS (This might be deprecated if pdf_styles.css covers everything) ---
# Keeping COMMON_PDF_CSS and TOTAL_HISTORY_PDF_CSS_EXTENSION for now,
# in case they are used by something or if pdf_styles.css doesn't cover all cases yet.
# Ideally, all styling should move to pdf_styles.css.
COMMON_PDF_CSS = """""" # Correctly emptied

TOTAL_HISTORY_PDF_CSS_EXTENSION = """""" # Correctly emptied
# --- END COMMON PDF CSS ---

# --- PDF EXPORT ROUTES ---

@pdf_export_bp.route('/vaccination_record_fr')
def export_vaccination_record_fr(patient_id):
    db = get_db()
    config = load_pdf_config()
    patient = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,)).fetchone()
    autres_vaccins_query = db.execute("SELECT * FROM NonStandardVaccines WHERE patient_id = ? ORDER BY vaccine_date ASC", (patient_id,)).fetchall()
    if not patient: return "Patient not found", 404

    physician_details = config.get('physician_details_fr', {})
    footer_note = config.get('footer_note_fr', '')
    signature_filename = config.get('signature_image_filename')
    signature_image_url_for_pdf = None
    if signature_filename:
        full_path = os.path.join(current_app.config['USER_MEDIA_FOLDER'], signature_filename)
        if os.path.exists(full_path):
            signature_image_url_for_pdf = f"file://{os.path.abspath(full_path)}"

    current_date_fr = datetime.datetime.now().strftime("%d/%m/%y")

    # Use centralized constants and helper
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data(
        patient, autres_vaccins_query,
        PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_FR, 
        VACCINE_ALIAS_MAP_FR,
        MANDATORY_CANONICAL_VACCINE_NAMES_FR, 
        non_standard_date_format='%d/%m/%Y'
    )

    html_out = render_template('vaccination_record_fr.html',
                               patient=patient, 
                               mandatory_vaccine_table_data=mandatory_vaccine_table_data,
                               recommended_vaccine_table_data=recommended_vaccine_table_data,
                               active_dose_keys=active_dose_keys,
                               table_column_labels=TABLE_COLUMN_LABELS_FR, 
                               physician=physician_details,
                               current_date_fr=current_date_fr, 
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note, 
                               signature_image_url_for_pdf=signature_image_url_for_pdf)
    
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
    autres_vaccins_query = db.execute("SELECT * FROM NonStandardVaccines WHERE patient_id = ? ORDER BY vaccine_date ASC", (patient_id,)).fetchall()
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

    # Use centralized constants and helper
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data(
        patient, autres_vaccins_query,
        PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN, 
        VACCINE_ALIAS_MAP_EN,
        MANDATORY_CANONICAL_VACCINE_NAMES_EN
    )

    html_out = render_template('vaccination_record_en.html',
                               patient=patient, 
                               mandatory_vaccine_table_data=mandatory_vaccine_table_data,
                               recommended_vaccine_table_data=recommended_vaccine_table_data,
                               active_dose_keys=active_dose_keys,
                               table_column_labels=TABLE_COLUMN_LABELS_EN, 
                               physician=physician_details,
                               current_date_en=current_date_en, 
                               format_date_for_pdf=format_date_for_pdf,
                               footer_note=footer_note, 
                               signature_image_url_for_pdf=signature_image_url_for_pdf)
    
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
    autres_vaccins_query = db.execute("SELECT * FROM NonStandardVaccines WHERE patient_id = ? ORDER BY vaccine_date ASC", (patient_id,)).fetchall()
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

    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data(
        patient, autres_vaccins_query,
        PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_FR, 
        VACCINE_ALIAS_MAP_FR,
        MANDATORY_CANONICAL_VACCINE_NAMES_FR,
        non_standard_date_format='%d/%m/%Y'
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
    autres_vaccins_query = db.execute("SELECT * FROM NonStandardVaccines WHERE patient_id = ? ORDER BY vaccine_date ASC", (patient_id,)).fetchall()
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
    
    mandatory_vaccine_table_data, recommended_vaccine_table_data, active_dose_keys = _prepare_vaccine_table_data(
        patient, autres_vaccins_query,
        PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN, 
        VACCINE_ALIAS_MAP_EN,
        MANDATORY_CANONICAL_VACCINE_NAMES_EN
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