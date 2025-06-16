#!/usr/bin/env python3

import sqlite3
import emr_config

def check_outlier_type():
    """Check what type of outlier MRN 10715 actually is"""
    
    try:
        from statistics_engine.statistics_calculator import find_measurement_outliers
        
        config = emr_config.EMRConfig()
        db_path = config.get_database_path()
        
        # Get outliers
        outliers = find_measurement_outliers(db_path=db_path, std_dev_threshold=4.0, age_limit_months=60)
        
        # Find outliers for MRN 10715
        mrn_outliers = [o for o in outliers if o['patient_mrn'] == '10715']
        
        print("Outliers for MRN 10715:")
        print("=" * 50)
        
        for outlier in mrn_outliers:
            print(f"Type: {outlier['measurement_type']}")
            print(f"Value: {outlier['value']}")
            print(f"Age: {outlier['age_months']} months")
            print(f"Sex: {outlier['sex']}")
            print(f"Std Devs: {outlier['num_std_devs']}")
            print("-" * 30)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_outlier_type() 