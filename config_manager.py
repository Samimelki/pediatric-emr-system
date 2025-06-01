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

# Default configuration
DEFAULT_CONFIG = {
    'database_path': DEFAULT_DATABASE_PATH,
    'storage_type': 'local',  # 'local', 'google_drive', 'dropbox', 'onedrive'
    'cloud_path': None,  # Path to cloud storage folder when using cloud storage
    'word_docs_folder': WORD_DOCS_FOLDER,  # Path to Word documents folder
    'emr_name': 'GARBIS EMR',  # Customizable EMR name
    'background_image_filename': None,  # Home page background image filename
}

def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
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
            print(f"Error loading config: {e}")
            config = {}
    # Always fill in missing keys (recursively)
    config = deep_update(config, DEFAULT_CONFIG)
    # Optionally, save the repaired config back to disk
    save_config(config)
    return config

def save_config(config):
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False 