#!/usr/bin/env python3

import tempfile
import os
import sqlite3
from csv_importer import CSVImporter

def test_french_csv_import():
    """Test CSV import with French column names like the actual export."""
    
    # Create a test CSV with French column names (like your actual export)
    test_patients_csv = '''id,mrn,nom,prenom,naissance_date,sexe,telephone,domicile
1,MRN001,Dupont,Jean,1990-01-01,M,555-1234,123 Rue Test
2,MRN002,Martin,Marie,1985-05-15,F,555-5678,456 Avenue Test'''
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='_patients.csv', delete=False) as f:
        f.write(test_patients_csv)
        test_file = f.name
    
    # Create temporary database
    temp_db = tempfile.mktemp(suffix='.db')
    
    try:
        print(f"Testing French CSV import with:")
        print(f"  CSV content:")
        print(test_patients_csv)
        print("\n" + "="*50)
        
        # Initialize importer
        importer = CSVImporter(temp_db)
        importer.clear_errors()
        
        # Try to import
        print("Starting import...")
        results = importer.import_patients_csv(test_file, update_existing=False)
        
        print(f"\nImport Results:")
        print(f"  Imported: {results.get('imported', 0)}")
        print(f"  Updated: {results.get('updated', 0)}")
        print(f"  Skipped: {results.get('skipped', 0)}")
        print(f"  Errors: {results.get('errors', 0)}")
        
        # Show detailed errors if any
        detailed_errors = importer.get_detailed_errors(limit=5)
        if detailed_errors:
            print(f"\nFirst 5 detailed errors:")
            for i, error in enumerate(detailed_errors, 1):
                print(f"  {i}. {error}")
        
        # Check database contents
        if os.path.exists(temp_db):
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM patients")
            patient_count = cursor.fetchone()[0]
            print(f"\nDatabase contents:")
            print(f"  Patients in database: {patient_count}")
            
            if patient_count > 0:
                cursor.execute("SELECT id, first_name, last_name, mrn FROM patients")
                patients = cursor.fetchall()
                print(f"  Sample patients:")
                for patient in patients:
                    print(f"    ID {patient[0]}: {patient[1]} {patient[2]} (MRN: {patient[3]})")
            
            conn.close()
        
    except Exception as e:
        print(f"ERROR during debug: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.unlink(test_file)
        if os.path.exists(temp_db):
            os.unlink(temp_db)

if __name__ == "__main__":
    test_french_csv_import() 