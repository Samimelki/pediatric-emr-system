#!/usr/bin/env python3

import sqlite3
import emr_config

def debug_vaccine_issue():
    """Debug why vaccine calculation returns 0 despite having vaccine data"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Debugging vaccine calculation issue...")
    print("=" * 60)
    
    # 1. Check what the vaccine function is looking for
    print("1. VACCINE FUNCTION EXPECTATIONS:")
    print("-" * 40)
    
    standard_vaccine_columns = [
        'rougeole_seule_date',
        'dtcp1_date', 'dtcp2_date', 'dtcp3_date',
        'dtcp_rappel1_date', 'dtcp_rappel2_date', 'dtcp_rappel3_date', 'dtcp_rappel4_date',
        'hep_b1_date', 'hep_b2_date', 'hep_b3_date',
        'hib1_date', 'hib2_date', 'hib3_date', 'hib_rappel_date',
        'ror_date'
    ]
    
    print("Function expects these columns in Patients table:")
    for col in standard_vaccine_columns:
        print(f"  - {col}")
    
    # 2. Check what columns actually exist in Patients table
    print(f"\n2. ACTUAL PATIENTS TABLE STRUCTURE:")
    print("-" * 40)
    
    cursor.execute("PRAGMA table_info(Patients)")
    patient_columns = cursor.fetchall()
    
    existing_vaccine_columns = []
    for col in patient_columns:
        col_name = col[1]
        if any(vaccine_col in col_name.lower() for vaccine_col in ['date', 'dtcp', 'hep', 'hib', 'ror', 'rougeole']):
            existing_vaccine_columns.append(col_name)
    
    print("Vaccine-related columns that exist:")
    for col in existing_vaccine_columns:
        print(f"  ✅ {col}")
    
    print("\nMissing vaccine columns:")
    for col in standard_vaccine_columns:
        if col not in [c[1] for c in patient_columns]:
            print(f"  ❌ {col}")
    
    # 3. Check if any patients have data in the expected columns
    print(f"\n3. CHECKING DATA IN EXPECTED COLUMNS:")
    print("-" * 40)
    
    for col in standard_vaccine_columns:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM Patients WHERE {col} IS NOT NULL AND {col} != ''")
            count = cursor.fetchone()[0]
            print(f"  {col}: {count} patients")
        except sqlite3.OperationalError:
            print(f"  {col}: COLUMN DOES NOT EXIST")
    
    # 4. Check NonStandardVaccines table
    print(f"\n4. CHECKING NON-STANDARD VACCINES TABLE:")
    print("-" * 40)
    
    try:
        cursor.execute("SELECT COUNT(*) FROM NonStandardVaccines")
        non_standard_count = cursor.fetchone()[0]
        print(f"NonStandardVaccines table: {non_standard_count} records")
    except sqlite3.OperationalError:
        print("NonStandardVaccines table: DOES NOT EXIST")
    
    # 5. Show what we actually have in Immunizations
    print(f"\n5. ACTUAL IMMUNIZATIONS DATA:")
    print("-" * 40)
    
    cursor.execute("SELECT COUNT(*) FROM Immunizations")
    total_immunizations = cursor.fetchone()[0]
    print(f"Total immunizations: {total_immunizations}")
    
    cursor.execute("SELECT COUNT(DISTINCT patient_id) FROM Immunizations")
    patients_with_vaccines = cursor.fetchone()[0]
    print(f"Patients with vaccines: {patients_with_vaccines}")
    
    # Sample immunizations
    cursor.execute("SELECT patient_id, immunization, administered_date FROM Immunizations LIMIT 10")
    sample_immunizations = cursor.fetchall()
    print(f"\nSample immunizations:")
    for imm in sample_immunizations:
        print(f"  Patient {imm[0]}: {imm[1]} on {imm[2]}")
    
    # 6. Calculate what the average SHOULD be
    print(f"\n6. CORRECT CALCULATION:")
    print("-" * 40)
    
    if total_immunizations > 0 and patients_with_vaccines > 0:
        correct_average = total_immunizations / patients_with_vaccines
        print(f"Correct average vaccines per child: {correct_average:.2f}")
    
    conn.close()

if __name__ == "__main__":
    debug_vaccine_issue() 