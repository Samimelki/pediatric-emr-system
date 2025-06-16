#!/usr/bin/env python3

import sqlite3
import emr_config

def debug_matching_issue():
    """Debug why visit matching isn't working in extract_visit_with_all_measurements"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Debugging visit matching issue...")
    print("=" * 60)
    
    # Test with MRN 10715 which shows the issue
    mrn = '10715'
    
    # Get patient info
    cursor.execute("SELECT id, first_name, last_name FROM Patients WHERE mrn = ?", (mrn,))
    patient = cursor.fetchone()
    
    if not patient:
        print(f"Patient MRN {mrn} not found")
        return
    
    patient_id, first_name, last_name = patient
    print(f"Testing patient: {first_name} {last_name} (MRN {mrn}, ID {patient_id})")
    
    # Get all visits for this patient
    cursor.execute("""
        SELECT id, visit_date, weight_g, height_cm, head_circumference_cm, raw_visit_entry
        FROM Visits 
        WHERE patient_id = ?
        ORDER BY visit_date
    """, (patient_id,))
    visits = cursor.fetchall()
    
    print(f"\nFound {len(visits)} visits:")
    for i, visit in enumerate(visits):
        visit_id, visit_date, weight_g, height_cm, hc_cm, raw_entry = visit
        weight_kg = weight_g / 1000 if weight_g else None
        print(f"  {i+1}. Visit {visit_id} ({visit_date})")
        print(f"      Weight: {weight_g}g ({weight_kg}kg), Height: {height_cm}cm, HC: {hc_cm}cm")
        print(f"      Raw: {raw_entry}")
    
    # Test the outlier value we're looking for (87.0 kg from the screenshot)
    target_value = 87.0
    measurement_type = 'Weight (kg)'
    
    print(f"\n🔍 TESTING MATCHING LOGIC:")
    print(f"Looking for {measurement_type} = {target_value}")
    print("-" * 40)
    
    # Simulate the matching logic from extract_visit_with_all_measurements
    target_visit = None
    for visit in visits:
        visit_id, visit_date, weight_g, height_cm, hc_cm, raw_entry = visit
        
        if measurement_type == 'Weight (kg)' and weight_g:
            weight_kg = weight_g / 1000
            difference = abs(weight_kg - target_value)
            print(f"  Visit {visit_date}: {weight_g}g = {weight_kg}kg, diff = {difference}")
            
            if difference < 0.01:  # The current matching threshold
                target_visit = visit
                print(f"    ✅ MATCH FOUND!")
                break
            else:
                print(f"    ❌ No match (diff {difference} >= 0.01)")
    
    if not target_visit:
        print(f"\n❌ NO MATCHING VISIT FOUND!")
        print(f"The issue is likely that the outlier value {target_value} doesn't exactly match any visit weight")
        
        # Show the closest matches
        print(f"\nClosest weight matches:")
        weight_diffs = []
        for visit in visits:
            visit_id, visit_date, weight_g, height_cm, hc_cm, raw_entry = visit
            if weight_g:
                weight_kg = weight_g / 1000
                diff = abs(weight_kg - target_value)
                weight_diffs.append((diff, weight_kg, visit_date, raw_entry))
        
        weight_diffs.sort()
        for diff, weight_kg, visit_date, raw_entry in weight_diffs[:5]:
            print(f"  {weight_kg}kg ({visit_date}): diff = {diff:.3f} - {raw_entry}")
    else:
        print(f"\n✅ FOUND MATCHING VISIT:")
        visit_id, visit_date, weight_g, height_cm, hc_cm, raw_entry = target_visit
        print(f"  Visit: {visit_date}")
        print(f"  Weight: {weight_g}g ({weight_g/1000}kg)")
        print(f"  Raw entry: {raw_entry}")
    
    conn.close()

if __name__ == "__main__":
    debug_matching_issue() 