-- Create unified Immunizations table for all vaccines
-- This replaces the need for separate standard vaccine columns and NonStandardVaccines table

CREATE TABLE IF NOT EXISTS Immunizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    immunization TEXT NOT NULL,          -- Canonical disease name (e.g., "Hepatitis A", "DTaP - IPV")
    administered_date DATE NOT NULL,     -- Date vaccine was given
    brand_name TEXT,                     -- Original vaccine brand name (e.g., "EPAXAL", "TETRAVAC")
    dose_number INTEGER,                 -- Dose sequence (1, 2, 3, etc.)
    notes TEXT,                          -- Optional notes from provider
    source TEXT DEFAULT 'manual',       -- 'import', 'manual', 'migration'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    FOREIGN KEY (patient_id) REFERENCES Patients(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_immunizations_patient_id ON Immunizations(patient_id);
CREATE INDEX IF NOT EXISTS idx_immunizations_disease ON Immunizations(immunization);
CREATE INDEX IF NOT EXISTS idx_immunizations_date ON Immunizations(administered_date);

-- Create trigger to update updated_at timestamp
CREATE TRIGGER IF NOT EXISTS update_immunizations_timestamp 
    AFTER UPDATE ON Immunizations
    FOR EACH ROW
BEGIN
    UPDATE Immunizations SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END; 