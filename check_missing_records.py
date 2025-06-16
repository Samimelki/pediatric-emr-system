#!/usr/bin/env python3

import csv
import sqlite3
import emr_config

def check_missing_records():
    """Check which records from the CSV didn't get imported and why"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    csv_directory = '../Documents/emr_csv_export_20250616_123235'
    
    print("Checking missing records from CSV import...")
    print("=" * 60)
    
    # Check patients
    print("\n1. PATIENTS - Checking missing records:")
    print("-" * 40)
    
    patients_csv = f"{csv_directory}/patients.csv"
    with open(patients_csv, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        csv_patient_count = 0
        missing_patients = []
        
        for row_num, row in enumerate(reader, start=2):
            csv_patient_count += 1
            patient_id = row.get('id')
            mrn = row.get('mrn', '').strip()
            prenom = row.get('prenom', '').strip()
            nom = row.get('nom', '').strip()
            naissance_date = row.get('naissance_date', '').strip()
            
            # Check if this patient exists in database
            if mrn:
                cursor.execute("SELECT id FROM Patients WHERE mrn = ?", (mrn,))
            else:
                cursor.execute("SELECT id FROM Patients WHERE first_name = ? AND last_name = ? AND date_of_birth = ?", 
                             (prenom, nom, naissance_date))
            
            if not cursor.fetchone():
                missing_patients.append({
                    'row': row_num,
                    'id': patient_id,
                    'mrn': mrn,
                    'prenom': prenom,
                    'nom': nom,
                    'naissance_date': naissance_date,
                    'reason': 'Missing both first_name and last_name' if not prenom and not nom else 'Unknown'
                })
    
    cursor.execute("SELECT COUNT(*) FROM Patients")
    db_patient_count = cursor.fetchone()[0]
    
    print(f"CSV patients: {csv_patient_count}")
    print(f"DB patients: {db_patient_count}")
    print(f"Missing patients: {len(missing_patients)}")
    
    if missing_patients:
        print("\nMissing patient details:")
        for patient in missing_patients:
            print(f"  Row {patient['row']}: ID={patient['id']}, MRN={patient['mrn']}, Name='{patient['prenom']} {patient['nom']}', DOB={patient['naissance_date']}")
            print(f"    Reason: {patient['reason']}")
    
    # Check visits
    print("\n2. VISITS - Checking missing records:")
    print("-" * 40)
    
    visits_csv = f"{csv_directory}/visits.csv"
    with open(visits_csv, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        csv_visit_count = 0
        missing_visits = []
        
        for row_num, row in enumerate(reader, start=2):
            csv_visit_count += 1
            visit_id = row.get('id')
            patient_id = row.get('patient_id')
            patient_mrn = row.get('patient_mrn')
            visit_date = row.get('visit_date')
            
            # Check if this visit exists in database
            cursor.execute("SELECT id FROM Visits WHERE id = ?", (visit_id,))
            if not cursor.fetchone():
                # Check if the patient exists
                cursor.execute("SELECT id FROM Patients WHERE id = ?", (patient_id,))
                patient_exists = cursor.fetchone()
                
                missing_visits.append({
                    'row': row_num,
                    'id': visit_id,
                    'patient_id': patient_id,
                    'patient_mrn': patient_mrn,
                    'visit_date': visit_date,
                    'reason': 'Patient not found' if not patient_exists else 'Unknown'
                })
    
    cursor.execute("SELECT COUNT(*) FROM Visits")
    db_visit_count = cursor.fetchone()[0]
    
    print(f"CSV visits: {csv_visit_count}")
    print(f"DB visits: {db_visit_count}")
    print(f"Missing visits: {len(missing_visits)}")
    
    if missing_visits:
        print("\nMissing visit details (first 10):")
        for visit in missing_visits[:10]:
            print(f"  Row {visit['row']}: Visit ID={visit['id']}, Patient ID={visit['patient_id']}, MRN={visit['patient_mrn']}, Date={visit['visit_date']}")
            print(f"    Reason: {visit['reason']}")
        if len(missing_visits) > 10:
            print(f"  ... and {len(missing_visits) - 10} more missing visits")
    
    # Check immunizations
    print("\n3. IMMUNIZATIONS - Checking missing records:")
    print("-" * 40)
    
    immunizations_csv = f"{csv_directory}/immunizations.csv"
    with open(immunizations_csv, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        csv_immunization_count = 0
        skipped_immunizations = 0
        missing_immunizations = []
        
        for row_num, row in enumerate(reader, start=2):
            csv_immunization_count += 1
            immunization_id = row.get('id')
            patient_id = row.get('patient_id')
            patient_mrn = row.get('patient_mrn')
            immunization = row.get('immunization')
            administered_date = row.get('administered_date', '').strip()
            
            # Check if this was skipped due to "None" date
            if administered_date.lower() == 'none' or not administered_date:
                skipped_immunizations += 1
                continue
            
            # Check if this immunization exists in database
            cursor.execute("SELECT id FROM Immunizations WHERE id = ?", (immunization_id,))
            if not cursor.fetchone():
                # Check if the patient exists
                cursor.execute("SELECT id FROM Patients WHERE id = ?", (patient_id,))
                patient_exists = cursor.fetchone()
                
                missing_immunizations.append({
                    'row': row_num,
                    'id': immunization_id,
                    'patient_id': patient_id,
                    'patient_mrn': patient_mrn,
                    'immunization': immunization,
                    'administered_date': administered_date,
                    'reason': 'Patient not found' if not patient_exists else 'Unknown'
                })
    
    cursor.execute("SELECT COUNT(*) FROM Immunizations")
    db_immunization_count = cursor.fetchone()[0]
    
    print(f"CSV immunizations: {csv_immunization_count}")
    print(f"Skipped (None dates): {skipped_immunizations}")
    print(f"DB immunizations: {db_immunization_count}")
    print(f"Missing immunizations: {len(missing_immunizations)}")
    
    if missing_immunizations:
        print("\nMissing immunization details (first 10):")
        for immunization in missing_immunizations[:10]:
            print(f"  Row {immunization['row']}: ID={immunization['id']}, Patient ID={immunization['patient_id']}, MRN={immunization['patient_mrn']}")
            print(f"    Vaccine: {immunization['immunization']}, Date: {immunization['administered_date']}")
            print(f"    Reason: {immunization['reason']}")
        if len(missing_immunizations) > 10:
            print(f"  ... and {len(missing_immunizations) - 10} more missing immunizations")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"Missing patients: {len(missing_patients)}")
    print(f"Missing visits: {len(missing_visits)}")
    print(f"Missing immunizations: {len(missing_immunizations)}")
    print(f"Skipped immunizations (None dates): {skipped_immunizations}")
    
    conn.close()

if __name__ == "__main__":
    check_missing_records() 