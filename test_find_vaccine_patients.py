#!/usr/bin/env python3
"""
Find patients with vaccine data in the XML file for testing the unified import system.
"""

import sys
sys.path.append('.')

from xml_parser import parse_excel_xml

def find_vaccine_patients():
    """Find patients with vaccine data."""
    print("🔍 FINDING PATIENTS WITH VACCINE DATA")
    print("=" * 50)
    
    xml_file = "Copy of databasepap.xml"
    print(f"📂 Parsing XML: {xml_file}")
    
    all_patients = parse_excel_xml(xml_file)
    print(f"✅ Found {len(all_patients)} total patients")
    
    patients_with_vaccines = []
    
    # Standard vaccine fields to check
    standard_fields = ['/fichier/dtcp1', '/fichier/dtcp2', '/fichier/dtcp3', 
                      '/fichier/hep_b1', '/fichier/hep_b2', '/fichier/hep_b3',
                      '/fichier/hib1', '/fichier/hib2', '/fichier/hib3', '/fichier/ror']
    
    for i, patient in enumerate(all_patients):
        name = f"{patient.get('/fichier/prenom', '')} {patient.get('/fichier/nom', '')}"
        
        # Count standard vaccines
        standard_count = sum(1 for field in standard_fields if patient.get(field))
        
        # Count non-standard vaccines
        autres_vaccins = patient.get('parsed_autres_vaccins', [])
        nonstandard_count = len(autres_vaccins)
        
        total_vaccines = standard_count + nonstandard_count
        
        if total_vaccines > 0:
            patients_with_vaccines.append({
                'index': i,
                'name': name,
                'standard_vaccines': standard_count,
                'nonstandard_vaccines': nonstandard_count,
                'total_vaccines': total_vaccines,
                'patient_data': patient
            })
    
    print(f"\n📊 Found {len(patients_with_vaccines)} patients with vaccine data")
    
    # Show top 10 patients with most vaccines
    patients_with_vaccines.sort(key=lambda x: x['total_vaccines'], reverse=True)
    
    print("\n🏆 TOP 10 PATIENTS WITH MOST VACCINES:")
    for i, p in enumerate(patients_with_vaccines[:10]):
        print(f"{i+1:2d}. {p['name']} (Index {p['index']}) - {p['total_vaccines']} vaccines "
              f"({p['standard_vaccines']} standard, {p['nonstandard_vaccines']} non-standard)")
    
    # Show some examples of the vaccines
    if patients_with_vaccines:
        print(f"\n🧪 DETAILED VACCINE DATA FOR TOP PATIENT:")
        top_patient = patients_with_vaccines[0]
        patient_data = top_patient['patient_data']
        
        print(f"Patient: {top_patient['name']}")
        
        # Show standard vaccines
        print("Standard vaccines:")
        for field in standard_fields:
            value = patient_data.get(field)
            if value:
                print(f"  - {field}: {value}")
        
        # Show non-standard vaccines
        autres_vaccins = patient_data.get('parsed_autres_vaccins', [])
        if autres_vaccins:
            print("Non-standard vaccines:")
            for vaccine in autres_vaccins[:5]:  # Show first 5
                print(f"  - {vaccine.get('vaccine_name')}: {vaccine.get('vaccine_date')}")
            if len(autres_vaccins) > 5:
                print(f"  ... and {len(autres_vaccins) - 5} more")
    
    print("\n" + "=" * 50)
    
    # Return indices of patients we can use for testing
    if len(patients_with_vaccines) >= 2:
        test_indices = [patients_with_vaccines[0]['index'], patients_with_vaccines[1]['index']]
        print(f"🎯 Use patient indices {test_indices} for testing")
        return test_indices
    else:
        print("⚠️  Not enough patients with vaccine data found")
        return []

if __name__ == "__main__":
    find_vaccine_patients() 