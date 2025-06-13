import sqlite3

# Direct database creation without Flask context
conn = sqlite3.connect('unified_emr.db')
cursor = conn.cursor()

# Create NonStandardVaccines table directly
cursor.execute('''
CREATE TABLE IF NOT EXISTS NonStandardVaccines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    vaccine_name TEXT,
    vaccine_date TEXT,
    dose_number INTEGER DEFAULT 1,
    interval_months INTEGER,
    total_doses_planned INTEGER DEFAULT 1,
    batch_number TEXT,
    administrator TEXT,
    reaction_notes TEXT,
    raw_entry TEXT,
    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES Patients (id)
);
''')

conn.commit()
conn.close()
print('NonStandardVaccines table created with correct schema!') 