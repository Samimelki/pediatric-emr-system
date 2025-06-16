#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from routes.statistics_routes import extract_visit_with_all_measurements

def test_extract_function():
    """Test the fixed extract_visit_with_all_measurements function"""
    
    print("Testing extract_visit_with_all_measurements function...")
    print("=" * 60)
    
    # Test with a patient that has no raw_dossier_text but has raw_visit_entry
    # Using MRN 10715 (MARINE CHALHOUB, patient_id 10713)
    
    # Test case 1: Weight outlier
    result = extract_visit_with_all_measurements(
        raw_dossier_text=None,  # No raw dossier text
        target_value=3.9,       # 3.9 kg weight
        measurement_type='Weight (kg)',
        patient_id=10713
    )
    
    print("Test 1 - Weight outlier (3.9kg):")
    print(f"  Visit text: {result['visit_text']}")
    print(f"  Measurements: {result['measurements']}")
    print(f"  Visit date: {result['visit_date']}")
    
    if result['visit_text'] and result['measurements']:
        print("  ✅ SUCCESS: Found measurements and visit text")
    else:
        print("  ❌ FAILED: Missing measurements or visit text")
    
    print("\n" + "-"*50)
    
    # Test case 2: Height outlier
    result2 = extract_visit_with_all_measurements(
        raw_dossier_text=None,
        target_value=51.5,      # 51.5 cm height
        measurement_type='Height (cm)',
        patient_id=10713
    )
    
    print("Test 2 - Height outlier (51.5cm):")
    print(f"  Visit text: {result2['visit_text']}")
    print(f"  Measurements: {result2['measurements']}")
    print(f"  Visit date: {result2['visit_date']}")
    
    if result2['visit_text'] and result2['measurements']:
        print("  ✅ SUCCESS: Found measurements and visit text")
    else:
        print("  ❌ FAILED: Missing measurements or visit text")

if __name__ == "__main__":
    test_extract_function() 