#!/usr/bin/env python3

import csv
import os
from pathlib import Path

class WHODataLoader:
    """
    Loads WHO standards data from CSV files for growth charts.
    Expects data in format: Month,P3,P15,P50,P85,P97
    """
    
    def __init__(self, data_dir="data/who_standards"):
        self.data_dir = Path(data_dir)
        self.cache = {}
    
    def load_percentile_data(self, measurement_type, sex):
        """
        Load WHO percentile data for specific measurement and sex.
        
        Args:
            measurement_type: 'wfa', 'lhfa', 'hcfa', or 'hfa_5_19'
            sex: 'boys' or 'girls'
            
        Returns:
            Dict with keys: Month, P3, P15, P50, P85, P97
            Each key maps to a list of values
        """
        cache_key = f"{measurement_type}_{sex}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Determine filename based on measurement type and sex
        if measurement_type == 'wfa':
            filename = f"wfa_{sex}_0_5_percentiles.csv"
        elif measurement_type == 'lhfa':
            filename = f"lhfa_{sex}_0_5_percentiles.csv"
        elif measurement_type == 'hcfa':
            filename = f"hcfa_{sex}_0_5_percentiles.csv"
        elif measurement_type == 'hfa_5_19':
            filename = f"hfa_{sex}_p_5_19.csv"
        else:
            return None
            
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            print(f"WHO data file not found: {filepath}")
            return None
            
        try:
            data = {
                'Month': [],
                'P3': [],
                'P15': [],
                'P50': [],
                'P85': [],
                'P97': []
            }
            
            with open(filepath, 'r') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    data['Month'].append(int(row['Month']))
                    # Handle different column naming conventions
                    if 'P3' in row:
                        # Standard format: P3, P15, P50, P85, P97
                        data['P3'].append(float(row['P3']))
                        data['P15'].append(float(row['P15']))
                        data['P50'].append(float(row['P50']))
                        data['P85'].append(float(row['P85']))
                        data['P97'].append(float(row['P97']))
                    elif '3rd' in row:
                        # Alternative format: 3rd, 15th, 50th, 85th, 97th
                        data['P3'].append(float(row['3rd']))
                        data['P15'].append(float(row['15th']))
                        data['P50'].append(float(row['50th']))
                        data['P85'].append(float(row['85th']))
                        data['P97'].append(float(row['97th']))
                    else:
                        raise ValueError(f"Unknown column format in {filepath}")
            
            # Cache the loaded data
            self.cache[cache_key] = data
            return data
            
        except Exception as e:
            print(f"Error loading WHO data from {filepath}: {e}")
            return None
    
    def get_chart_data_for_patient(self, patient_sex, measurement_type="wfa"):
        """
        Get WHO chart data for a specific patient sex and measurement type.
        
        Args:
            patient_sex: 'M', 'F', 'Male', 'Female', or similar
            measurement_type: 'wfa', 'lhfa', 'hcfa', or 'hfa_5_19'
            
        Returns:
            WHO percentile data dict or None if not available
        """
        # Normalize sex to boys/girls
        if not patient_sex:
            return None
            
        sex_normalized = patient_sex.lower()
        if sex_normalized in ['m', 'male', 'boy', 'boys']:
            who_sex = 'boys'
        elif sex_normalized in ['f', 'female', 'girl', 'girls']:
            who_sex = 'girls'  
        else:
            return None
            
        return self.load_percentile_data(measurement_type, who_sex)
    
    def prepare_chart_data_for_patient(self, patient_sex):
        """
        Prepare all chart data for a patient (wfa, lhfa, hcfa).
        
        Returns:
            Dict with keys: who_wfa_data, who_lhfa_data, who_hc_data, patient_sex_for_chart
        """
        # Normalize patient sex for chart background
        patient_sex_for_chart = None
        if patient_sex:
            sex_normalized = patient_sex.lower()
            if sex_normalized in ['m', 'male', 'boy', 'boys']:
                patient_sex_for_chart = 'boys'
            elif sex_normalized in ['f', 'female', 'girl', 'girls']:
                patient_sex_for_chart = 'girls'
        
        return {
            'who_wfa_data': self.get_chart_data_for_patient(patient_sex, 'wfa'),
            'who_lhfa_data': self.get_chart_data_for_patient(patient_sex, 'lhfa'), 
            'who_hc_data': self.get_chart_data_for_patient(patient_sex, 'hcfa'),
            'who_hfa_5_19_data': self.get_chart_data_for_patient(patient_sex, 'hfa_5_19'),
            'patient_sex_for_chart': patient_sex_for_chart
        }

# Global instance
who_loader = WHODataLoader() 