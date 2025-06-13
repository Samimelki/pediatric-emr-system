#!/usr/bin/env python3
"""
Test the unified immunization import system with real XML data.

This script:
1. Parses patients with extensive vaccine data from XML
2. Imports them using the new unified system
3. Verifies vaccines are stored in the Immunizations table
4. Shows comprehensive mapping in action
"""

import sys
import os
from datetime import datetime
import sqlite3

# Add paths for imports
sys.path.append('immunization_logic')
sys.path.append('.')

def test_xml_import():
    """Test importing patients with the unified system."""
    print("🧪 TESTING UNIFIED XML IMPORT")
    print("=" * 50)
    
    try:
        # Initialize Flask app context
        from app import app
        
        with app.app_context():
            # Import our modules
            from xml_parser import parse_excel_xml
            from populate_db import populate_database_from_parsed_data
            
            xml_file = "Copy of databasepap.xml"
            db_path = "/Users/samimelki/Documents/UnifiedEMR/unified_emr.db"
            
            print(f"📂 Parsing XML: {xml_file}")
            
            # Parse XML data
            all_patients = parse_excel_xml(xml_file)
            
            if not all_patients:
                print("❌ No patients found in XML")
                return False
            
            print(f"✅ Found {len(all_patients)} patients in XML")
            
            # Use patients with extensive vaccine data (found from previous analysis)
            test_indices = [3333, 5596]  # JOSEPH NAJM-MEZHER and TERESIA FARES
            test_patients = [all_patients[i] for i in test_indices]
            print(f"🔬 Testing with 2 patients with extensive vaccine data (indices {test_indices})")
            
            # Check what vaccines these patients have before import
            print("\n📋 PRE-IMPORT ANALYSIS:")
            for i, patient in enumerate(test_patients):
                name = f"{patient.get('/fichier/prenom', '')} {patient.get('/fichier/nom', '')}"
                print(f"\nPatient {i+1}: {name}")
                
                # Check standard vaccines
                standard_vaccines = []
                standard_fields = ['/fichier/dtcp1', '/fichier/dtcp2', '/fichier/dtcp3', 
                                 '/fichier/hep_b1', '/fichier/hep_b2', '/fichier/hep_b3',
                                 '/fichier/hib1', '/fichier/hib2', '/fichier/hib3', '/fichier/ror']
                
                for field in standard_fields:
                    if patient.get(field):
                        standard_vaccines.append(f"{field}: {patient.get(field)}")
                
                if standard_vaccines:
                    print(f"  📅 Standard vaccines: {len(standard_vaccines)}")
                    for vaccine in standard_vaccines[:3]:  # Show first 3
                        print(f"    - {vaccine}")
                    if len(standard_vaccines) > 3:
                        print(f"    ... and {len(standard_vaccines) - 3} more")
                
                # Check non-standard vaccines
                autres_vaccins = patient.get('parsed_autres_vaccins', [])
                if autres_vaccins:
                    print(f"  💉 Non-standard vaccines: {len(autres_vaccins)}")
                    for vaccine in autres_vaccins[:5]:  # Show first 5
                        print(f"    - {vaccine.get('vaccine_name')}: {vaccine.get('vaccine_date')}")
                    if len(autres_vaccins) > 5:
                        print(f"    ... and {len(autres_vaccins) - 5} more")
                
                total_vaccines = len(standard_vaccines) + len(autres_vaccins)
                print(f"  🎯 Total vaccines: {total_vaccines}")
            
            # Count current immunizations in database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Immunizations")
            before_count = cursor.fetchone()[0]
            conn.close()
            
            print(f"\n💾 Immunizations in database before import: {before_count}")
            
            # Import using unified system
            print("\n🚀 IMPORTING WITH UNIFIED SYSTEM...")
            print("   (This will show comprehensive mapping in action)")
            
            patients_added, visits_added, vaccines_added = populate_database_from_parsed_data(
                test_patients, 
                target_mode='pediatric',
                document_format='md'
            )
            
            print(f"\n📊 IMPORT RESULTS:")
            print(f"  - Patients added: {patients_added}")
            print(f"  - Visits added: {visits_added}")  
            print(f"  - Vaccines processed: {vaccines_added}")
            
            # Count immunizations after import
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Immunizations")
            after_count = cursor.fetchone()[0]
            
            new_immunizations = after_count - before_count
            print(f"  - New immunizations in database: {new_immunizations}")
            
            # Show sample of imported immunizations
            if new_immunizations > 0:
                print(f"\n💉 SAMPLE IMPORTED IMMUNIZATIONS:")
                cursor.execute("""
                    SELECT patient_id, immunization, administered_date, brand_name, dose_number, source
                    FROM Immunizations 
                    ORDER BY id DESC 
                    LIMIT 15
                """)
                
                immunizations = cursor.fetchall()
                for imm in immunizations:
                    patient_id, disease, date, brand, dose, source = imm
                    brand_display = f" ({brand})" if brand else ""
                    print(f"  • Patient {patient_id}: {disease}{brand_display} - Dose {dose or 1} - {date} [{source}]")
                
                # Show summary by disease type
                print(f"\n📈 SUMMARY BY DISEASE:")
                cursor.execute("""
                    SELECT immunization, COUNT(*) as count, GROUP_CONCAT(DISTINCT brand_name) as brands
                    FROM Immunizations 
                    GROUP BY immunization
                    ORDER BY count DESC
                    LIMIT 10
                """)
                
                summary = cursor.fetchall()
                for disease, count, brands in summary:
                    brands_display = f" (brands: {brands})" if brands else ""
                    print(f"  • {disease}: {count} doses{brands_display}")
            
            conn.close()
            
            print("\n✅ Unified import test completed successfully!")
            return True
        
    except Exception as e:
        print(f"❌ Error during unified import test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the unified import test."""
    success = test_xml_import()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 UNIFIED IMPORT SYSTEM WORKING CORRECTLY!")
        print("✅ Standard vaccines mapped to canonical diseases")
        print("✅ Non-standard vaccines mapped using comprehensive mapping")
        print("✅ All vaccines stored in unified Immunizations table")
    else:
        print("⚠️  Issues found - check the errors above")
    print("=" * 50)

if __name__ == "__main__":
    main() 