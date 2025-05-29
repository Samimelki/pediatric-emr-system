import sqlite3
from flask import g, current_app
import re # For validating field names

# DATABASE = 'emr_database.db' # This will now be set in app.config['DATABASE']

# Database connection helper
def get_db():
    # print("[DB get_db] Attempting to get DB connection.", flush=True) # Can be too verbose
    db = getattr(g, '_database', None)
    if db is None:
        # print("[DB get_db] No existing connection found on g, creating new.", flush=True)
        db_path = current_app.config['DATABASE']
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row # Access columns by name
        # print(f"[DB get_db] New connection established to {db_path}.", flush=True)
    # else:
        # print("[DB get_db] Reusing existing connection from g.", flush=True)
    return db

# Teardown appcontext to close connection
# This function will be registered with app.teardown_appcontext in app.py
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close() 

def init_db_schema():
    """Initializes the database with all necessary tables if they don't exist."""
    db = get_db()
    cursor = db.cursor()

    # Patients Table (revamped, English only)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mrn TEXT UNIQUE,
        first_name TEXT,
        last_name TEXT,
        date_of_birth TEXT,
        sex TEXT,
        phone TEXT,
        address TEXT,
        email TEXT,
        insurance TEXT,
        primary_physician TEXT,
        pmh TEXT,  -- Past Medical History
        psh TEXT,  -- Past Surgical History
        family_history TEXT,  -- Family History (added for Word import)
        medications TEXT,
        allergies TEXT,
        smoker BOOLEAN,
        smoker_details TEXT,
        alcohol BOOLEAN,
        alcohol_details TEXT,
        raw_dossier_text TEXT
    );
    """)

    # Ensure family_history column exists (for upgrades)
    try:
        patient_columns_cursor = db.execute("PRAGMA table_info(Patients);")
        patient_column_names = [col['name'] for col in patient_columns_cursor.fetchall()]
        if 'family_history' not in patient_column_names:
            db.execute("ALTER TABLE Patients ADD COLUMN family_history TEXT;")
            print("Added missing column family_history to Patients table during init.")
    except sqlite3.Error as e:
        print(f"Error adding family_history column during init: {e}")

    # Visits Table (modified for adult patients)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        visit_date TEXT NOT NULL,
        vital_signs TEXT,  -- JSON string containing BP, HR, Temp, etc.
        chief_complaint TEXT,
        subjective TEXT,
        objective TEXT,
        assessment TEXT,
        plan TEXT,
        notes TEXT,
        raw_visit_entry TEXT,
        FOREIGN KEY (patient_id) REFERENCES Patients (id)
    );
    """)

    # VisitAddenda Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS VisitAddenda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id INTEGER NOT NULL,
        addendum_datetime TEXT NOT NULL,
        addendum_text TEXT NOT NULL,
        raw_addendum_entry TEXT,
        FOREIGN KEY (visit_id) REFERENCES Visits(id)
    );
    """)

    # CustomDemographicFields Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS CustomDemographicFields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field_name TEXT UNIQUE NOT NULL,
        field_label TEXT NOT NULL,
        field_type TEXT NOT NULL DEFAULT 'TEXT',
        display_order INTEGER,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        display_section TEXT NOT NULL DEFAULT 'Additional Information'
    );
    """)
    
    # Ensure 'is_active' and 'display_section' columns exist
    try:
        cursor.execute("PRAGMA table_info(CustomDemographicFields);")
        columns = [column[1] for column in cursor.fetchall()]
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE CustomDemographicFields ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;")
        if 'display_section' not in columns:
            cursor.execute("ALTER TABLE CustomDemographicFields ADD COLUMN display_section TEXT NOT NULL DEFAULT 'Additional Information';")
    except sqlite3.Error as e:
        print(f"Error checking/adding columns to CustomDemographicFields: {e}")

    # Ensure all existing custom fields exist as columns in Patients table
    custom_fields = get_custom_demographic_fields(db_conn=db)
    if custom_fields:
        patient_columns_cursor = db.execute("PRAGMA table_info(Patients);")
        patient_column_names = [col['name'] for col in patient_columns_cursor.fetchall()]
        for field in custom_fields:
            if field['field_name'] not in patient_column_names:
                try:
                    db.execute(f"ALTER TABLE Patients ADD COLUMN {field['field_name']} TEXT;")
                    print(f"Added missing column {field['field_name']} to Patients table during init.")
                except sqlite3.Error as e:
                    print(f"Error adding missing column {field['field_name']} during init: {e}")

    db.commit()
    print("Database schema initialized or verified.")

def get_custom_demographic_fields(db_conn=None):
    """Fetches all defined custom demographic fields (active and inactive), ordered by display_order, then id."""
    if db_conn:
        conn = db_conn
    else:
        conn = get_db()
    cursor = conn.execute("SELECT id, field_name, field_label, field_type, display_order, is_active, display_section FROM CustomDemographicFields ORDER BY display_order ASC, id ASC;")
    fields = cursor.fetchall()
    return fields

def get_active_custom_demographic_fields(db_conn=None):
    """Fetches only active custom demographic fields, ordered by display_order, then id."""
    if db_conn:
        conn = db_conn
    else:
        conn = get_db()
    # Query for active fields
    cursor = conn.execute("SELECT id, field_name, field_label, field_type, display_order, display_section FROM CustomDemographicFields WHERE is_active = TRUE ORDER BY display_order ASC, id ASC;")
    fields = cursor.fetchall()
    return fields

def add_custom_demographic_field(field_label: str, field_name_suggestion: str, field_type: str = 'TEXT', display_section: str = 'Additional Information'):
    """
    Adds a new custom demographic field.
    - field_label: User-friendly label (e.g., "Nationality").
    - field_name_suggestion: User's suggestion for field name (e.g., "nationality").
                         This will be sanitized and prefixed.
    - field_type: Data type, defaults to 'TEXT'. SQLite types like TEXT, INTEGER, REAL.
    - display_section: The section where this field should be displayed.
    Returns: (bool_success, message_or_error_string)
    """
    db = get_db()
    
    # Sanitize and create the actual column name
    # Must start with a letter, can contain letters, numbers, underscores.
    # We will prefix with "custom_" to avoid conflicts and for clarity.
    sanitized_suggestion = re.sub(r'\W|^(?=\d)', '_', field_name_suggestion.lower().strip().replace(' ', '_'))
    if not sanitized_suggestion:
        return False, "Invalid field name suggestion. Please use alphanumeric characters."
    
    field_name = f"custom_{sanitized_suggestion}"
    
    # Validate field_type (basic validation for now)
    allowed_types = ['TEXT', 'INTEGER', 'REAL', 'DATE'] # DATE is just TEXT in SQLite but good for convention
    if field_type.upper() not in allowed_types:
        return False, f"Invalid field type '{field_type}'. Allowed types are: {', '.join(allowed_types)}"
    actual_field_type = field_type.upper() # Store in uppercase for consistency

    # Check if field_name (column name) already exists in Patients table or CustomDemographicFields
    try:
        cursor = db.execute("SELECT COUNT(*) FROM CustomDemographicFields WHERE field_name = ?", (field_name,))
        if cursor.fetchone()[0] > 0:
            return False, f"A custom field with the internal name '{field_name}' already exists."

        # Check against actual Patient table columns (though prefixing should mostly avoid this)
        patient_cols_cursor = db.execute("PRAGMA table_info(Patients);").fetchall()
        existing_patient_cols = [col['name'] for col in patient_cols_cursor]
        if field_name in existing_patient_cols:
             return False, f"A column with the name '{field_name}' already exists in the Patients table."

        # Add to CustomDemographicFields metadata table
        # is_active defaults to TRUE via table schema
        db.execute("INSERT INTO CustomDemographicFields (field_name, field_label, field_type, display_section) VALUES (?, ?, ?, ?)",
                   (field_name, field_label, actual_field_type, display_section))
        
        # Add column to Patients table
        # Note: Be very careful with f-strings in SQL if field_name wasn't sanitized.
        # Here, field_name is constructed by us and sanitized, so it should be safe.
        db.execute(f"ALTER TABLE Patients ADD COLUMN {field_name} {actual_field_type};")
        
        db.commit()
        return True, f"Custom field '{field_label}' (as {field_name}) added successfully."
    except sqlite3.IntegrityError as e:
        db.rollback()
        return False, f"Database integrity error (e.g., field name not unique or other constraint): {e}"
    except sqlite3.Error as e:
        db.rollback()
        return False, f"Database error: {e}"
    except Exception as e:
        db.rollback()
        return False, f"An unexpected error occurred: {e}"

def set_custom_field_active_status(field_id: int, is_active: bool):
    """Sets the is_active status for a given custom field."""
    db = get_db()
    try:
        db.execute("UPDATE CustomDemographicFields SET is_active = ? WHERE id = ?", (is_active, field_id))
        db.commit()
        return True, "Field active status updated."
    except sqlite3.Error as e:
        db.rollback()
        return False, f"Database error: {e}"

def get_all_patient_data_for_export():
    """Fetches all patient data, including custom fields, visits, and non-standard vaccines for XML export."""
    print("[DB get_all_patient_data_for_export] Entered function.", flush=True)
    db = get_db()
    print("[DB get_all_patient_data_for_export] DB connection obtained.", flush=True)

    # 1. Fetch all patients
    print("[DB get_all_patient_data_for_export] Fetching all patients...", flush=True)
    patients_cursor = db.execute("SELECT * FROM Patients ORDER BY id ASC")
    all_patient_rows = patients_cursor.fetchall()
    print(f"[DB get_all_patient_data_for_export] Fetched {len(all_patient_rows)} patients.", flush=True)

    # 2. Fetch all visits and group by patient_id
    print("[DB get_all_patient_data_for_export] Fetching all visits...", flush=True)
    visits_cursor = db.execute("SELECT * FROM Visits ORDER BY patient_id, visit_date ASC")
    all_visits = visits_cursor.fetchall()
    visits_by_patient_id = {}
    for visit_row in all_visits:
        pid = visit_row['patient_id']
        if pid not in visits_by_patient_id:
            visits_by_patient_id[pid] = []
        visits_by_patient_id[pid].append(dict(visit_row))
    print(f"[DB get_all_patient_data_for_export] Fetched and grouped {len(all_visits)} visits for {len(visits_by_patient_id)} patients.", flush=True)

    # 4. Fetch active custom field metadata
    print("[DB get_all_patient_data_for_export] Fetching active custom field metadata...", flush=True)
    custom_fields_meta = get_active_custom_demographic_fields(db_conn=db)
    print(f"[DB get_all_patient_data_for_export] Fetched {len(custom_fields_meta)} active custom fields metadata.", flush=True)

    patients_data = []
    patient_count = 0
    for patient_row in all_patient_rows:
        patient_count += 1
        # print(f"[DB get_all_patient_data_for_export] Processing patient {patient_count}/{len(all_patient_rows)}, ID: {patient_row['id']}", flush=True) # Can be too verbose
        patient_dict = dict(patient_row)
        patient_id = patient_row['id']

        # Add custom fields
        patient_dict['custom_fields'] = []
        for cf_meta in custom_fields_meta:
            field_name = cf_meta['field_name']
            if field_name in patient_row.keys() and patient_row[field_name] is not None:
                patient_dict['custom_fields'].append({
                    'field_name': field_name,
                    'field_label': cf_meta['field_label'],
                    'value': patient_row[field_name],
                    'type': cf_meta['field_type']
                })
            if field_name in patient_dict:
                del patient_dict[field_name]

        # Add pre-fetched visits
        patient_dict['visits'] = visits_by_patient_id.get(patient_id, [])
        
        patients_data.append(patient_dict)
    
    print("[DB get_all_patient_data_for_export] Finished processing all patients. Returning data.", flush=True)
    return patients_data

# Example of how you might get a specific patient's data including custom fields:
# def get_patient_with_custom_fields(patient_id):
#     db = get_db()
#     custom_fields_meta = get_active_custom_demographic_fields(db_conn=db) # Use active fields
#     
#     # Base query for standard patient fields
#     patient_query = "SELECT * FROM Patients WHERE id = ?"
#     patient_cursor = db.execute(patient_query, (patient_id,))
#     patient_data_row = patient_cursor.fetchone()
#     
#     if not patient_data_row:
#         return None
# 
#     patient_data = dict(patient_data_row) # Convert to mutable dict
# 
#     # Fetch values for custom fields for this patient
#     # This part needs to be dynamic based on the columns actually present on the patient_data_row
#     # If a custom field was added AFTER the patient record was created, that column won't be in patient_data_row directly
#     # A safer way is to query them explicitly IF they exist for that patient_id
#     # However, since ALTER TABLE adds NULLs, they *should* be there if queried via SELECT *.
# 
#     # For simplicity, we assume ALTER TABLE worked and the columns exist in the row if SELECT * was used.
#     # The patient_data dict will automatically contain these custom columns as keys if SELECT * was used.
#     # We just need to pass along the metadata for the template to know how to label them.
# 
#     return patient_data, custom_fields_meta 