#!/usr/bin/env python3
"""
Migration Utility for EMR Database Field Standardization

This script fixes the French/English field confusion in the database by:
1. Ensuring all patients have both French and English fields populated
2. Correcting any swapped name fields (first_name/last_name vs prenom/nom)
3. Standardizing all field mappings

Usage: python migration_utility.py
"""

import sqlite3
import os
from typing import Dict, Any
from unified_database import standardize_patient_fields


def migrate_patient_field_standardization(db_path: str) -> Dict[str, int]:
    """
    Migrate database to fix French/English field confusion.
    
    Returns:
        Dictionary with migration statistics
    """
    stats = {
        'patients_processed': 0,
        'patients_updated': 0,
        'errors': 0
    }
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")
    
            conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable row access by column name
            cursor = conn.cursor()
    
    try:
        # Get all patients
        cursor.execute("SELECT * FROM Patients")
        patients = cursor.fetchall()
        
        for patient in patients:
            stats['patients_processed'] += 1
            
            try:
                # Convert to dict for processing
                patient_dict = dict(patient)
                
                # Apply standardization - but standardize_patient_fields expects a dict with .get() method
                # So we need to handle the Row object properly
                standardized = standardize_patient_fields(patient_dict)
                
                # Check if any fields need updating
                needs_update = False
                update_fields = {}
                
                # Key fields to check and update
                fields_to_check = [
                    'first_name', 'last_name', 'prenom', 'nom',
                    'date_of_birth', 'naissance_date',
                    'sex', 'sexe',
                    'phone', 'telephone',
                    'address', 'domicile'
                ]
                
                for field in fields_to_check:
                    # Compare standardized value with original value from database
                    original_value = patient[field] if field in patient.keys() else None
                    standardized_value = standardized.get(field)
                    
                    if standardized_value != original_value:
                        needs_update = True
                        update_fields[field] = standardized_value
                
                if needs_update:
                    # Build update query
                    set_clauses = []
                    values = []
                    
                    for field, value in update_fields.items():
                        set_clauses.append(f"{field} = ?")
                        values.append(value)
                    
                    if set_clauses:
                        update_query = f"UPDATE Patients SET {', '.join(set_clauses)} WHERE id = ?"
                        values.append(patient['id'])
                        
                        cursor.execute(update_query, values)
                        stats['patients_updated'] += 1
                        
                        print(f"Updated patient {patient['id']} ({patient.get('mrn', 'No MRN')}): {list(update_fields.keys())}")
                
            except Exception as e:
                stats['errors'] += 1
                print(f"Error processing patient {patient['id']}: {e}")
                continue
        
        conn.commit()
        print(f"\nMigration completed:")
        print(f"- Patients processed: {stats['patients_processed']}")
        print(f"- Patients updated: {stats['patients_updated']}")
        print(f"- Errors: {stats['errors']}")
        
    except Exception as e:
        conn.rollback()
        raise Exception(f"Migration failed: {e}")
    finally:
        conn.close()
    
    return stats


def verify_field_consistency(db_path: str) -> Dict[str, int]:
    """
    Verify that all patients have consistent French/English field mapping.
    
    Returns:
        Dictionary with verification statistics
    """
    stats = {
        'total_patients': 0,
        'missing_english_names': 0,
        'missing_french_names': 0,
        'missing_birth_dates': 0,
        'missing_contact_info': 0,
        'inconsistent_fields': 0
    }
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM Patients")
        patients = cursor.fetchall()
        
        for patient in patients:
            stats['total_patients'] += 1
            patient_dict = dict(patient)
            
            # Check for missing English names
            if not patient_dict.get('first_name') or not patient_dict.get('last_name'):
                stats['missing_english_names'] += 1
                print(f"Patient {patient['id']} missing English names: first_name='{patient_dict.get('first_name')}', last_name='{patient_dict.get('last_name')}'")
            
            # Check for missing French names
            if not patient_dict.get('prenom') or not patient_dict.get('nom'):
                stats['missing_french_names'] += 1
                print(f"Patient {patient['id']} missing French names: prenom='{patient_dict.get('prenom')}', nom='{patient_dict.get('nom')}'")
            
            # Check for missing birth dates
            if not patient_dict.get('date_of_birth') and not patient_dict.get('naissance_date'):
                stats['missing_birth_dates'] += 1
            
            # Check for inconsistent field mapping
            if (patient_dict.get('first_name') and patient_dict.get('prenom') and 
                patient_dict['first_name'] != patient_dict['prenom']):
                stats['inconsistent_fields'] += 1
                print(f"Patient {patient['id']} has inconsistent names: first_name='{patient_dict['first_name']}' vs prenom='{patient_dict['prenom']}'")
    
    finally:
        conn.close()
    
    return stats


if __name__ == "__main__":
    import sys
    
    # Use the unified EMR database path
    db_path = os.path.expanduser("~/Documents/UnifiedEMR/unified_emr.db")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "verify":
            print("Verifying field consistency...")
            stats = verify_field_consistency(db_path)
            print("\nVerification Results:")
            for key, value in stats.items():
                print(f"- {key}: {value}")
        elif sys.argv[1] == "migrate":
            print("Starting migration...")
            stats = migrate_patient_field_standardization(db_path)
        else:
            print("Usage: python migration_utility.py [verify|migrate]")
    else:
        print("Usage: python migration_utility.py [verify|migrate]")
        print("  verify  - Check field consistency without making changes")
        print("  migrate - Fix field mapping issues") 