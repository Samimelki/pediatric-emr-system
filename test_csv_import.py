#!/usr/bin/env python3

import sys
import os
import tempfile
import csv
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from csv_importer import CSVImporter
import emr_config

def create_test_csv_files():
    """Create test CSV files with French characters for testing"""
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Test patients data with French characters
    patients_data = [
        {
            'id': '99001',
            'mrn': 'TEST001',
            'first_name': 'François',
            'last_name': 'Dupré',
            'date_of_birth': '2020-01-15',
            'sex': 'M',
            'phone': '514-555-0001',
            'address': '123 Rue Montréal, Québec',
            'email': 'francois.dupre@test.com',
            'insurance': 'RAMQ',
            'primary_physician': 'Dr. André Côté',
            'pmh': 'Aucun antécédent médical',
            'psh': 'Aucun antécédent chirurgical',
            'family_history': 'Père: hypertension',
            'medications': 'Aucun',
            'allergies': 'Pénicilline',
            'smoker': 'Non',
            'smoker_details': '',
            'alcohol': 'Non',
            'alcohol_details': '',
            'raw_dossier_text': 'Patient pédiatrique en bonne santé'
        },
        {
            'id': '99002',
            'mrn': 'TEST002',
            'first_name': 'Élise',
            'last_name': 'Bélanger',
            'date_of_birth': '2019-06-20',
            'sex': 'F',
            'phone': '514-555-0002',
            'address': '456 Avenue Québec, Montréal',
            'email': 'elise.belanger@test.com',
            'insurance': 'RAMQ',
            'primary_physician': 'Dr. Françoise Léger',
            'pmh': 'Asthme léger',
            'psh': 'Aucun',
            'family_history': 'Mère: allergies saisonnières',
            'medications': 'Ventolin au besoin',
            'allergies': 'Arachides, œufs',
            'smoker': 'Non',
            'smoker_details': '',
            'alcohol': 'Non',
            'alcohol_details': '',
            'raw_dossier_text': 'Patiente avec asthme bien contrôlé'
        }
    ]
    
    # Test visits data
    visits_data = [
        {
            'id': '99001',
            'patient_id': '99001',
            'visit_date': '2024-01-15',
            'age_at_visit_months': '48',
            'weight_kg': '16.5',
            'height_cm': '102.0',
            'head_circumference_cm': '50.2',
            'temperature_c': '36.8',
            'heart_rate_bpm': '95',
            'respiratory_rate_bpm': '22',
            'blood_pressure_systolic': '',
            'blood_pressure_diastolic': '',
            'oxygen_saturation_percent': '98.5',
            'visit_notes': 'Examen de routine - développement normal',
            'diagnosis': 'Enfant en bonne santé',
            'treatment_plan': 'Continuer surveillance régulière',
            'follow_up_instructions': 'Prochain rendez-vous dans 6 mois'
        },
        {
            'id': '99002',
            'patient_id': '99002',
            'visit_date': '2024-01-20',
            'age_at_visit_months': '54',
            'weight_kg': '18.2',
            'height_cm': '105.5',
            'head_circumference_cm': '51.0',
            'temperature_c': '37.1',
            'heart_rate_bpm': '88',
            'respiratory_rate_bpm': '20',
            'blood_pressure_systolic': '',
            'blood_pressure_diastolic': '',
            'oxygen_saturation_percent': '99.0',
            'visit_notes': 'Suivi asthme - aucun épisode récent',
            'diagnosis': 'Asthme stable',
            'treatment_plan': 'Continuer traitement actuel',
            'follow_up_instructions': 'Retour si symptômes'
        }
    ]
    
    # Test immunizations data
    immunizations_data = [
        {
            'id': '99001',
            'patient_id': '99001',
            'immunization': 'DTaP-IPV',
            'administered_date': '2024-01-15',
            'brand_name': 'Quadracel',
            'dose_number': '4',
            'notes': 'Rappel à 4 ans - bien toléré'
        },
        {
            'id': '99002',
            'patient_id': '99002',
            'immunization': 'MMR',
            'administered_date': '2024-01-20',
            'brand_name': 'M-M-R II',
            'dose_number': '2',
            'notes': 'Deuxième dose - aucune réaction'
        }
    ]
    
    # Write CSV files with UTF-8 BOM
    csv_files = {}
    
    # Patients CSV
    patients_file = os.path.join(temp_dir, 'patients.csv')
    with open(patients_file, 'w', encoding='utf-8-sig', newline='') as f:
        if patients_data:
            writer = csv.DictWriter(f, fieldnames=patients_data[0].keys())
            writer.writeheader()
            writer.writerows(patients_data)
    csv_files['patients'] = patients_file
    
    # Visits CSV
    visits_file = os.path.join(temp_dir, 'visits.csv')
    with open(visits_file, 'w', encoding='utf-8-sig', newline='') as f:
        if visits_data:
            writer = csv.DictWriter(f, fieldnames=visits_data[0].keys())
            writer.writeheader()
            writer.writerows(visits_data)
    csv_files['visits'] = visits_file
    
    # Immunizations CSV
    immunizations_file = os.path.join(temp_dir, 'immunizations.csv')
    with open(immunizations_file, 'w', encoding='utf-8-sig', newline='') as f:
        if immunizations_data:
            writer = csv.DictWriter(f, fieldnames=immunizations_data[0].keys())
            writer.writeheader()
            writer.writerows(immunizations_data)
    csv_files['immunizations'] = immunizations_file
    
    return temp_dir, csv_files

def test_csv_import():
    """Test the fixed CSV importer with actual exported data"""
    
    # Initialize importer
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    importer = CSVImporter(db_path)
    
    # Test import with the actual CSV files
    csv_directory = '../Documents/emr_csv_export_20250616_123235'
    
    print("Starting CSV import test...")
    print(f"CSV directory: {csv_directory}")
    print(f"Database path: {db_path}")
    print("-" * 50)
    
    try:
        results = importer.import_csv_bundle(csv_directory, update_existing=True)
        
        print('Import Results:')
        total_imported = 0
        total_errors = 0
        
        for file_type, stats in results.items():
            print(f'{file_type}: {stats}')
            if isinstance(stats, dict) and 'imported' in stats:
                total_imported += stats.get('imported', 0)
                total_errors += stats.get('errors', 0)
        
        print(f"\nSummary:")
        print(f"Total imported: {total_imported}")
        print(f"Total errors: {total_errors}")
        
        # Show detailed errors if any
        errors = importer.get_detailed_errors(20)
        if errors:
            print('\nFirst 20 Detailed Errors:')
            for i, error in enumerate(errors, 1):
                print(f'  {i}. {error}')
        else:
            print('\nNo detailed errors!')
            
    except Exception as e:
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_import() 