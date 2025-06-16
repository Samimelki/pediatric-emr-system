#!/usr/bin/env python3

import sqlite3
import emr_config

def check_measurements():
    """Check why measurements aren't showing up despite being imported"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Investigating measurement data issues...")
    print("=" * 60)
    
    # Check visits table structure and data
    print("1. VISITS TABLE ANALYSIS:")
    print("-" * 40)
    
    cursor.execute("PRAGMA table_info(Visits)")
    columns = cursor.fetchall()
    print("Visits table columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Count total visits
    cursor.execute("SELECT COUNT(*) FROM Visits")
    total_visits = cursor.fetchone()[0]
    print(f"\nTotal visits: {total_visits}")
    
    # Check for measurement data in visits
    cursor.execute("SELECT COUNT(*) FROM Visits WHERE weight_g IS NOT NULL")
    weight_g_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Visits WHERE weight_kg IS NOT NULL")
    weight_kg_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Visits WHERE height_cm IS NOT NULL")
    height_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM Visits WHERE head_circumference_cm IS NOT NULL")
    hc_count = cursor.fetchone()[0]
    
    print(f"Visits with weight_g: {weight_g_count}")
    print(f"Visits with weight_kg: {weight_kg_count}")
    print(f"Visits with height_cm: {height_count}")
    print(f"Visits with head_circumference_cm: {hc_count}")
    
    # Sample some visits with measurements
    print(f"\nSample visits with measurements:")
    cursor.execute("""
        SELECT v.id, v.patient_id, v.visit_date, v.weight_g, v.weight_kg, v.height_cm, v.head_circumference_cm,
               p.mrn, p.first_name, p.last_name
        FROM Visits v
        JOIN Patients p ON v.patient_id = p.id
        WHERE v.weight_g IS NOT NULL OR v.height_cm IS NOT NULL OR v.head_circumference_cm IS NOT NULL
        LIMIT 10
    """)
    sample_visits = cursor.fetchall()
    
    for visit in sample_visits:
        visit_id, patient_id, visit_date, weight_g, weight_kg, height_cm, hc_cm, mrn, first_name, last_name = visit
        print(f"  Visit {visit_id}: Patient {mrn} ({first_name} {last_name})")
        print(f"    Date: {visit_date}, Weight: {weight_g}g/{weight_kg}kg, Height: {height_cm}cm, HC: {hc_cm}cm")
    
    # Check specific patients from the outlier screenshot
    outlier_mrns = ['10715', '11305', '10903', '10931', '10762']
    
    print(f"\n2. CHECKING SPECIFIC OUTLIER PATIENTS:")
    print("-" * 40)
    
    for mrn in outlier_mrns:
        cursor.execute("SELECT id, first_name, last_name, date_of_birth FROM Patients WHERE mrn = ?", (mrn,))
        patient = cursor.fetchone()
        
        if patient:
            patient_id, first_name, last_name, dob = patient
            print(f"\nPatient MRN {mrn}: {first_name} {last_name} (ID: {patient_id})")
            print(f"  DOB: {dob}")
            
            # Check their visits
            cursor.execute("""
                SELECT id, visit_date, weight_g, weight_kg, height_cm, head_circumference_cm, notes, raw_visit_entry
                FROM Visits 
                WHERE patient_id = ?
                ORDER BY visit_date
            """, (patient_id,))
            visits = cursor.fetchall()
            
            print(f"  Visits: {len(visits)}")
            for visit in visits[:5]:  # Show first 5 visits
                visit_id, visit_date, weight_g, weight_kg, height_cm, hc_cm, notes, raw_entry = visit
                print(f"    Visit {visit_id} ({visit_date}): W:{weight_g}g/{weight_kg}kg, H:{height_cm}cm, HC:{hc_cm}cm")
                if notes:
                    print(f"      Notes: {notes[:50]}...")
                if raw_entry:
                    print(f"      Raw: {raw_entry[:50]}...")
        else:
            print(f"\nPatient MRN {mrn}: NOT FOUND")
    
    # Check if there's a GrowthMeasurements table
    print(f"\n3. CHECKING GROWTH MEASUREMENTS TABLE:")
    print("-" * 40)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='GrowthMeasurements'")
    growth_table_exists = cursor.fetchone()
    
    if growth_table_exists:
        cursor.execute("SELECT COUNT(*) FROM GrowthMeasurements")
        growth_count = cursor.fetchone()[0]
        print(f"GrowthMeasurements table exists with {growth_count} records")
        
        if growth_count > 0:
            cursor.execute("SELECT * FROM GrowthMeasurements LIMIT 5")
            growth_samples = cursor.fetchall()
            print("Sample growth measurements:")
            for sample in growth_samples:
                print(f"  {sample}")
    else:
        print("GrowthMeasurements table does not exist")
    
    # Check if there are any NULL date_of_birth issues
    print(f"\n4. CHECKING DATE OF BIRTH ISSUES:")
    print("-" * 40)
    
    cursor.execute("SELECT COUNT(*) FROM Patients WHERE date_of_birth IS NULL OR date_of_birth = ''")
    null_dob_count = cursor.fetchone()[0]
    print(f"Patients with NULL/empty date_of_birth: {null_dob_count}")
    
    if null_dob_count > 0:
        cursor.execute("SELECT mrn, first_name, last_name FROM Patients WHERE date_of_birth IS NULL OR date_of_birth = '' LIMIT 5")
        null_dob_patients = cursor.fetchall()
        print("Sample patients with missing DOB:")
        for patient in null_dob_patients:
            print(f"  MRN {patient[0]}: {patient[1]} {patient[2]}")
    
    conn.close()

if __name__ == "__main__":
    check_measurements() 