#!/usr/bin/env python3
"""
Debug Import Issues

Let's debug why records aren't being saved properly
"""

import sys
import os
sys.path.append('immunization_logic')

from services.import_service import UnifiedImmunizationImporter
from services.immunization_service import ImmunizationService
from services.models import ImmunizationAdministration
import sqlite3

def debug_import():
    """Debug the import process step by step"""
    db_path = "/Users/samimelki/Documents/UnifiedEMR/unified_emr.db"
    
    print("🔍 DEBUG IMPORT PROCESS")
    print("=" * 50)
    
    # Test 1: Check database connection
    print("\n1️⃣ Testing database connection...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Immunizations")
        count = cursor.fetchone()[0]
        print(f"   ✅ Database connected. Current records: {count}")
        conn.close()
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        return
    
    # Test 2: Test direct service insertion
    print("\n2️⃣ Testing direct service insertion...")
    service = ImmunizationService(db_path)
    
    admin = ImmunizationAdministration(
        patient_id=99996,
        immunization="Debug Test",
        administered_date="2023-01-15",
        brand_name="Debug Brand",
        dose_number=1,
        notes="Debug test",
        source="debug"
    )
    
    try:
        record_id = service.add_immunization(admin)
        print(f"   ✅ Successfully added record ID: {record_id}")
        
        # Verify it was saved
        records = service.get_patient_immunizations(99996)
        print(f"   ✅ Retrieved {len(records)} records for patient 99996")
        
        # Clean up
        if records:
            service.delete_immunization(records[0].id)
            print(f"   🧹 Cleaned up debug record")
        
    except Exception as e:
        print(f"   ❌ Direct service test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Test importer components
    print("\n3️⃣ Testing importer components...")
    importer = UnifiedImmunizationImporter(db_path)
    
    # Test standard vaccine mapping
    print(f"   📋 Importer has {len(importer.standard_vaccine_columns)} standard vaccine mappings")
    print(f"   📋 Brand mapping has {len(importer.brand_to_disease)} brand mappings")
    
    # Test single standard vaccine
    test_data = {'/fichier/dtcp1': '2023-01-15'}
    try:
        count = importer._import_standard_vaccines(99995, test_data)
        print(f"   ✅ Standard vaccine import returned: {count}")
        
        # Check if it was saved
        records = service.get_patient_immunizations(99995)
        print(f"   ✅ Found {len(records)} records for patient 99995")
        
        if records:
            print(f"      - {records[0].immunization} (dose {records[0].dose_number})")
            service.delete_immunization(records[0].id)
            print(f"   🧹 Cleaned up test record")
        
    except Exception as e:
        print(f"   ❌ Standard vaccine import failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Test non-standard vaccine
    print("\n4️⃣ Testing non-standard vaccine import...")
    nonstandard_data = [
        {
            'vaccine_name': 'HAVRIX',
            'vaccine_date': '2023-03-15',
            'raw_entry': 'HAVRIX 15/03/2023'
        }
    ]
    
    try:
        count = importer._import_nonstandard_vaccines(99994, nonstandard_data)
        print(f"   ✅ Non-standard vaccine import returned: {count}")
        
        # Check if it was saved
        records = service.get_patient_immunizations(99994)
        print(f"   ✅ Found {len(records)} records for patient 99994")
        
        if records:
            print(f"      - {records[0].immunization} (brand: {records[0].brand_name})")
            service.delete_immunization(records[0].id)
            print(f"   🧹 Cleaned up test record")
        
    except Exception as e:
        print(f"   ❌ Non-standard vaccine import failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ DEBUG COMPLETE")

if __name__ == "__main__":
    debug_import() 