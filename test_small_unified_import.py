#!/usr/bin/env python3
"""
Small Test: Unified Immunization Import

Test with a single patient to confirm the unified import works correctly
"""

import sys
import os
sys.path.append('immunization_logic')
sys.path.append('.')

from services.import_service import UnifiedImmunizationImporter
from services.immunization_service import ImmunizationService
import sqlite3

def test_single_patient():
    """Test unified import with a single patient"""
    db_path = "/Users/samimelki/Documents/UnifiedEMR/unified_emr.db"
    
    print("🧪 SMALL UNIFIED IMPORT TEST")
    print("=" * 50)
    
    # Create test patient data - simulating what populate_db.py would provide
    test_patient_data = {
        # Standard vaccines from XML columns
        '/fichier/dtcp1': '2023-01-15',
        '/fichier/dtcp2': '2023-02-15', 
        '/fichier/hep_b1': '2023-01-20',
        '/fichier/hep_b2': '2023-02-20',
        '/fichier/ror': '2023-06-15',
        
        # Non-standard vaccines from parsed autres_vac
        'parsed_autres_vaccins': [
            {
                'vaccine_name': 'HAVRIX',
                'vaccine_date': '2023-03-15',
                'raw_entry': 'HAVRIX 15/03/2023'
            },
            {
                'vaccine_name': 'SYNFLORIX',
                'vaccine_date': '2023-04-15',
                'raw_entry': 'SYNFLORIX 15/04/2023'
            },
            {
                'vaccine_name': 'VAXIGRIP',
                'vaccine_date': '2023-10-15',
                'raw_entry': 'VAXIGRIP 15/10/2023'
            }
        ]
    }
    
    test_patient_id = 99997
    
    print(f"📋 Testing with patient ID: {test_patient_id}")
    print(f"📅 Standard vaccines: {len([k for k in test_patient_data.keys() if k.startswith('/fichier')])}")
    print(f"💉 Non-standard vaccines: {len(test_patient_data.get('parsed_autres_vaccins', []))}")
    
    # Initialize services
    importer = UnifiedImmunizationImporter(db_path)
    service = ImmunizationService(db_path)
    
    # Clear any existing test data
    existing_records = service.get_patient_immunizations(test_patient_id)
    for record in existing_records:
        service.delete_immunization(record.id)
    print(f"🧹 Cleared {len(existing_records)} existing test records")
    
    # Run the import
    try:
        vaccines_imported = importer.import_patient_vaccines(test_patient_id, test_patient_data)
        print(f"✅ Successfully imported {vaccines_imported} vaccines")
        
        # Get import statistics
        stats = importer.get_import_stats()
        print(f"   📊 Standard vaccines: {stats['standard_vaccines_imported']}")
        print(f"   📊 Non-standard vaccines: {stats['nonstandard_vaccines_imported']}")
        
        if stats['unmapped_brands']:
            print(f"   ⚠️  Unmapped brands: {stats['unmapped_brands']}")
        
        if stats['errors']:
            print(f"   ❌ Errors: {stats['errors']}")
        
        # Verify import by reading back
        final_records = service.get_patient_immunizations(test_patient_id)
        print(f"✅ Verified {len(final_records)} records in database")
        
        # Show sample records
        print("\n📋 Sample imported records:")
        for i, record in enumerate(final_records[:5]):  # Show first 5
            print(f"   {i+1}. {record.immunization} - Dose {record.dose_number or 'N/A'} - {record.administered_date}")
            if record.brand_name:
                print(f"      Brand: {record.brand_name}")
            print(f"      Source: {record.source}")
        
        if len(final_records) > 5:
            print(f"   ... and {len(final_records) - 5} more")
        
        # Clean up
        for record in final_records:
            service.delete_immunization(record.id)
        print(f"\n🧹 Cleaned up {len(final_records)} test records")
        
        print("\n✅ SMALL IMPORT TEST PASSED!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_single_patient() 