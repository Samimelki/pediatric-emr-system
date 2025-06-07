import os
import sys
import json
import datetime
import threading
import base64
import shutil
import io
import zipfile
import logging

from flask import Flask, render_template, g, request, url_for, flash, redirect, current_app
import webview
from database import get_db, close_connection, init_db_schema, get_all_patient_data_for_export, get_active_custom_demographic_fields
from xml_exporter import generate_patient_xml
from csv_exporter import generate_patient_csvs
from utils import format_datetime
from config_manager import load_config, APP_DATA_DIR, UPLOAD_FOLDER, USER_MEDIA_FOLDER, WORD_DOCS_FOLDER
from emr_config import emr_config
from routes.patient_routes import patient_bp
from routes.pdf_export_routes import pdf_export_bp
from routes.admin_routes import admin_bp
from routes.settings_routes import settings_bp
from routes.emr_settings_routes import emr_settings_bp

# --- Start of Logging Setup ---
# Ensure the log directory exists
log_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'WordDocsEMR')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, 'app_debug.log') # Use a different name to avoid conflict

# Configure logging
logging.basicConfig(
    filename=log_file,
    filemode='w',  # Overwrite log on each run
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger(__name__)

def handle_exception(exc_type, exc_value, exc_traceback):
    """Log any uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    _logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

_logger.info("--- Application Starting (app.py) ---")
# --- End of Logging Setup ---

try:
    logging.info("Importing Flask...")
    from flask import Flask, render_template, g, request, url_for, flash, redirect, current_app
    logging.info("Importing webview...")
    import webview
    logging.info("Importing database functions...")
    from database import get_db, close_connection, init_db_schema, get_all_patient_data_for_export, get_active_custom_demographic_fields
    logging.info("Importing exporters...")
    from xml_exporter import generate_patient_xml
    from csv_exporter import generate_patient_csvs
    logging.info("Importing utils...")
    from utils import format_datetime
    logging.info("Importing config_manager...")
    from config_manager import load_config, APP_DATA_DIR, UPLOAD_FOLDER, USER_MEDIA_FOLDER, WORD_DOCS_FOLDER
    logging.info("Importing Blueprints...")
    from routes.patient_routes import patient_bp
    from routes.pdf_export_routes import pdf_export_bp
    from routes.admin_routes import admin_bp
    from routes.settings_routes import settings_bp
    logging.info("All imports successful.")
except Exception as e:
    logging.critical(f"A critical module failed to import: {e}", exc_info=True)
    sys.exit(1)

if getattr(sys, 'frozen', False):
    logging.info("Running in a PyInstaller bundle.")
    bundle_dir = sys._MEIPASS
    font_config_path = os.path.join(bundle_dir, 'etc', 'fonts')
    if os.path.isdir(font_config_path):
        os.environ['FONTCONFIG_PATH'] = font_config_path
        logging.info(f"FONTCONFIG_PATH set to: {font_config_path}")
    else:
        logging.warning(f"Bundled font config directory not found at: {font_config_path}")

app = Flask(__name__)
app.secret_key = 'your secret key'

logging.info("Loading unified EMR configuration...")
config = load_config()  # Legacy config for backward compatibility

# Use the unified EMR configuration system
logging.info(f"EMR Mode: {emr_config.get_emr_mode()}")
logging.info(f"Database Path: {emr_config.get_database_path()}")
logging.info(f"Upload Folder: {emr_config.get_upload_folder()}")
logging.info(f"User Media Folder: {emr_config.get_user_media_folder()}")
logging.info(f"Word Docs Folder: {emr_config.get_word_docs_folder()}")

# Configure Flask app with unified settings
app.config['DATABASE'] = emr_config.get_database_path()
app.config['UPLOAD_FOLDER'] = emr_config.get_upload_folder()
app.config['USER_MEDIA_FOLDER'] = emr_config.get_user_media_folder()
app.config['WORD_DOCS_FOLDER'] = emr_config.get_word_docs_folder()
app.config['STORAGE_TYPE'] = config.get('storage_type', 'local')  # Legacy fallback
app.config['CLOUD_PATH'] = config.get('cloud_path')  # Legacy fallback
app.config['EMR_CONFIG'] = emr_config
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.filters['format_datetime'] = format_datetime

@app.context_processor
def inject_now():
    return {'current_year': datetime.datetime.now().year}

@app.context_processor
def inject_emr_config():
    return {
        'emr_config': emr_config,
        'emr_mode': emr_config.get_emr_mode(),  # Legacy compatibility
        'active_profile': emr_config.get_active_profile(),
        'emr_features': emr_config.get_enabled_features(),
        'is_feature_enabled': emr_config.is_feature_enabled,
        'practice_info': emr_config.get_practice_info()
    }

app.teardown_appcontext(close_connection)

logging.info("Registering blueprints...")
app.register_blueprint(patient_bp)
app.register_blueprint(pdf_export_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(emr_settings_bp)

# Import functionality
from routes.import_routes import import_bp
app.register_blueprint(import_bp)

# Vaccine functionality
from routes.vaccine_routes import vaccine_bp
app.register_blueprint(vaccine_bp)

logging.info("Blueprints registered.")

@app.route('/')
def index():
    config = load_config()  # Legacy config
    emr_mode = emr_config.get_emr_mode()
    features = emr_config.get_enabled_features()
    
    return render_template('index.html', 
                         title='Home', 
                         config=config, 
                         emr_mode=emr_mode,
                         emr_features=features,
                         emr_config=emr_config)

def run_flask_app():
    logging.info("Flask app thread started.")
    app.run(debug=False, port=9999, host='127.0.0.1', use_reloader=False)

class Api:
    def __init__(self):
        self.window = None
        self.app = None

    def set_window(self, window):
        self.window = window

    def set_app(self, flask_app):
        self.app = flask_app

    def select_cloud_folder(self):
        try:
            home_dir = os.path.expanduser('~')
            chosen_path = self.window.create_file_dialog(webview.FOLDER_DIALOG, directory=home_dir)
            if chosen_path:
                return {"status": "success", "path": chosen_path[0]}
            return {"status": "cancelled"}
        except Exception as e:
            logging.error("Exception in select_cloud_folder", exc_info=True)
            return {"status": "error", "message": str(e)}

    def save_chart_image(self, filename, base64_data_uri):
        try:
            header, encoded = base64_data_uri.split(',', 1)
            image_data = base64.b64decode(encoded)
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            chosen_path = self.window.create_file_dialog(webview.SAVE_DIALOG, directory=downloads_dir, save_filename=filename)
            if chosen_path:
                with open(chosen_path, 'wb') as f:
                    f.write(image_data)
                return {"status": "success", "path": chosen_path}
            return {"status": "cancelled"}
        except Exception as e:
            logging.error("Exception in save_chart_image", exc_info=True)
            return {"status": "error", "message": str(e)}
    
    def save_database_backup(self):
        try:
            db_path = self.app.config['DATABASE']
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"emr_database_backup_{timestamp}.db"
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Documents')
            chosen_path = self.window.create_file_dialog(webview.SAVE_DIALOG, directory=downloads_dir, save_filename=backup_filename)
            if chosen_path:
                shutil.copy2(db_path, chosen_path)
                return {"status": "success", "path": chosen_path}
            return {"status": "cancelled"}
        except Exception as e:
            logging.error("Exception in save_database_backup", exc_info=True)
            return {"status": "error", "message": str(e)}

    def save_xml_export(self):
        try:
            with self.app.app_context():
                all_data = get_all_patient_data_for_export()
            if not all_data:
                return {"status": "info", "message": "No data to export."}
            xml_string = generate_patient_xml(all_data)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            xml_filename = f"emr_export_{timestamp}.xml"
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Documents')
            chosen_path = self.window.create_file_dialog(webview.SAVE_DIALOG, directory=downloads_dir, save_filename=xml_filename, file_types=("XML Files (*.xml)",))
            if chosen_path:
                with open(chosen_path, 'w', encoding='utf-8') as f:
                    f.write(xml_string)
                return {"status": "success", "path": chosen_path}
            return {"status": "cancelled"}
        except Exception as e:
            logging.error("Exception in save_xml_export", exc_info=True)
            return {"status": "error", "message": str(e)}

    def save_csv_export(self):
        try:
            with self.app.app_context():
                all_data = get_all_patient_data_for_export()
                active_custom_fields = get_active_custom_demographic_fields()
            if not all_data:
                return {"status": "info", "message": "No data to export."}
            csv_files_dict = generate_patient_csvs(all_data, active_custom_fields)
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for filename, content in csv_files_dict.items():
                    zip_file.writestr(filename, content.encode('utf-8'))
            zip_buffer.seek(0)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"emr_csv_export_{timestamp}.zip"
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Documents')
            chosen_path = self.window.create_file_dialog(webview.SAVE_DIALOG, directory=downloads_dir, save_filename=zip_filename, file_types=("ZIP Files (*.zip)",))
            if chosen_path:
                with open(chosen_path, 'wb') as f:
                    f.write(zip_buffer.getvalue())
                return {"status": "success", "path": chosen_path}
            return {"status": "cancelled"}
        except Exception as e:
            logging.error("Exception in save_csv_export", exc_info=True)
            return {"status": "error", "message": str(e)}

if __name__ == '__main__':
    logging.info("Entering __main__ block.")
    try:
        flask_thread = threading.Thread(target=run_flask_app)
        flask_thread.daemon = True
        flask_thread.start()
        logging.info("Flask thread started.")
        api_instance = Api()
        with app.app_context():
            logging.info("Initializing DB schema...")
            init_db_schema()
            logging.info("DB schema initialized.")

        logging.info("Creating webview window...")
        window = webview.create_window(
            'EMR',
            'http://127.0.0.1:9999',
            js_api=api_instance,
            min_size=(1024, 768)
        )
        api_instance.set_window(window)
        api_instance.set_app(app)
        logging.info("Starting webview event loop...")
        webview.start(debug=True)
    except Exception as e:
        logging.critical("An error occurred in the __main__ block:", exc_info=True)
    finally:
        logging.info("--- Application Shutdown ---")