#!/usr/bin/env python3

import csv
import sqlite3
import emr_config

def investigate_missing_patients():
    """Investigate why specific patients with valid data didn't import"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    csv_directory = '../Documents/emr_csv_export_20250616_123235'
    patients_csv = f"{csv_directory}/patients.csv"
    
    # List of missing patient IDs from the previous check
    missing_patient_ids = [4635, 10242, 10521, 10676, 10691, 10708, 10726, 10772, 11005, 11196, 11204]
    
    print("Investigating missing patients with valid data...")
    print("=" * 60)
    
    with open(patients_csv, 'r', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row_num, row in enumerate(reader, start=2):
            patient_id = int(row.get('id', 0))
            
            if patient_id in missing_patient_ids:
                print(f"\nRow {row_num}, Patient ID {patient_id}:")
                print(f"  MRN: '{row.get('mrn', '')}'")
                print(f"  Prenom: '{row.get('prenom', '')}'")
                print(f"  Nom: '{row.get('nom', '')}'")
                print(f"  Naissance Date: '{row.get('naissance_date', '')}'")
                print(f"  Sexe: '{row.get('sexe', '')}'")
                
                # Check if patient exists by different criteria
                mrn = row.get('mrn', '').strip()
                prenom = row.get('prenom', '').strip()
                nom = row.get('nom', '').strip()
                naissance_date = row.get('naissance_date', '').strip()
                
                # Check by MRN
                if mrn:
                    cursor.execute("SELECT id, first_name, last_name FROM Patients WHERE mrn = ?", (mrn,))
                    result = cursor.fetchone()
                    if result:
                        print(f"  ✓ Found by MRN: DB ID {result[0]}, Name: {result[1]} {result[2]}")
                    else:
                        print(f"  ✗ Not found by MRN: {mrn}")
                
                # Check by name and DOB
                cursor.execute("SELECT id, mrn FROM Patients WHERE first_name = ? AND last_name = ? AND date_of_birth = ?", 
                             (prenom, nom, naissance_date))
                result = cursor.fetchone()
                if result:
                    print(f"  ✓ Found by name+DOB: DB ID {result[0]}, MRN: {result[1]}")
                else:
                    print(f"  ✗ Not found by name+DOB")
                
                # Check if there's a similar patient
                cursor.execute("SELECT id, mrn, first_name, last_name FROM Patients WHERE first_name LIKE ? AND last_name LIKE ?", 
                             (f"%{prenom}%", f"%{nom}%"))
                similar = cursor.fetchall()
                if similar:
                    print(f"  Similar patients found:")
                    for sim in similar[:3]:  # Show first 3
                        print(f"    DB ID {sim[0]}, MRN: {sim[1]}, Name: {sim[2]} {sim[3]}")
                else:
                    print(f"  No similar patients found")
    
    # Check the highest patient ID in the database
    cursor.execute("SELECT MAX(id) FROM Patients")
    max_db_id = cursor.fetchone()[0]
    print(f"\nHighest patient ID in database: {max_db_id}")
    
    # Check if the missing patients are beyond the imported range
    print(f"Missing patient IDs: {missing_patient_ids}")
    print(f"IDs beyond DB range: {[pid for pid in missing_patient_ids if pid > max_db_id]}")
    
    conn.close()

if __name__ == "__main__":
    investigate_missing_patients() 