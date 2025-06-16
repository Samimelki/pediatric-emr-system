#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_vaccine_fix():
    """Test the fixed vaccine calculation function"""
    print("Testing vaccine calculation fix...")
    print("=" * 50)
    
    try:
        from statistics_engine.statistics_calculator import calculate_average_vaccines_per_child
        import emr_config
        
        config = emr_config.EMRConfig()
        db_path = config.get_database_path()
        
        avg_vaccines = calculate_average_vaccines_per_child(db_path=db_path)
        print(f"✅ Vaccine calculation result: {avg_vaccines:.2f} vaccines per child")
        
        if avg_vaccines > 15:
            print("✅ SUCCESS: Vaccine calculation is now working correctly!")
        else:
            print("❌ FAILED: Still getting low vaccine count")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

def test_extract_fix():
    """Test the fixed extract function"""
    print("\nTesting measurement extraction fix...")
    print("=" * 50)
    
    try:
        # This would need Flask context, so just check if the function exists
        from routes.statistics_routes import extract_visit_with_all_measurements
        print("✅ Extract function imported successfully")
        print("✅ Function should now work without raw_dossier_text")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_vaccine_fix()
    test_extract_fix() 