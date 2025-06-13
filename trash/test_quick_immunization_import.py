#!/usr/bin/env python3
"""
Quick Test: Unified Immunization Import

Test the fixed import system with a single patient
"""

import sys
import os
sys.path.append('immunization_logic')

from services.import_service import UnifiedImmunizationImporter
from services.immunization_service import ImmunizationService
from services.models import ImmunizationAdministration
import sqlite3

def test_simple_import():
    """Test simple immunization import"""
    db_path = "/Users/samimelki/Documents/UnifiedEMR/unified_emr.db"
    
    print("🧪 QUICK IMMUNIZATION IMPORT TEST")
    print("=" * 50)
    
    # Test 1: Direct service test
    print("\n1️⃣ Testing ImmunizationService directly...")
    service = ImmunizationService(db_path)
    
    # Create a test immunization
    admin = ImmunizationAdministration(
        patient_id=99999,  # Test patient ID
        immunization="DTaP - IPV", 
        administered_date="2023-01-15",
        brand_name="Test Brand",
        dose_number=1,
        notes="Test import",
        source="test"
    )
    
    try:
        record_id = service.add_immunization(admin)
        print(f"   ✅ Successfully added immunization record ID: {record_id}")
        
        # Clean up
        service.delete_immunization(record_id)
        print(f"   🧹 Cleaned up test record")
        
    except Exception as e:
        print(f"   ❌ Service test failed: {e}")
        return False
    
    # Test 2: Import service test
    print("\n2️⃣ Testing UnifiedImmunizationImporter...")
    importer = UnifiedImmunizationImporter(db_path)
    
    # Test XML data
    test_xml_data = {
        '/fichier/dtcp1': '2023-01-15',
        '/fichier/hep_b1': '2023-02-15',
        'parsed_autres_vaccins': [
            {
                'vaccine_name': 'HAVRIX',
                'vaccine_date': '2023-03-15',
                'raw_entry': 'HAVRIX 15/03/2023'
            }
        ]
    }
    
    try:
        vaccines_imported = importer.import_patient_vaccines(99998, test_xml_data)
        print(f"   ✅ Successfully imported {vaccines_imported} vaccines")
        
        # Clean up - get and delete all test records
        records = service.get_patient_immunizations(99998)
        for record in records:
            service.delete_immunization(record.id)
        print(f"   🧹 Cleaned up {len(records)} test records")
        
    except Exception as e:
        print(f"   ❌ Import test failed: {e}")
        return False
    
    print("\n✅ ALL TESTS PASSED!")
    print("The immunization import system is working correctly.")
    return True

if __name__ == "__main__":
    test_simple_import() 