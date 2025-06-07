import sqlite3
from flask import g, current_app
import re
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from emr_config import emr_config

# Database connection helper (unchanged from original)
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db_path = current_app.config['DATABASE']
        db = g._database = sqlite3.connect(db_path)
        db.row_factory = sqlite3.Row
    return db

# Teardown appcontext to close connection
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_unified_db_schema():
    """Initializes the unified database schema supporting both adult and pediatric EMR."""
    db = get_db()
    cursor = db.cursor()

    # UNIFIED PATIENTS TABLE - Combines adult and pediatric fields
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mrn TEXT UNIQUE,
        mrn_agg TEXT,  -- From pediatric system
        
        -- Unified Name Fields (English/French support)
        first_name TEXT,
        last_name TEXT,
        prenom TEXT,     -- French first name (pediatric)
        nom TEXT,        -- French last name (pediatric)
        
        -- Birth Information
        date_of_birth TEXT,
        naissance_date TEXT,  -- French birth date (pediatric)
        birth_weight_g INTEGER,
        birth_height_cm REAL,
        birth_head_circumference_cm REAL,
        birth_notes TEXT,
        
        -- Demographics
        sex TEXT,
        sexe TEXT,       -- French gender (pediatric)
        
        -- Contact Information
        phone TEXT,
        telephone TEXT,  -- French phone (pediatric)
        address TEXT,
        domicile TEXT,   -- French address (pediatric)
        email TEXT,
        
        -- Medical Information - Adult Fields
        insurance TEXT,
        primary_physician TEXT,
        pmh TEXT,               -- Past Medical History
        psh TEXT,               -- Past Surgical History
        family_history TEXT,
        medications TEXT,
        allergies TEXT,
        smoker BOOLEAN,
        smoker_details TEXT,
        alcohol BOOLEAN,
        alcohol_details TEXT,
        
        -- Medical Information - Pediatric Fields
        mere_nom TEXT,          -- Mother's name
        pere_nom TEXT,          -- Father's name
        pediatre_initiales TEXT, -- Pediatrician initials
        third_party_payer TEXT,
        hopital TEXT,           -- Hospital
        diag1 TEXT,
        diag2 TEXT,
        obstetrical_history TEXT,
        
        -- Test Results (Pediatric)
        monotest1 TEXT,
        monotest2 TEXT,
        monotest3 TEXT,
        
        -- Standard Vaccines (Pediatric)
        rougeole_seule_date TEXT,   -- Measles alone
        dtcp1_date TEXT,
        dtcp2_date TEXT,
        dtcp3_date TEXT,
        dtcp_rappel1_date TEXT,     -- Booster shots
        dtcp_rappel2_date TEXT,
        dtcp_rappel3_date TEXT,
        dtcp_rappel4_date TEXT,
        hep_b1_date TEXT,
        hep_b2_date TEXT,
        hep_b3_date TEXT,
        hib1_date TEXT,
        hib2_date TEXT,
        hib3_date TEXT,
        hib_rappel_date TEXT,
        ror_date TEXT,              -- MMR vaccine
        
        -- Raw Text Fields
        raw_dossier_text TEXT,
        raw_autres_vaccins_text TEXT, -- Other vaccines text
        
        -- Metadata
        created_date TEXT DEFAULT CURRENT_TIMESTAMP,
        modified_date TEXT DEFAULT CURRENT_TIMESTAMP,
        emr_mode TEXT DEFAULT 'mixed'  -- Track which mode created this patient
    );
    """)

    # UNIFIED VISITS TABLE - Supports both adult and pediatric visit types
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        visit_date TEXT NOT NULL,
        
        -- Adult Visit Fields
        vital_signs TEXT,           -- JSON string containing BP, HR, Temp, etc.
        chief_complaint TEXT,
        subjective TEXT,
        objective TEXT,
        assessment TEXT,
        plan TEXT,
        
        -- Pediatric Visit Fields  
        weight_g INTEGER,           -- Weight in grams (pediatric)
        weight_kg REAL,             -- Weight in kg (adult)
        height_cm REAL,
        head_circumference_cm REAL,
        
        -- Shared Fields
        notes TEXT,
        raw_visit_entry TEXT,
        
        -- Metadata
        visit_type TEXT,            -- 'adult', 'pediatric', 'mixed'
        created_date TEXT DEFAULT CURRENT_TIMESTAMP,
        
        FOREIGN KEY (patient_id) REFERENCES Patients (id)
    );
    """)

    # NON-STANDARD VACCINES TABLE (Pediatric feature)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS NonStandardVaccines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        vaccine_name TEXT,
        vaccine_date TEXT,
        batch_number TEXT,
        administrator TEXT,
        reaction_notes TEXT,
        raw_entry TEXT,
        created_date TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES Patients (id)
    );
    """)

    # VISIT ADDENDA TABLE (Shared)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS VisitAddenda (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id INTEGER NOT NULL,
        addendum_datetime TEXT NOT NULL,
        addendum_text TEXT NOT NULL,
        raw_addendum_entry TEXT,
        created_by TEXT,
        FOREIGN KEY (visit_id) REFERENCES Visits(id)
    );
    """)

    # VISIT MEDIA TABLE (Enhanced from current system)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS VisitMedia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        visit_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        original_filename TEXT,
        media_type TEXT NOT NULL,
        file_size INTEGER,
        upload_date TEXT NOT NULL,
        description TEXT,
        tags TEXT,  -- JSON array of tags
        FOREIGN KEY (visit_id) REFERENCES Visits(id)
    );
    """)

    # GROWTH MEASUREMENTS TABLE (Pediatric feature)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS GrowthMeasurements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        measurement_date TEXT NOT NULL,
        age_days INTEGER,
        weight_g INTEGER,
        height_cm REAL,
        head_circumference_cm REAL,
        weight_percentile REAL,
        height_percentile REAL,
        head_circumference_percentile REAL,
        notes TEXT,
        who_standards_version TEXT DEFAULT 'WHO2006',
        FOREIGN KEY (patient_id) REFERENCES Patients (id)
    );
    """)

    # CUSTOM DEMOGRAPHIC FIELDS TABLE (Enhanced)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS CustomDemographicFields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field_name TEXT UNIQUE NOT NULL,
        field_label TEXT NOT NULL,
        field_label_fr TEXT,        -- French label
        field_type TEXT NOT NULL DEFAULT 'TEXT',
        display_order INTEGER,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        display_section TEXT NOT NULL DEFAULT 'Additional Information',
        display_section_fr TEXT DEFAULT 'Informations Supplémentaires',
        emr_mode_restriction TEXT,  -- 'adult', 'pediatric', 'mixed', NULL for all
        validation_rules TEXT,      -- JSON string for validation rules
        default_value TEXT,
        help_text TEXT,
        help_text_fr TEXT,
        created_date TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # EMR CONFIGURATION AUDIT TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ConfigurationAudit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        change_date TEXT DEFAULT CURRENT_TIMESTAMP,
        emr_mode_from TEXT,
        emr_mode_to TEXT,
        features_changed TEXT,  -- JSON string of changed features
        changed_by TEXT,
        reason TEXT
    );
    """)

    # DATA MIGRATION TRACKING TABLE
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS DataMigrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        migration_name TEXT UNIQUE NOT NULL,
        applied_date TEXT DEFAULT CURRENT_TIMESTAMP,
        source_system TEXT,         -- 'adult_emr', 'pediatric_emr'
        records_migrated INTEGER,
        migration_notes TEXT
    );
    """)

    # Add indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_mrn ON Patients(mrn);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_names ON Patients(first_name, last_name, prenom, nom);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_visits_patient_date ON Visits(patient_id, visit_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_visits_date ON Visits(visit_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_growth_patient_date ON GrowthMeasurements(patient_id, measurement_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vaccines_patient ON NonStandardVaccines(patient_id);")

    # Perform any necessary schema upgrades
    _perform_schema_upgrades(db)
    
    db.commit()
    print("Unified database schema initialized successfully.")

def _perform_schema_upgrades(db):
    """Perform incremental schema upgrades for existing databases."""
    cursor = db.cursor()
    
    # Check if we need to add new columns to existing tables
    upgrades = [
        # Patients table upgrades
        ("Patients", "created_date", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ("Patients", "modified_date", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        ("Patients", "emr_mode", "TEXT DEFAULT 'mixed'"),
        ("Patients", "prenom", "TEXT"),
        ("Patients", "nom", "TEXT"),
        ("Patients", "naissance_date", "TEXT"),
        ("Patients", "birth_weight_g", "INTEGER"),
        ("Patients", "birth_height_cm", "REAL"),
        ("Patients", "birth_head_circumference_cm", "REAL"),
        ("Patients", "birth_notes", "TEXT"),
        ("Patients", "sexe", "TEXT"),
        ("Patients", "telephone", "TEXT"),
        ("Patients", "domicile", "TEXT"),
        ("Patients", "mere_nom", "TEXT"),
        ("Patients", "pere_nom", "TEXT"),
        ("Patients", "pediatre_initiales", "TEXT"),
        ("Patients", "third_party_payer", "TEXT"),
        ("Patients", "hopital", "TEXT"),
        ("Patients", "family_history", "TEXT"),
        
        # Visits table upgrades
        ("Visits", "weight_kg", "REAL"),
        ("Visits", "visit_type", "TEXT"),
        ("Visits", "created_date", "TEXT DEFAULT CURRENT_TIMESTAMP"),
        
        # VisitMedia upgrades
        ("VisitMedia", "original_filename", "TEXT"),
        ("VisitMedia", "file_size", "INTEGER"),
        ("VisitMedia", "tags", "TEXT"),
        
        # CustomDemographicFields upgrades
        ("CustomDemographicFields", "field_label_fr", "TEXT"),
        ("CustomDemographicFields", "display_section_fr", "TEXT DEFAULT 'Informations Supplémentaires'"),
        ("CustomDemographicFields", "emr_mode_restriction", "TEXT"),
        ("CustomDemographicFields", "validation_rules", "TEXT"),
        ("CustomDemographicFields", "default_value", "TEXT"),
        ("CustomDemographicFields", "help_text", "TEXT"),
        ("CustomDemographicFields", "help_text_fr", "TEXT"),
        ("CustomDemographicFields", "created_date", "TEXT DEFAULT CURRENT_TIMESTAMP"),
    ]
    
    for table_name, column_name, column_def in upgrades:
        try:
            # Check if column exists
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [col[1] for col in cursor.fetchall()]
            
            if column_name not in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def};")
                print(f"Added column {column_name} to {table_name} table.")
        except sqlite3.Error as e:
            print(f"Error adding column {column_name} to {table_name}: {e}")

    # Ensure custom fields exist as columns in Patients table
    custom_fields = get_custom_demographic_fields(db_conn=db)
    if custom_fields:
        cursor.execute("PRAGMA table_info(Patients);")
        patient_columns = [col[1] for col in cursor.fetchall()]
        
        for field in custom_fields:
            if field['field_name'] not in patient_columns:
                try:
                    cursor.execute(f"ALTER TABLE Patients ADD COLUMN {field['field_name']} TEXT;")
                    print(f"Added custom field column {field['field_name']} to Patients table.")
                except sqlite3.Error as e:
                    print(f"Error adding custom field column {field['field_name']}: {e}")

def get_patient_unified_data(patient_id: int, mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get patient data formatted according to the current EMR mode."""
    if mode is None:
        mode = emr_config.get_emr_mode()
    
    db = get_db()
    cursor = db.execute("SELECT * FROM Patients WHERE id = ?", (patient_id,))
    patient = cursor.fetchone()
    
    if not patient:
        return None
    
    # Convert to dictionary for easier manipulation
    patient_dict = dict(patient)
    
        # Apply mode-specific field mapping
    if mode == 'adult':
        # Prefer English fields, hide pediatric-specific data
        patient_dict = _map_to_adult_fields(patient_dict)
    elif mode == 'pediatric':
        # Prefer French fields, show pediatric data
        patient_dict = _map_to_pediatric_fields(patient_dict)
    else:  # MIXED mode
        # Show all available data with preference based on config
        patient_dict = _map_to_mixed_fields(patient_dict)
    
    return patient_dict

def _map_to_adult_fields(patient_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Map patient data to adult EMR field preferences."""
    # Use English names if available, fallback to French
    if not patient_dict.get('first_name') and patient_dict.get('prenom'):
        patient_dict['first_name'] = patient_dict['prenom']
    if not patient_dict.get('last_name') and patient_dict.get('nom'):
        patient_dict['last_name'] = patient_dict['nom']
    if not patient_dict.get('date_of_birth') and patient_dict.get('naissance_date'):
        patient_dict['date_of_birth'] = patient_dict['naissance_date']
    if not patient_dict.get('sex') and patient_dict.get('sexe'):
        patient_dict['sex'] = patient_dict['sexe']
    if not patient_dict.get('phone') and patient_dict.get('telephone'):
        patient_dict['phone'] = patient_dict['telephone']
    if not patient_dict.get('address') and patient_dict.get('domicile'):
        patient_dict['address'] = patient_dict['domicile']
    
    return patient_dict

def _map_to_pediatric_fields(patient_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Map patient data to pediatric EMR field preferences."""
    # Use French names if available, fallback to English
    if not patient_dict.get('prenom') and patient_dict.get('first_name'):
        patient_dict['prenom'] = patient_dict['first_name']
    if not patient_dict.get('nom') and patient_dict.get('last_name'):
        patient_dict['nom'] = patient_dict['last_name']
    if not patient_dict.get('naissance_date') and patient_dict.get('date_of_birth'):
        patient_dict['naissance_date'] = patient_dict['date_of_birth']
    if not patient_dict.get('sexe') and patient_dict.get('sex'):
        patient_dict['sexe'] = patient_dict['sex']
    if not patient_dict.get('telephone') and patient_dict.get('phone'):
        patient_dict['telephone'] = patient_dict['phone']
    if not patient_dict.get('domicile') and patient_dict.get('address'):
        patient_dict['domicile'] = patient_dict['address']
    
    return patient_dict

def _map_to_mixed_fields(patient_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Map patient data for mixed mode (show all, prefer based on config)."""
    # Use the configuration to determine field preferences
    config_uses_adult_naming = emr_config.config.get('patient_form', {}).get(
        'mixed_mode_field_mapping', {}
    ).get('use_adult_naming', True)
    
    if config_uses_adult_naming:
        return _map_to_adult_fields(patient_dict)
    else:
        return _map_to_pediatric_fields(patient_dict)

def get_visit_unified_data(visit_id: int, mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get visit data formatted according to the current EMR mode."""
    if mode is None:
        mode = emr_config.get_emr_mode()
    
    # Extract string value if mode is an EMRMode object (for backward compatibility)
    if hasattr(mode, 'value'):
        mode = mode.value
    
    db = get_db()
    cursor = db.execute("SELECT * FROM Visits WHERE id = ?", (visit_id,))
    visit = cursor.fetchone()
    
    if not visit:
        return None
    
    visit_dict = dict(visit)
    
    # Parse vital signs JSON if present
    if visit_dict.get('vital_signs'):
        try:
            visit_dict['vital_signs_parsed'] = json.loads(visit_dict['vital_signs'])
        except json.JSONDecodeError:
            visit_dict['vital_signs_parsed'] = {}
    
    return visit_dict

def save_patient_unified(patient_data: Dict[str, Any], mode: Optional[str] = None) -> int:
    """Save patient data with unified field mapping."""
    if mode is None:
        mode = emr_config.get_emr_mode()
    
    # Extract string value if mode is an EMRMode object (for backward compatibility)
    if hasattr(mode, 'value'):
        mode = mode.value
    
    db = get_db()
    
    # Prepare data with proper field mapping
    save_data = patient_data.copy()
    save_data['emr_mode'] = mode
    save_data['modified_date'] = datetime.now().isoformat()
    
    # Apply bidirectional field mapping to ensure data is saved in both formats when possible
    _apply_bidirectional_mapping(save_data)
    
    if save_data.get('id'):
        # Update existing patient
        return _update_patient_unified(save_data)
    else:
        # Insert new patient
        return _insert_patient_unified(save_data)

def _apply_bidirectional_mapping(patient_data: Dict[str, Any]):
    """Apply bidirectional field mapping to ensure compatibility."""
    # English to French mapping
    if patient_data.get('first_name') and not patient_data.get('prenom'):
        patient_data['prenom'] = patient_data['first_name']
    if patient_data.get('last_name') and not patient_data.get('nom'):
        patient_data['nom'] = patient_data['last_name']
    if patient_data.get('date_of_birth') and not patient_data.get('naissance_date'):
        patient_data['naissance_date'] = patient_data['date_of_birth']
    if patient_data.get('sex') and not patient_data.get('sexe'):
        patient_data['sexe'] = patient_data['sex']
    if patient_data.get('phone') and not patient_data.get('telephone'):
        patient_data['telephone'] = patient_data['phone']
    if patient_data.get('address') and not patient_data.get('domicile'):
        patient_data['domicile'] = patient_data['address']
    
    # French to English mapping
    if patient_data.get('prenom') and not patient_data.get('first_name'):
        patient_data['first_name'] = patient_data['prenom']
    if patient_data.get('nom') and not patient_data.get('last_name'):
        patient_data['last_name'] = patient_data['nom']
    if patient_data.get('naissance_date') and not patient_data.get('date_of_birth'):
        patient_data['date_of_birth'] = patient_data['naissance_date']
    if patient_data.get('sexe') and not patient_data.get('sex'):
        patient_data['sex'] = patient_data['sexe']
    if patient_data.get('telephone') and not patient_data.get('phone'):
        patient_data['phone'] = patient_data['telephone']
    if patient_data.get('domicile') and not patient_data.get('address'):
        patient_data['address'] = patient_data['domicile']

def _insert_patient_unified(patient_data: Dict[str, Any]) -> int:
    """Insert new patient with unified data."""
    db = get_db()
    
    # Get all column names from Patients table
    cursor = db.execute("PRAGMA table_info(Patients);")
    columns = [col[1] for col in cursor.fetchall() if col[1] != 'id']
    
    # Prepare insert data only for existing columns
    insert_data = {}
    for column in columns:
        if column in patient_data:
            insert_data[column] = patient_data[column]
    
    if not insert_data.get('created_date'):
        insert_data['created_date'] = datetime.now().isoformat()
    
    # Build INSERT query
    placeholders = ', '.join(['?' for _ in insert_data])
    column_names = ', '.join(insert_data.keys())
    
    query = f"INSERT INTO Patients ({column_names}) VALUES ({placeholders})"
    
    cursor = db.execute(query, list(insert_data.values()))
    patient_id = cursor.lastrowid
    db.commit()
    
    return patient_id

def _update_patient_unified(patient_data: Dict[str, Any]) -> int:
    """Update existing patient with unified data."""
    db = get_db()
    patient_id = patient_data['id']
    
    # Get all column names from Patients table
    cursor = db.execute("PRAGMA table_info(Patients);")
    columns = [col[1] for col in cursor.fetchall() if col[1] not in ('id', 'created_date')]
    
    # Prepare update data only for existing columns
    update_data = {}
    for column in columns:
        if column in patient_data:
            update_data[column] = patient_data[column]
    
    if update_data:
        # Build UPDATE query
        set_clause = ', '.join([f"{col} = ?" for col in update_data.keys()])
        query = f"UPDATE Patients SET {set_clause} WHERE id = ?"
        
        db.execute(query, list(update_data.values()) + [patient_id])
        db.commit()
    
    return patient_id

def get_custom_demographic_fields(db_conn=None, mode: Optional[str] = None):
    """Get custom demographic fields filtered by EMR mode."""
    if mode is None:
        mode = emr_config.get_emr_mode()
    
    # Extract string value if mode is an EMRMode object (for backward compatibility)
    if hasattr(mode, 'value'):
        mode = mode.value
    
    if db_conn:
        conn = db_conn
    else:
        conn = get_db()
    
    query = """
    SELECT id, field_name, field_label, field_label_fr, field_type, display_order, 
           is_active, display_section, display_section_fr, emr_mode_restriction
    FROM CustomDemographicFields 
    WHERE is_active = TRUE 
    AND (emr_mode_restriction IS NULL OR emr_mode_restriction = ? OR emr_mode_restriction = 'mixed')
    ORDER BY display_order ASC, id ASC
    """
    
    cursor = conn.execute(query, (mode,))
    return cursor.fetchall()

def get_active_custom_demographic_fields(db_conn=None, mode: Optional[str] = None):
    """Fetches only active custom demographic fields for the current mode."""
    return get_custom_demographic_fields(db_conn, mode)

def migrate_from_legacy_database(source_db_path: str, source_type: str) -> Dict[str, int]:
    """Migrate data from legacy adult or pediatric EMR database."""
    migration_stats = {
        'patients_migrated': 0,
        'visits_migrated': 0,
        'errors': 0
    }
    
    try:
        # Connect to source database
        source_conn = sqlite3.connect(source_db_path)
        source_conn.row_factory = sqlite3.Row
        
        # Get destination database
        dest_db = get_db()
        
        # Record migration start
        dest_db.execute("""
        INSERT INTO DataMigrations (migration_name, source_system, migration_notes)
        VALUES (?, ?, ?)
        """, (f"migration_{source_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}", 
              source_type, f"Migrating from {source_db_path}"))
        
        if source_type == 'adult_emr':
            migration_stats = _migrate_adult_data(source_conn, dest_db, migration_stats)
        elif source_type == 'pediatric_emr':
            migration_stats = _migrate_pediatric_data(source_conn, dest_db, migration_stats)
        
        # Update migration record
        dest_db.execute("""
        UPDATE DataMigrations 
        SET records_migrated = ?, migration_notes = migration_notes || ?
        WHERE migration_name LIKE ?
        """, (migration_stats['patients_migrated'] + migration_stats['visits_migrated'],
              f" | Results: {migration_stats}",
              f"migration_{source_type}_%"))
        
        dest_db.commit()
        source_conn.close()
        
    except Exception as e:
        print(f"Migration error: {e}")
        migration_stats['errors'] += 1
    
    return migration_stats

def _migrate_adult_data(source_conn, dest_db, stats):
    """Migrate data from adult EMR system."""
    # Migrate patients
    cursor = source_conn.execute("SELECT * FROM Patients")
    for patient in cursor.fetchall():
        try:
            patient_dict = dict(patient)
            patient_dict['emr_mode'] = 'adult'
            patient_dict.pop('id', None)  # Remove ID to get new one
            _insert_patient_unified(patient_dict)
            stats['patients_migrated'] += 1
        except Exception as e:
            print(f"Error migrating adult patient {patient.get('id', 'unknown')}: {e}")
            stats['errors'] += 1
    
    return stats

def _migrate_pediatric_data(source_conn, dest_db, stats):
    """Migrate data from pediatric EMR system."""
    # Migrate patients
    cursor = source_conn.execute("SELECT * FROM Patients")
    for patient in cursor.fetchall():
        try:
            patient_dict = dict(patient)
            patient_dict['emr_mode'] = 'pediatric'
            patient_dict.pop('id', None)  # Remove ID to get new one
            _insert_patient_unified(patient_dict)
            stats['patients_migrated'] += 1
        except Exception as e:
            print(f"Error migrating pediatric patient {patient.get('id', 'unknown')}: {e}")
            stats['errors'] += 1
    
    return stats

# Initialize the schema (called from app startup)
init_db_schema = init_unified_db_schema

# Legacy function compatibility
def get_all_patient_data_for_export():
    """Get all patient data for export (maintains compatibility)."""
    db = get_db()
    cursor = db.execute("SELECT * FROM Patients ORDER BY id")
    return cursor.fetchall() 