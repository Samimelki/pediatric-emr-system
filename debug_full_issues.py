#!/usr/bin/env python3

import sqlite3
import emr_config

def debug_full_issues():
    """Debug both measurement display and vaccine calculation issues"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Debugging measurement display and vaccine calculation issues...")
    print("=" * 70)
    
    # 1. Check vaccine data
    print("1. VACCINE DATA ANALYSIS:")
    print("-" * 40)
    
    cursor.execute("SELECT COUNT(*) FROM Immunizations")
    total_immunizations = cursor.fetchone()[0]
    print(f"Total immunizations: {total_immunizations}")
    
    cursor.execute("SELECT COUNT(DISTINCT patient_id) FROM Immunizations")
    patients_with_vaccines = cursor.fetchone()[0]
    print(f"Patients with vaccines: {patients_with_vaccines}")
    
    if total_immunizations > 0 and patients_with_vaccines > 0:
        avg_vaccines = total_immunizations / patients_with_vaccines
        print(f"Average vaccines per child: {avg_vaccines:.2f}")
    else:
        print("❌ No vaccine data found!")
    
    # Sample vaccine data
    cursor.execute("SELECT * FROM Immunizations LIMIT 5")
    sample_vaccines = cursor.fetchall()
    print(f"\nSample vaccines:")
    for vaccine in sample_vaccines:
        print(f"  {vaccine}")
    
    # 2. Check outlier calculation
    print(f"\n2. OUTLIER CALCULATION TEST:")
    print("-" * 40)
    
    # Test the outlier detection function directly
    try:
        from statistics_engine.statistics_calculator import find_measurement_outliers
        outliers = find_measurement_outliers(db_path=db_path, std_dev_threshold=4.0, age_limit_months=60)
        print(f"✅ Outlier detection works: Found {len(outliers)} outliers")
        
        if outliers:
            print("Sample outliers:")
            for i, outlier in enumerate(outliers[:3]):
                print(f"  {i+1}. MRN {outlier['patient_mrn']}: {outlier['measurement_type']} = {outlier['value']} ({outlier['num_std_devs']}σ)")
    except Exception as e:
        print(f"❌ Outlier detection failed: {e}")
    
    # 3. Test the extract function with a specific case
    print(f"\n3. EXTRACT FUNCTION TEST:")
    print("-" * 40)
    
    # Get a specific outlier patient
    cursor.execute("SELECT id, mrn, first_name, last_name FROM Patients WHERE mrn = '10715'")
    patient = cursor.fetchone()
    
    if patient:
        patient_id, mrn, first_name, last_name = patient
        print(f"Testing with patient: {first_name} {last_name} (MRN {mrn}, ID {patient_id})")
        
        # Get a visit with measurements
        cursor.execute("""
            SELECT visit_date, weight_g, height_cm, head_circumference_cm, raw_visit_entry
            FROM Visits 
            WHERE patient_id = ? AND weight_g IS NOT NULL
            LIMIT 1
        """, (patient_id,))
        visit = cursor.fetchone()
        
        if visit:
            visit_date, weight_g, height_cm, hc_cm, raw_entry = visit
            target_weight_kg = weight_g / 1000
            print(f"Test visit: {visit_date}, Weight: {weight_g}g ({target_weight_kg}kg)")
            print(f"Raw entry: {raw_entry}")
            
            # Test the extract function manually
            stored_measurements = {
                'weight_kg': weight_g / 1000 if weight_g else None,
                'height_cm': height_cm,
                'head_circumference_cm': hc_cm,
                'raw_measurement_string': raw_entry if raw_entry else 'N/A'
            }
            
            print(f"Expected measurements: {stored_measurements}")
            
            # Check if the issue is in the template logic
            if stored_measurements['weight_kg']:
                print("✅ Weight data exists")
            else:
                print("❌ No weight data")
                
            if raw_entry:
                print("✅ Raw visit entry exists")
            else:
                print("❌ No raw visit entry")
    
    # 4. Check statistics cache/calculation
    print(f"\n4. STATISTICS CALCULATION TEST:")
    print("-" * 40)
    
    try:
        from statistics_engine.statistics_calculator import calculate_average_vaccines_per_child
        avg_vaccines = calculate_average_vaccines_per_child(db_path=db_path)
        print(f"✅ Vaccine calculation works: {avg_vaccines:.2f} vaccines per child")
    except Exception as e:
        print(f"❌ Vaccine calculation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Check if the issue is in the web route
    print(f"\n5. WEB ROUTE SIMULATION:")
    print("-" * 40)
    
    try:
        # Simulate what the statistics_outliers route does
        from routes.statistics_routes import get_statistics_data
        stats = get_statistics_data()
        
        print(f"Statistics success: {stats['success']}")
        print(f"Average vaccines: {stats.get('avg_vaccines', 'N/A')}")
        print(f"Outliers found: {len(stats.get('outliers', []))}")
        print(f"Percentiles calculated: {bool(stats.get('percentiles'))}")
        
        if stats.get('outliers'):
            # Test the enhancement logic
            outlier = stats['outliers'][0]
            print(f"\nTesting enhancement for outlier: MRN {outlier['patient_mrn']}")
            
            # Check if patient has raw_dossier_text
            cursor.execute("SELECT raw_dossier_text FROM Patients WHERE id = ?", (outlier['patient_id'],))
            patient_data = cursor.fetchone()
            
            if patient_data and patient_data[0]:
                print("✅ Patient has raw_dossier_text")
            else:
                print("❌ Patient has NO raw_dossier_text - this is the issue!")
                
                # Check if they have raw_visit_entry in visits
                cursor.execute("""
                    SELECT COUNT(*) FROM Visits 
                    WHERE patient_id = ? AND raw_visit_entry IS NOT NULL
                """, (outlier['patient_id'],))
                raw_visit_count = cursor.fetchone()[0]
                print(f"   But patient has {raw_visit_count} visits with raw_visit_entry")
        
    except Exception as e:
        print(f"❌ Web route simulation failed: {e}")
        import traceback
        traceback.print_exc()
    
    conn.close()

if __name__ == "__main__":
    debug_full_issues() 