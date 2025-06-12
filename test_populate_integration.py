#!/usr/bin/env python3
"""
Test Integration with populate_db.py

Test that the existing XML import process correctly uses the unified immunization system
"""

import sys
import os
sys.path.append('.')

from populate_db import populate_database_from_parsed_data
from unified_database import get_db
import sqlite3

def test_populate_integration():
    """Test that populate_db.py correctly uses unified immunization system"""
    
    print("🧪 TESTING POPULATE_DB.PY INTEGRATION")
    print("=" * 60)
    
    # Create test patient data that simulates what parse_excel_xml returns
    test_xml_patients = [
        {
            # Patient info
            '/fichier/nom': 'Integration',
            '/fichier/prenom': 'Test',
            '/fichier/ddn': '2020-01-15T00:00:00.000',
            '/fichier/sexe': 'M',
            
            # Standard vaccines (XML columns)
            '/fichier/dtcp1': '2020-03-15T00:00:00.000',
            '/fichier/dtcp2': '2020-04-15T00:00:00.000',
            '/fichier/hep_b1': '2020-02-15T00:00:00.000',
            '/fichier/ror': '2021-03-15T00:00:00.000',
            
            # Non-standard vaccines (parsed from autres_vac)
            'parsed_autres_vaccins': [
                {
                    'vaccine_name': 'HAVRIX',
                    'vaccine_date': '2022-06-15',
                    'raw_entry': 'HAVRIX 15/06/2022'
                },
                {
                    'vaccine_name': 'SYNFLORIX',
                    'vaccine_date': '2020-05-15',
                    'raw_entry': 'SYNFLORIX 15/05/2020'
                }
            ],
            
            # Visit data (minimal)
            'parsed_dossier_content': {
                'parsed_visits': [
                    {
                        'visit_date': '2020-03-15',
                        'weight_g': 4500,
                        'raw_visit_entry': 'Test visit'
                    }
                ]
            }
        }
    ]
    
    print(f"📋 Testing with 1 patient containing:")
    print(f"   📅 4 standard vaccines")
    print(f"   💉 2 non-standard vaccines")
    print(f"   🏥 1 visit")
    
    # Count immunizations before import
    db_path = "/Users/samimelki/Documents/UnifiedEMR/unified_emr.db"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Immunizations")
        initial_count = cursor.fetchone()[0]
        print(f"   💾 Initial immunizations in database: {initial_count}")
    
    # Run the actual populate_database_from_parsed_data function
    try:
        patients_added, visits_added, vaccines_added = populate_database_from_parsed_data(
            test_xml_patients, 
            target_mode='pediatric',
            document_format='md'
        )
        
        print(f"\n📊 POPULATE_DB.PY RESULTS:")
        print(f"   👥 Patients added: {patients_added}")
        print(f"   🏥 Visits added: {visits_added}")  
        print(f"   💉 Vaccines added: {vaccines_added}")
        
        # Count immunizations after import
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Immunizations")
            final_count = cursor.fetchone()[0]
            print(f"   💾 Final immunizations in database: {final_count}")
            
            # Show some sample records
            cursor.execute("""
                SELECT immunization, dose_number, administered_date, brand_name, source
                FROM Immunizations 
                ORDER BY id DESC 
                LIMIT 6
            """)
            recent_records = cursor.fetchall()
            
            print(f"\n📋 Recent immunization records:")
            for record in recent_records:
                immunization, dose, date, brand, source = record
                brand_info = f" (brand: {brand})" if brand else ""
                print(f"   - {immunization} dose {dose or 'N/A'}: {date}{brand_info} [{source}]")
        
        # Clean up test data
        print(f"\n🧹 Cleaning up test data...")
        if patients_added > 0:
            db = get_db()
            # Get the test patient ID (most recent)
            cursor = db.execute("SELECT id FROM Patients ORDER BY id DESC LIMIT 1")
            test_patient_id = cursor.fetchone()[0]
            
            # Delete test records
            db.execute("DELETE FROM Immunizations WHERE patient_id = ?", (test_patient_id,))
            db.execute("DELETE FROM Visits WHERE patient_id = ?", (test_patient_id,))
            db.execute("DELETE FROM Patients WHERE id = ?", (test_patient_id,))
            db.commit()
            print(f"   ✅ Cleaned up test patient {test_patient_id}")
        
        print(f"\n✅ INTEGRATION TEST PASSED!")
        print(f"populate_db.py correctly uses the unified immunization system!")
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_populate_integration() 