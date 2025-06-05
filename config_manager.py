import os
import json

# Define application name and paths
APP_NAME = "WordDocsEMR"
USER_DOCUMENTS = os.path.join(os.path.expanduser('~'), 'Documents')
APP_DATA_DIR = os.path.join(USER_DOCUMENTS, APP_NAME)
DATABASE_NAME = 'word_docs_emr.db'
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')
DEFAULT_DATABASE_PATH = os.path.join(APP_DATA_DIR, DATABASE_NAME)
UPLOAD_FOLDER = os.path.join(APP_DATA_DIR, 'uploads')  # For temporary XML uploads
USER_MEDIA_FOLDER = os.path.join(APP_DATA_DIR, 'user_media')  # For user-uploaded images like signatures
WORD_DOCS_FOLDER = os.path.join(APP_DATA_DIR, 'word_documents')  # For patient Word documents

# Default general configuration
DEFAULT_CONFIG = {
    'database_path': DEFAULT_DATABASE_PATH,
    'storage_type': 'local',  # 'local', 'google_drive', 'dropbox', 'onedrive'
    'cloud_path': None,  # Path to cloud storage folder when using cloud storage
    'word_docs_folder': WORD_DOCS_FOLDER,  # Path to Word documents folder
    'emr_name': 'GARBIS EMR',  # Customizable EMR name
    'background_image_filename': None,  # Home page background image filename
}

# Default PDF specific configuration (used within the main config under 'pdf_settings' key)
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
    "footer_alignment": "center"  # Options: "left", "center", "right"
}

def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict):
            # For pdf_settings, we ensure it exists and then update its keys directly
            # from DEFAULT_PDF_CONFIG if that's what u is.
            if k == 'pdf_settings' and u is DEFAULT_CONFIG: # Check if we are at the top level merge
                # Ensure pdf_settings exists in d, then merge DEFAULT_PDF_CONFIG into it
                pdf_settings_in_d = d.get(k, {})
                d[k] = deep_update(pdf_settings_in_d, DEFAULT_PDF_CONFIG) 
            else:
                d[k] = deep_update(d.get(k, {}), v)
        else:
            # Only set if key is not present in d, to preserve existing values
            if k not in d:
                d[k] = v
    return d

def load_config():
    """Load configuration from config.json or create default if not exists."""
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e} - Reverting to default.")
            config = {}

    # Create a copy of DEFAULT_CONFIG to avoid modifying it directly
    # This will be the base for our final configuration
    final_config = DEFAULT_CONFIG.copy()

    # Ensure 'pdf_settings' exists and is a dictionary, then merge with DEFAULT_PDF_CONFIG
    # This handles the case where 'pdf_settings' might be missing or not a dict in the loaded config.
    loaded_pdf_settings = config.get('pdf_settings', {})
    if not isinstance(loaded_pdf_settings, dict):
        loaded_pdf_settings = {}
    
    # Merge DEFAULT_PDF_CONFIG into the loaded_pdf_settings
    # All keys from DEFAULT_PDF_CONFIG will be present, taking loaded values if they exist.
    merged_pdf_settings = DEFAULT_PDF_CONFIG.copy()
    merged_pdf_settings.update(loaded_pdf_settings) # Loaded values override defaults

    # Update the pdf_settings in the main config structure being built
    final_config['pdf_settings'] = merged_pdf_settings

    # Update the rest of the config, ensuring other top-level default keys are present
    for key, value in DEFAULT_CONFIG.items():
        if key not in config: # If a top-level key from DEFAULT_CONFIG is missing in loaded config
            final_config[key] = value # Add it from DEFAULT_CONFIG
        elif key != 'pdf_settings': # If key exists and is not pdf_settings, use loaded value
            final_config[key] = config[key]

    save_config(final_config) # Save the potentially repaired/updated config
    return final_config

def save_config(config):
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False 