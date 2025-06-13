import sqlite3
import emr_config

# Get the configured database path
config = emr_config.EMRConfig()
DB_PATH = config.get_database_path()

def init_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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
        pmh TEXT,
        psh TEXT,
        medications TEXT,
        allergies TEXT,
        smoker BOOLEAN,
        smoker_details TEXT,
        alcohol BOOLEAN,
        alcohol_details TEXT,
        raw_dossier_text TEXT
    );
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        visit_date TEXT NOT NULL,
        notes TEXT,
        raw_visit_entry TEXT,
        FOREIGN KEY (patient_id) REFERENCES Patients (id)
    );
    """)
    # You can add other tables here if needed
    conn.commit()
    conn.close()
    print('Database schema initialized.')

if __name__ == '__main__':
    init_schema() 