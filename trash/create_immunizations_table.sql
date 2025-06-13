-- Create Immunizations table for unified vaccine tracking
CREATE TABLE IF NOT EXISTS Immunizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    immunization TEXT NOT NULL,
    administered_date TEXT NOT NULL,
    brand_name TEXT,
    dose_number INTEGER,
    notes TEXT,
    source TEXT DEFAULT 'manual',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES Patients(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_immunizations_patient_id ON Immunizations(patient_id);
CREATE INDEX IF NOT EXISTS idx_immunizations_immunization ON Immunizations(immunization);
CREATE INDEX IF NOT EXISTS idx_immunizations_date ON Immunizations(administered_date);

-- Create trigger to update timestamp
CREATE TRIGGER IF NOT EXISTS update_immunizations_timestamp 
    AFTER UPDATE ON Immunizations
    FOR EACH ROW
BEGIN
    UPDATE Immunizations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END; 