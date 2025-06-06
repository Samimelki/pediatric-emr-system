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
    'emr_name': 'EMR',  # Customizable EMR name
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
    """Recursively update a dictionary."""
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def ensure_directories_exist():
    """Ensure all necessary directories exist for the application to function properly."""
    directories_to_create = [
        APP_DATA_DIR,
        UPLOAD_FOLDER,
        USER_MEDIA_FOLDER,
        WORD_DOCS_FOLDER
    ]
    
    for directory in directories_to_create:
        try:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                print(f"Created directory: {directory}")
        except Exception as e:
            print(f"Error creating directory {directory}: {e}")

def load_config():
    """Load configuration from config.json or create default if not exists."""
    # Ensure directories exist before loading config
    ensure_directories_exist()
    
    config = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e} - Reverting to default.")
            config = {}

    final_config = DEFAULT_CONFIG.copy()

    loaded_pdf_settings = config.get('pdf_settings', {})
    if not isinstance(loaded_pdf_settings, dict):
        loaded_pdf_settings = {}
    
    merged_pdf_settings = DEFAULT_PDF_CONFIG.copy()
    merged_pdf_settings.update(loaded_pdf_settings)

    final_config['pdf_settings'] = merged_pdf_settings

    for key, value in DEFAULT_CONFIG.items():
        if key not in config:
            final_config[key] = value
        elif key != 'pdf_settings':
            final_config[key] = config[key]

    save_config(final_config)
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