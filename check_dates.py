#!/usr/bin/env python3

import sqlite3
import emr_config

def check_birth_dates():
    """Check if birth dates were imported correctly"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check a few patients' birth dates
    cursor.execute('SELECT id, first_name, last_name, date_of_birth, naissance_date FROM Patients LIMIT 10')
    patients = cursor.fetchall()
    
    print('Sample patient birth dates:')
    print('-' * 80)
    for patient in patients:
        print(f'ID: {patient[0]}, Name: {patient[1]} {patient[2]}, DOB: {patient[3]}, Naissance: {patient[4]}')
    
    # Check for patients with missing birth dates
    cursor.execute('SELECT COUNT(*) FROM Patients WHERE date_of_birth IS NULL OR date_of_birth = ""')
    missing_dob = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM Patients WHERE naissance_date IS NULL OR naissance_date = ""')
    missing_naissance = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM Patients')
    total_patients = cursor.fetchone()[0]
    
    print(f'\nBirth date statistics:')
    print(f'Total patients: {total_patients}')
    print(f'Missing date_of_birth: {missing_dob}')
    print(f'Missing naissance_date: {missing_naissance}')
    
    # Check if both fields are populated (they should be the same)
    cursor.execute('''
        SELECT id, first_name, last_name, date_of_birth, naissance_date 
        FROM Patients 
        WHERE date_of_birth != naissance_date 
        AND date_of_birth IS NOT NULL 
        AND naissance_date IS NOT NULL
        LIMIT 5
    ''')
    mismatched = cursor.fetchall()
    
    if mismatched:
        print(f'\nMismatched dates found:')
        for patient in mismatched:
            print(f'ID: {patient[0]}, Name: {patient[1]} {patient[2]}, DOB: {patient[3]}, Naissance: {patient[4]}')
    else:
        print('\nNo mismatched dates found.')
    
    conn.close()

if __name__ == "__main__":
    check_birth_dates() 