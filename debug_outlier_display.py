#!/usr/bin/env python3

import sqlite3
import emr_config

def debug_outlier_display():
    """Debug why outlier display shows 'No measurements found'"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Debugging outlier display issues...")
    print("=" * 60)
    
    # Check specific outlier patients from the screenshot
    outlier_mrns = ['10715', '11305', '10903', '10931', '10762']
    
    for mrn in outlier_mrns:
        print(f"\n{'='*50}")
        print(f"DEBUGGING PATIENT MRN {mrn}")
        print(f"{'='*50}")
        
        # Get patient data
        cursor.execute("SELECT id, first_name, last_name, raw_dossier_text FROM Patients WHERE mrn = ?", (mrn,))
        patient = cursor.fetchone()
        
        if not patient:
            print(f"❌ Patient MRN {mrn} NOT FOUND")
            continue
            
        patient_id, first_name, last_name, raw_dossier_text = patient
        print(f"✅ Patient: {first_name} {last_name} (ID: {patient_id})")
        
        # Check raw dossier text
        if raw_dossier_text:
            print(f"✅ Raw dossier text exists ({len(raw_dossier_text)} chars)")
            print(f"First 200 chars: {raw_dossier_text[:200]}...")
        else:
            print(f"❌ NO raw dossier text found")
        
        # Get visits with measurements
        cursor.execute("""
            SELECT id, visit_date, weight_g, weight_kg, height_cm, head_circumference_cm, raw_visit_entry
            FROM Visits 
            WHERE patient_id = ? AND (weight_g IS NOT NULL OR height_cm IS NOT NULL OR head_circumference_cm IS NOT NULL)
            ORDER BY visit_date
        """, (patient_id,))
        visits = cursor.fetchall()
        
        print(f"✅ Found {len(visits)} visits with measurements")
        
        if visits:
            print(f"\nFirst few visits:")
            for i, visit in enumerate(visits[:3]):
                visit_id, visit_date, weight_g, weight_kg, height_cm, hc_cm, raw_entry = visit
                print(f"  Visit {i+1}: {visit_date}")
                print(f"    Weight: {weight_g}g/{weight_kg}kg")
                print(f"    Height: {height_cm}cm")
                print(f"    HC: {hc_cm}cm")
                print(f"    Raw entry: {raw_entry[:100] if raw_entry else 'None'}...")
        
        # Test the extract_visit_with_all_measurements logic
        print(f"\n🔍 TESTING EXTRACT LOGIC:")
        
        if visits and raw_dossier_text:
            # Test with first visit that has weight
            test_visit = None
            for visit in visits:
                if visit[2]:  # weight_g exists
                    test_visit = visit
                    break
            
            if test_visit:
                visit_id, visit_date, weight_g, weight_kg, height_cm, hc_cm, raw_entry = test_visit
                target_value = weight_g / 1000  # Convert to kg
                measurement_type = 'Weight (kg)'
                
                print(f"  Testing with visit {visit_date}, target weight: {target_value}kg")
                
                # Simulate the extract_visit_with_all_measurements function
                import re
                from datetime import datetime
                
                # Convert visit date to short format
                try:
                    visit_date_obj = datetime.fromisoformat(visit_date.split('T')[0])
                    visit_date_short = visit_date_obj.strftime('%d-%m-%y')
                    print(f"  Looking for date pattern: *{visit_date_short}*")
                except:
                    visit_date_short = None
                    print(f"  ❌ Could not parse visit date: {visit_date}")
                
                # Look for this specific date in the raw dossier text
                if visit_date_short:
                    visit_pattern = rf'\*{re.escape(visit_date_short)}\*\s*([^\*]+?)(?=\*\d{{2}}-\d{{2}}-\d{{2}}\*|$)'
                    match = re.search(visit_pattern, raw_dossier_text, re.DOTALL)
                    if match:
                        relevant_visit_text = f"*{visit_date_short}* {match.group(1).strip()}"
                        print(f"  ✅ Found matching text: {relevant_visit_text[:100]}...")
                    else:
                        print(f"  ❌ No matching date pattern found")
                        
                        # Show what date patterns ARE in the raw text
                        all_dates = re.findall(r'\*(\d{2}-\d{2}-\d{2})\*', raw_dossier_text)
                        print(f"  Available dates in raw text: {all_dates[:10]}...")
                
                # Test measurement matching
                print(f"  Looking for weight value {weight_g}g in raw text...")
                if str(weight_g) in raw_dossier_text:
                    print(f"  ✅ Found weight value {weight_g} in raw text")
                else:
                    print(f"  ❌ Weight value {weight_g} not found in raw text")
                    
                    # Look for similar values
                    weight_patterns = re.findall(r'\b(\d{4,5})\b', raw_dossier_text)
                    print(f"  Similar weight-like numbers found: {weight_patterns[:10]}...")
        
        print(f"\n" + "-"*50)

    conn.close()

if __name__ == "__main__":
    debug_outlier_display() 