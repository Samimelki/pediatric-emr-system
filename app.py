import os # Add os import for path operations
import sys # For sys.executable and sys.frozen
import json # For storing cloud storage configuration

# --- PyInstaller: WeasyPrint Font Configuration ---
# When bundled, WeasyPrint (via Fontconfig) might not find its configuration.
# The 'datas' in app.spec copies Homebrew's fontconfig (e.g., /opt/homebrew/etc/fonts)
# into 'etc/fonts' at the root of the bundled app.
# We explicitly tell Fontconfig where to look for this 'fonts.conf' directory.
if os.path.isdir('./etc/fonts'): # Check if the directory exists in the bundled app
    os.environ['FONTCONFIG_PATH'] = './etc/fonts'
elif os.path.isdir(os.path.join(os.path.dirname(sys.executable), 'etc', 'fonts')) and getattr(sys, 'frozen', False):
    # If running from a bundled app (sys.frozen is True) and it's in a subfolder (like Contents/MacOS)
    os.environ['FONTCONFIG_PATH'] = os.path.join(os.path.dirname(sys.executable), 'etc', 'fonts')
# --- End PyInstaller: WeasyPrint Font Configuration ---

from flask import Flask, render_template, g, request, url_for, flash, redirect, current_app # Added current_app for app_context
import datetime
import threading # Added for running Flask in a separate thread
import webview # Added for pywebview
import base64 # For decoding base64 image data
import shutil # Added for file copying
import io # For in-memory zip file
import zipfile # For creating zip files

# import sqlite3 # Now in database.py
# import math # Now in patient_routes.py
# from weasyprint import HTML, CSS # Now in pdf_export_routes.py

# Import database functions and constants
from database import get_db, close_connection, init_db_schema, get_all_patient_data_for_export, get_active_custom_demographic_fields # Added get_all_patient_data_for_export and get_active_custom_demographic_fields
# from db_setup import setup_database # Removed import setup_database
from xml_exporter import generate_patient_xml # Added for XML export
from csv_exporter import generate_patient_csvs # Added for CSV export
from utils import format_datetime # Import the datetime formatter

# Import configuration management
from config_manager import load_config, APP_DATA_DIR, UPLOAD_FOLDER, USER_MEDIA_FOLDER, WORD_DOCS_FOLDER

# Import Blueprints
from routes.patient_routes import patient_bp
from routes.pdf_export_routes import pdf_export_bp
from routes.admin_routes import admin_bp # Import the new admin blueprint
from routes.settings_routes import settings_bp # Import the new settings blueprint

# Define application name and paths
APP_NAME = "WordDocsEMR"
USER_DOCUMENTS = os.path.join(os.path.expanduser('~'), 'Documents')
APP_DATA_DIR = os.path.join(USER_DOCUMENTS, APP_NAME)
DATABASE_NAME = 'word_docs_emr.db'
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')
DEFAULT_DATABASE_PATH = os.path.join(APP_DATA_DIR, DATABASE_NAME)
UPLOAD_FOLDER = os.path.join(APP_DATA_DIR, 'uploads') # For temporary XML uploads
USER_MEDIA_FOLDER = os.path.join(APP_DATA_DIR, 'user_media') # For user-uploaded images like signatures
ALLOWED_EXTENSIONS = {'xml'}

# Default configuration
DEFAULT_CONFIG = {
    'database_path': DEFAULT_DATABASE_PATH,
    'storage_type': 'local',  # 'local', 'google_drive', 'dropbox', 'onedrive'
    'cloud_path': None,  # Path to cloud storage folder when using cloud storage
}

def save_config(config):
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

app = Flask(__name__)
app.secret_key = 'your secret key' # Important for flash messages

# Load configuration
config = load_config()

# Ensure all required directories exist
if not os.path.exists(APP_DATA_DIR):
    os.makedirs(APP_DATA_DIR)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(USER_MEDIA_FOLDER):
    os.makedirs(USER_MEDIA_FOLDER)
if not os.path.exists(WORD_DOCS_FOLDER):
    os.makedirs(WORD_DOCS_FOLDER)
    print(f"Created Word documents folder at: {WORD_DOCS_FOLDER}")

# Set database path from config
app.config['DATABASE'] = config['database_path']
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['USER_MEDIA_FOLDER'] = USER_MEDIA_FOLDER
app.config['STORAGE_TYPE'] = config['storage_type']
app.config['CLOUD_PATH'] = config['cloud_path']
app.config['WORD_DOCS_FOLDER'] = WORD_DOCS_FOLDER

# Cache busting configurations for development
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Register the custom filter
app.jinja_env.filters['format_datetime'] = format_datetime

# Context processor to inject variables into all templates
@app.context_processor
def inject_now():
    return {'current_year': datetime.datetime.now().year}

# Register database close function
app.teardown_appcontext(close_connection)

# Register Blueprints
app.register_blueprint(patient_bp)
app.register_blueprint(pdf_export_bp)
app.register_blueprint(admin_bp) # Register the admin blueprint
app.register_blueprint(settings_bp) # Register the settings blueprint

# Main index route (can stay here or be moved to a general_routes.py if more exist)
@app.route('/')
def index():
    config = load_config()
    return render_template('index.html', title='Home', config=config)

# Function to run Flask app
def run_flask_app():
    # When running from PyInstaller bundle, debug should ideally be False.
    # Host 0.0.0.0 makes it accessible on the network, but for pywebview, 127.0.0.1 is usually preferred.
    app.run(debug=False, port=9999, host='127.0.0.1', use_reloader=False) # use_reloader=False is important with threads

# --- Pywebview API Class ---
class Api:
    def __init__(self):
        self.window = None  # Will be set after window creation
        self.app = None # To access app.config

    def set_window(self, window):
        self.window = window

    def set_app(self, flask_app):
        self.app = flask_app

    def select_cloud_folder(self):
        """Opens a folder selection dialog for choosing a cloud storage location."""
        if not self.window:
            return {"status": "error", "message": "Window reference not configured."}
        
        try:
            # Get the user's home directory
            home_dir = os.path.expanduser('~')
            
            # Common cloud storage locations
            cloud_locations = [
                os.path.join(home_dir, 'Google Drive'),
                os.path.join(home_dir, 'Dropbox'),
                os.path.join(home_dir, 'OneDrive'),
                os.path.join(home_dir, 'Documents', 'Google Drive'),
                os.path.join(home_dir, 'Documents', 'Dropbox'),
                os.path.join(home_dir, 'Documents', 'OneDrive')
            ]
            
            # Find the first existing cloud storage location
            start_dir = home_dir
            for location in cloud_locations:
                if os.path.exists(location):
                    start_dir = location
                    break
            
            # Open folder selection dialog
            chosen_path = self.window.create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=start_dir
            )
            
            if chosen_path and chosen_path.strip():
                return {"status": "success", "path": chosen_path}
            else:
                return {"status": "cancelled", "message": "No folder selected"}
                
        except Exception as e:
            print(f"Error selecting cloud folder: {e}")
            return {"status": "error", "message": str(e)}

    def save_chart_image(self, filename, base64_data_uri):
        """Saves a base64 encoded image to a file, prompting the user for location."""
        if not self.window:
            print("Error: Window reference not set for API class.")
            return {"status": "error", "message": "Window reference not configured."}
        try:
            # base64_data_uri is expected to be like "data:image/png;base64,ActualBase64String=="
            # Or "data:image/jpeg;base64,ActualBase64String=="
            header, encoded = base64_data_uri.split(',', 1)
            image_data = base64.b64decode(encoded)

            # Suggest a filename and directory
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            if not os.path.exists(downloads_dir):
                downloads_dir = os.path.expanduser('~')
            
            # create_file_dialog for SAVE_DIALOG returns a string (path) or None
            chosen_path = self.window.create_file_dialog( 
                webview.SAVE_DIALOG,
                directory=downloads_dir,
                save_filename=filename
            )

            # Explicitly check for None or empty string from dialog
            if chosen_path and chosen_path.strip(): # If a path string was returned and it's not empty/whitespace
                file_path = chosen_path
                try:
                    with open(file_path, 'wb') as f:
                        f.write(image_data)
                    print(f"Chart saved to {file_path}")
                    return {"status": "success", "path": file_path}
                except Exception as e_save:
                    print(f"Error writing to file {file_path}: {e_save}")
                    return {"status": "error", "message": f"Failed to write to file: {e_save}"}
            else: 
                print(f"Chart save cancelled or no path chosen. chosen_path: '{chosen_path}'")
                return {"status": "cancelled"}
        except Exception as e:
            print(f"Error saving chart: {e}")
            return {"status": "error", "message": str(e)}

    def save_database_backup(self):
        if not self.window or not self.app:
            print("Error: Window or App reference not set for API class.")
            return {"status": "error", "message": "Window or App reference not configured."}
        try:
            db_path = self.app.config['DATABASE']
            if not os.path.exists(db_path):
                return {"status": "error", "message": "Database file not found."}

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"emr_database_backup_{timestamp}.db"
            
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Documents') # Save to Documents by default
            if not os.path.exists(downloads_dir):
                downloads_dir = os.path.expanduser('~')

            chosen_path = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=downloads_dir,
                save_filename=backup_filename
            )

            if chosen_path and chosen_path.strip():
                try:
                    shutil.copy2(db_path, chosen_path)
                    print(f"Database backed up to {chosen_path}")
                    return {"status": "success", "path": chosen_path, "message": f"Database successfully backed up to {chosen_path}"}
                except Exception as e_copy:
                    print(f"Error copying database to {chosen_path}: {e_copy}")
                    return {"status": "error", "message": f"Failed to copy database: {e_copy}"}
            else:
                print("Database backup cancelled or no path chosen.")
                return {"status": "cancelled", "message": "Backup cancelled by user."}
        except Exception as e:
            print(f"Error during database backup: {e}")
            return {"status": "error", "message": str(e)}

    def save_xml_export(self):
        print("[PY API save_xml_export] Entered method.", flush=True)
        if not self.window or not self.app:
            print("[PY API save_xml_export] Error: Window or App reference not set.", flush=True)
            return {"status": "error", "message": "Window or App reference not configured."}
        try:
            print("[PY API save_xml_export] Inside try block.", flush=True)
            
            # --- Test Simple DB Call ---
            print("[PY API save_xml_export] Attempting simple DB call first...", flush=True)
            with self.app.app_context():
                print("[PY API save_xml_export] App context for simple call acquired.", flush=True)
                db = get_db() # Get database connection from database.py
                print("[PY API save_xml_export] Simple call: got DB.", flush=True)
                try:
                    # Try to count patients as a simple read operation
                    cursor = db.execute("SELECT COUNT(*) FROM Patients")
                    count = cursor.fetchone()[0]
                    print(f"[PY API save_xml_export] Simple DB call successful. Patient count: {count}", flush=True)
                except Exception as e_simple:
                    print(f"[PY API save_xml_export] Simple DB call FAILED: {e_simple}", flush=True)
                    return {"status": "error", "message": f"Simple DB test failed: {e_simple}"}
            print("[PY API save_xml_export] Simple DB call test finished.", flush=True)
            # --- End Test Simple DB Call ---

            print("[PY API save_xml_export] Attempting to call get_all_patient_data_for_export...", flush=True)
            with self.app.app_context():
                print("[PY API save_xml_export] App context for main data export acquired.", flush=True)
                all_data = get_all_patient_data_for_export()
                print(f"[PY API save_xml_export] Main data fetched. Record count: {len(all_data) if all_data is not None else 'None'}", flush=True)
            
            if all_data is None: # Check if all_data itself is None (e.g. if function errored before returning list)
                print("[PY API save_xml_export] all_data is None after call.", flush=True)
                return {"status": "error", "message": "Failed to retrieve data for export (data was None)."}
            if not all_data: # Check if list is empty
                print("[PY API save_xml_export] No patient data found (empty list).", flush=True)
                return {"status": "info", "message": "No patient data found to export."}

            print("[PY API save_xml_export] Generating XML string...", flush=True)
            xml_string = generate_patient_xml(all_data)
            print("[PY API save_xml_export] XML string generated.", flush=True)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            xml_filename = f"pediatric_emr_export_{timestamp}.xml"
            print(f"[PY API save_xml_export] Suggested filename: {xml_filename}", flush=True)
            
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Documents') # Save to Documents by default
            if not os.path.exists(downloads_dir):
                downloads_dir = os.path.expanduser('~')
            print(f"[PY API save_xml_export] Default save directory: {downloads_dir}", flush=True)

            print("[PY API save_xml_export] Calling create_file_dialog...", flush=True)
            chosen_path = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=downloads_dir,
                save_filename=xml_filename,
                file_types=("XML Files (*.xml)", "All files (*.*)") # Added file types
            )
            print(f"[PY API save_xml_export] create_file_dialog returned: {chosen_path}", flush=True)

            if chosen_path and chosen_path.strip():
                print(f"[PY API save_xml_export] Path chosen: {chosen_path}. Writing file...", flush=True)
                try:
                    with open(chosen_path, 'w', encoding='utf-8') as f:
                        f.write(xml_string)
                    print(f"[PY API save_xml_export] XML data exported to {chosen_path}", flush=True)
                    return {"status": "success", "path": chosen_path, "message": f"Data successfully exported as XML to {chosen_path}"}
                except Exception as e_write:
                    print(f"[PY API save_xml_export] Error writing XML to {chosen_path}: {e_write}", flush=True)
                    current_app.logger.error(f"Error writing XML to {chosen_path}: {e_write}", exc_info=True)
                    return {"status": "error", "message": f"Failed to write XML file: {e_write}"}
            else:
                print("[PY API save_xml_export] XML export cancelled or no path chosen.", flush=True)
                return {"status": "cancelled", "message": "XML export cancelled by user."}
        except Exception as e:
            # Log the full exception for debugging
            print(f"[PY API save_xml_export] General exception: {e}", flush=True)
            current_app.logger.error(f"Error during XML export API call: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def save_csv_export(self):
        print("[PY API save_csv_export] Entered method.", flush=True)
        if not self.window or not self.app:
            print("[PY API save_csv_export] Error: Window or App reference not set.", flush=True)
            return {"status": "error", "message": "Window or App reference not configured."}
        try:
            print("[PY API save_csv_export] Inside try block.", flush=True)
            all_data = None
            active_custom_fields = None
            with self.app.app_context():
                print("[PY API save_csv_export] App context acquired for data fetching.", flush=True)
                all_data = get_all_patient_data_for_export()
                active_custom_fields = get_active_custom_demographic_fields() # For CSV headers
                print(f"[PY API save_csv_export] Data fetched. Patient records: {len(all_data) if all_data is not None else 'None'}", flush=True)
                print(f"[PY API save_csv_export] Active custom fields fetched: {len(active_custom_fields) if active_custom_fields is not None else 'None'}", flush=True)

            if all_data is None or active_custom_fields is None:
                print("[PY API save_csv_export] Failed to retrieve data or custom fields.", flush=True)
                return {"status": "error", "message": "Failed to retrieve data for CSV export."}
            if not all_data:
                print("[PY API save_csv_export] No patient data found.", flush=True)
                return {"status": "info", "message": "No patient data found to export as CSV."}

            print("[PY API save_csv_export] Generating CSV data...", flush=True)
            csv_files_dict = generate_patient_csvs(all_data, active_custom_fields)
            print(f"[PY API save_csv_export] CSVs generated: {list(csv_files_dict.keys())}", flush=True)

            # Create a ZIP file in memory
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for filename, content in csv_files_dict.items():
                    zip_file.writestr(filename, content.encode('utf-8')) # Ensure content is bytes
            zip_buffer.seek(0)
            print("[PY API save_csv_export] In-memory ZIP file created.", flush=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"pediatric_emr_csv_export_{timestamp}.zip"
            print(f"[PY API save_csv_export] Suggested ZIP filename: {zip_filename}", flush=True)
            
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Documents')
            if not os.path.exists(downloads_dir):
                downloads_dir = os.path.expanduser('~')

            print("[PY API save_csv_export] Calling create_file_dialog for ZIP...", flush=True)
            chosen_path = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=downloads_dir,
                save_filename=zip_filename,
                file_types=("ZIP Files (*.zip)", "All files (*.*)")
            )
            print(f"[PY API save_csv_export] create_file_dialog for ZIP returned: {chosen_path}", flush=True)

            if chosen_path and chosen_path.strip():
                print(f"[PY API save_csv_export] Path chosen for ZIP: {chosen_path}. Writing file...", flush=True)
                try:
                    with open(chosen_path, 'wb') as f:
                        f.write(zip_buffer.getvalue())
                    print(f"[PY API save_csv_export] CSVs exported to ZIP: {chosen_path}", flush=True)
                    return {"status": "success", "path": chosen_path, "message": f"Data successfully exported as CSV (zipped) to {chosen_path}"}
                except Exception as e_write:
                    print(f"[PY API save_csv_export] Error writing ZIP to {chosen_path}: {e_write}", flush=True)
                    current_app.logger.error(f"Error writing ZIP to {chosen_path}: {e_write}", exc_info=True)
                    return {"status": "error", "message": f"Failed to write ZIP file: {e_write}"}
            else:
                print("[PY API save_csv_export] ZIP export cancelled or no path chosen.", flush=True)
                return {"status": "cancelled", "message": "CSV export (ZIP) cancelled by user."}
        except Exception as e:
            print(f"[PY API save_csv_export] General exception: {e}", flush=True)
            current_app.logger.error(f"Error during CSV export API call: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

if __name__ == '__main__':
    # Start Flask app in a new thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True  # Allow main program to exit even if this thread is still running
    flask_thread.start()

    api_instance = Api() # Create an instance of the API class
    api_instance.set_app(app) # Give API access to the Flask app instance for config

    # Create a pywebview window
    # The URL should match the Flask app's host and port
    # Expose the save_chart_image function to JavaScript via js_api
    window = webview.create_window(
        APP_NAME,
        'http://127.0.0.1:9999',
        width=1200,
        height=800,
        js_api=api_instance  # Pass the class instance to js_api
    )
    api_instance.set_window(window) # Set the window reference for the API instance
    webview.start(debug=True) # This will block until the window is closed

    # Instead, just initialize the schema
    with app.app_context():
        init_db_schema()