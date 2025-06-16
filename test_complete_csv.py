#!/usr/bin/env python3

import tempfile
import os
import sqlite3
from csv_importer import CSVImporter

def test_complete_csv_import():
    """Test complete CSV import with patients, visits, and immunizations."""
    
    # Create test CSVs with the exact format your system exports
    test_patients_csv = '''id,mrn,nom,prenom,naissance_date,sexe,telephone,domicile
1,MRN001,Dupont,Jean,1990-01-01,M,555-1234,123 Rue Test
2,MRN002,Martin,Marie,1985-05-15,F,555-5678,456 Avenue Test'''
    
    test_visits_csv = '''patient_id,patient_mrn,id,visit_date,weight_g,height_cm,head_circumference_cm,notes,raw_visit_entry
1,MRN001,101,2023-01-15,5000,50,35,Routine checkup,Visit notes here
2,MRN002,102,2023-02-20,4500,48,33,Follow-up visit,Follow-up notes'''
    
    test_immunizations_csv = '''patient_id,patient_mrn,id,immunization,administered_date,brand_name,dose_number,notes,source,created_at
1,MRN001,201,DTaP - IPV,2023-01-15,Pentacel,1,First dose,import,2023-01-15
1,MRN001,202,Hepatitis B,2023-01-15,Engerix-B,1,Birth dose,import,2023-01-15
2,MRN002,203,MMR (Measles Mumps Rubella),2023-02-20,M-M-R II,1,First MMR,import,2023-02-20'''
    
    # Create temporary directory and files
    temp_dir = tempfile.mkdtemp()
    
    patients_file = os.path.join(temp_dir, 'patients.csv')
    visits_file = os.path.join(temp_dir, 'visits.csv')
    immunizations_file = os.path.join(temp_dir, 'immunizations.csv')
    
    with open(patients_file, 'w') as f:
        f.write(test_patients_csv)
    with open(visits_file, 'w') as f:
        f.write(test_visits_csv)
    with open(immunizations_file, 'w') as f:
        f.write(test_immunizations_csv)
    
    # Create temporary database
    temp_db = tempfile.mktemp(suffix='.db')
    
    try:
        print(f"Testing complete CSV import with:")
        print(f"  Directory: {temp_dir}")
        print(f"  Database: {temp_db}")
        print("\n" + "="*50)
        
        # Initialize importer
        importer = CSVImporter(temp_db)
        importer.clear_errors()
        
        # Import bundle
        print("Starting bundle import...")
        results = importer.import_csv_bundle(temp_dir, update_existing=False)
        
        print(f"\nBundle Import Results:")
        for file_type, stats in results.items():
            if 'error' in stats:
                print(f"  {file_type}: ERROR - {stats['error']}")
            else:
                print(f"  {file_type}: {stats.get('imported', 0)} imported, {stats.get('updated', 0)} updated, {stats.get('skipped', 0)} skipped, {stats.get('errors', 0)} errors")
        
        # Show detailed errors if any
        detailed_errors = importer.get_detailed_errors(limit=10)
        if detailed_errors:
            print(f"\nFirst 10 detailed errors:")
            for i, error in enumerate(detailed_errors, 1):
                print(f"  {i}. {error}")
        
        # Check database contents
        if os.path.exists(temp_db):
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            
            # Check patients
            cursor.execute("SELECT COUNT(*) FROM patients")
            patient_count = cursor.fetchone()[0]
            print(f"\nDatabase contents:")
            print(f"  Patients: {patient_count}")
            
            # Check visits
            cursor.execute("SELECT COUNT(*) FROM visits")
            visit_count = cursor.fetchone()[0]
            print(f"  Visits: {visit_count}")
            
            # Check immunizations
            cursor.execute("SELECT COUNT(*) FROM immunizations")
            immunization_count = cursor.fetchone()[0]
            print(f"  Immunizations: {immunization_count}")
            
            if patient_count > 0:
                cursor.execute("SELECT id, first_name, last_name, mrn FROM patients")
                patients = cursor.fetchall()
                print(f"\n  Sample patients:")
                for patient in patients:
                    print(f"    ID {patient[0]}: {patient[1]} {patient[2]} (MRN: {patient[3]})")
            
            if visit_count > 0:
                cursor.execute("SELECT id, patient_id, visit_date, weight_kg FROM visits")
                visits = cursor.fetchall()
                print(f"\n  Sample visits:")
                for visit in visits:
                    print(f"    Visit ID {visit[0]}: Patient {visit[1]} on {visit[2]}, weight: {visit[3]}kg")
            
            if immunization_count > 0:
                cursor.execute("SELECT id, patient_id, immunization, administered_date FROM immunizations")
                immunizations = cursor.fetchall()
                print(f"\n  Sample immunizations:")
                for imm in immunizations:
                    print(f"    Imm ID {imm[0]}: Patient {imm[1]} - {imm[2]} on {imm[3]}")
            
            conn.close()
        
    except Exception as e:
        print(f"ERROR during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        if os.path.exists(temp_db):
            os.unlink(temp_db)

if __name__ == "__main__":
    test_complete_csv_import() 