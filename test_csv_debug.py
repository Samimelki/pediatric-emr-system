#!/usr/bin/env python3

import tempfile
import os
from csv_importer import CSVImporter

def test_csv_import():
    """Test CSV import with a simple case to identify issues."""
    
    # Create a simple test CSV for patients
    test_patients_csv = '''id,first_name,last_name,date_of_birth,sex,phone,address,email,insurance,primary_physician,pmh,psh,family_history,medications,allergies,smoker,smoker_details,alcohol,alcohol_details,raw_dossier_text
1,Test,Patient,1990-01-01,M,555-1234,123 Test St,test@example.com,Test Insurance,Dr. Test,None,None,None,None,None,0,,0,,Test patient data'''
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='_patients.csv', delete=False) as f:
        f.write(test_patients_csv)
        test_file = f.name
    
    try:
        print(f"Testing CSV import with file: {test_file}")
        
        # Test with temporary database
        test_db = '/tmp/test_csv_import.db'
        if os.path.exists(test_db):
            os.remove(test_db)
        
        importer = CSVImporter(test_db)
        print("CSV Importer created successfully")
        
        # Test import
        result = importer.import_patients_csv(test_file, False)
        print(f"Import result: {result}")
        
        # Check for errors
        errors = importer.get_detailed_errors()
        if errors:
            print(f"Detailed errors: {errors}")
        else:
            print("No detailed errors found")
            
        # Test with bundle import
        temp_dir = tempfile.mkdtemp()
        bundle_file = os.path.join(temp_dir, 'patients.csv')
        with open(bundle_file, 'w') as f:
            f.write(test_patients_csv)
        
        print(f"\nTesting bundle import from directory: {temp_dir}")
        bundle_result = importer.import_csv_bundle(temp_dir, False)
        print(f"Bundle import result: {bundle_result}")
        
        # Clean up
        os.remove(bundle_file)
        os.rmdir(temp_dir)
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists(test_db):
            os.remove(test_db)

if __name__ == "__main__":
    test_csv_import() 