#!/usr/bin/env python3
"""
CSV Header Analysis Script

This script analyzes CSV file headers to identify the correct field mappings
for birth measurements and other data fields.
"""

import sys
import os
from csv_importer import CSVImporter


def analyze_csv_file(csv_path: str):
    """Analyze a CSV file and print header analysis."""
    
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        return
    
    print(f"Analyzing CSV file: {csv_path}")
    print("=" * 60)
    
    # Create importer instance
    importer = CSVImporter("dummy.db")  # We don't need actual DB for header analysis
    
    try:
        # Analyze headers
        analysis = importer.analyze_csv_headers(csv_path)
        
        print(f"Total headers found: {len(analysis['all_headers'])}")
        print("\nALL HEADERS:")
        for i, header in enumerate(analysis['all_headers'], 1):
            print(f"  {i:2d}. {header}")
        
        print(f"\nBIRTH-RELATED HEADERS ({len(analysis['birth_related'])}):")
        for header in analysis['birth_related']:
            print(f"  - {header}")
        
        print(f"\nNAME-RELATED HEADERS ({len(analysis['name_related'])}):")
        for header in analysis['name_related']:
            print(f"  - {header}")
        
        print(f"\nDATE-RELATED HEADERS ({len(analysis['date_related'])}):")
        for header in analysis['date_related']:
            print(f"  - {header}")
        
        print(f"\nPARENT-RELATED HEADERS ({len(analysis['parent_related'])}):")
        for header in analysis['parent_related']:
            print(f"  - {header}")
        
        # Suggest field mappings
        print("\nSUGGESTED FIELD MAPPINGS:")
        print("Current importer expects these French field names:")
        print("  - poids_naissance → birth_weight_g")
        print("  - taille_naissance → birth_height_cm")
        print("  - pc_naissance → birth_head_circumference_cm")
        print("  - notes_naissance → birth_notes")
        print("  - mere_nom → mother's name")
        print("  - pere_nom → father's name")
        
        if analysis['birth_related']:
            print("\nYour CSV appears to have these birth-related fields:")
            for header in analysis['birth_related']:
                print(f"  - {header}")
        
        if analysis['parent_related']:
            print("\nYour CSV appears to have these parent-related fields:")
            for header in analysis['parent_related']:
                print(f"  - {header}")
        
    except Exception as e:
        print(f"Error analyzing CSV: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_csv_headers.py <csv_file_path>")
        print("Example: python analyze_csv_headers.py patients.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    analyze_csv_file(csv_file) 