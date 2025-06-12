#!/usr/bin/env python3
"""
Unified Immunization Import Service

This service handles importing vaccine data from XML and converting it to the unified
immunization system:
- Maps standard vaccine XML columns to canonical disease names
- Maps non-standard vaccine brands to canonical diseases using comprehensive mapping
- Stores all vaccines (standard and non-standard) in the unified Immunizations table
- Eliminates separate standard vaccine columns and NonStandardVaccines table
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys
import os

# Add parent directory to path to import our services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.config_service import ImmunizationConfigService
from services.immunization_service import ImmunizationService
from services.models import ImmunizationAdministration

class UnifiedImmunizationImporter:
    """Handles importing and converting vaccine data to unified immunization records."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.config_service = ImmunizationConfigService()
        self.immunization_service = ImmunizationService(db_path)
        
        # Load comprehensive mapping
        self.comprehensive_mapping = self.config_service.comprehensive_mapping
        self.brand_to_disease = self.config_service.get_brand_to_disease_mapping()
        
        # Standard vaccine column mappings (XML to canonical disease)
        self.standard_vaccine_columns = {
            # DTaP series
            '/fichier/dtcp1': ('DTaP - IPV', 1),
            '/fichier/dtcp2': ('DTaP - IPV', 2), 
            '/fichier/dtcp3': ('DTaP - IPV', 3),
            '/fichier/rdtcp1': ('DTaP - IPV', 4),  # First booster
            '/fichier/rdtcp2': ('DTaP - IPV', 5),  # Second booster
            '/fichier/rdtcp3': ('DTaP - IPV', 6),  # Third booster
            '/fichier/rdtcp4': ('DTaP - IPV', 7),  # Fourth booster
            
            # Hepatitis B series
            '/fichier/hep_b1': ('Hepatitis B', 1),
            '/fichier/hep_b2': ('Hepatitis B', 2),
            '/fichier/hep_b3': ('Hepatitis B', 3),
            
            # Haemophilus influenzae type b series
            '/fichier/hib1': ('Haemophilus influenzae type b (Hib)', 1),
            '/fichier/hib2': ('Haemophilus influenzae type b (Hib)', 2),
            '/fichier/hib3': ('Haemophilus influenzae type b (Hib)', 3),
            '/fichier/hib_rappel': ('Haemophilus influenzae type b (Hib)', 4),
            
            # Single dose vaccines
            '/fichier/ror': ('Measles - Mumps - Rubella (MMR)', 1),
            '/fichier/r': ('Measles', 1),  # Measles alone
        }
        
        self.import_stats = {
            'standard_vaccines_imported': 0,
            'nonstandard_vaccines_imported': 0,
            'unmapped_brands': set(),
            'errors': []
        }
    
    def import_patient_vaccines(self, patient_id: int, patient_xml_data: Dict) -> int:
        """Import all vaccines for a patient from XML data."""
        total_imported = 0
        
        # Import standard vaccines from XML columns
        standard_count = self._import_standard_vaccines(patient_id, patient_xml_data)
        total_imported += standard_count
        self.import_stats['standard_vaccines_imported'] += standard_count
        
        # Import non-standard vaccines from parsed data
        parsed_autres_vaccins = patient_xml_data.get('parsed_autres_vaccins', [])
        nonstandard_count = self._import_nonstandard_vaccines(patient_id, parsed_autres_vaccins) 
        total_imported += nonstandard_count
        self.import_stats['nonstandard_vaccines_imported'] += nonstandard_count
        
        return total_imported
    
    def _import_standard_vaccines(self, patient_id: int, patient_xml_data: Dict) -> int:
        """Import standard vaccines from XML column data."""
        imported_count = 0
        
        for xml_column, (canonical_disease, dose_number) in self.standard_vaccine_columns.items():
            vaccine_date = patient_xml_data.get(xml_column)
            
            if vaccine_date:
                try:
                    # Parse date string to YYYY-MM-DD format
                    if 'T' in vaccine_date:
                        clean_date = vaccine_date.split('T')[0]  # Remove time component
                    else:
                        clean_date = vaccine_date
                    
                    # Create ImmunizationAdministration object
                    administration = ImmunizationAdministration(
                        patient_id=patient_id,
                        immunization=canonical_disease,
                        administered_date=clean_date,
                        dose_number=dose_number,
                        notes=f"Imported from XML column {xml_column}",
                        source='import'
                    )
                    
                    # Save to database using correct method name
                    record_id = self.immunization_service.add_immunization(administration)
                    if record_id:
                        imported_count += 1
                    
                except Exception as e:
                    error_msg = f"Error importing standard vaccine {xml_column} for patient {patient_id}: {str(e)}"
                    self.import_stats['errors'].append(error_msg)
                    print(f"  ⚠️  {error_msg}")
        
        return imported_count
    
    def _import_nonstandard_vaccines(self, patient_id: int, parsed_vaccines: List[Dict]) -> int:
        """Import non-standard vaccines using comprehensive brand name mapping."""
        imported_count = 0
        
        for vaccine_entry in parsed_vaccines:
            brand_name = vaccine_entry.get('vaccine_name', '').strip()
            vaccine_date = vaccine_entry.get('vaccine_date')
            
            if not brand_name or not vaccine_date:
                continue
            
            # Look up canonical disease name using comprehensive mapping
            canonical_disease = self.brand_to_disease.get(brand_name)
            
            if canonical_disease:
                try:
                    # Create ImmunizationAdministration object
                    administration = ImmunizationAdministration(
                        patient_id=patient_id,
                        immunization=canonical_disease,
                        administered_date=vaccine_date,
                        brand_name=brand_name,
                        notes=f"Imported from XML autres_vac: {vaccine_entry.get('raw_entry', '')}",
                        source='import'
                    )
                    
                    # Save to database using correct method name
                    record_id = self.immunization_service.add_immunization(administration)
                    if record_id:
                        imported_count += 1
                    
                except Exception as e:
                    error_msg = f"Error importing non-standard vaccine {brand_name} for patient {patient_id}: {str(e)}"
                    self.import_stats['errors'].append(error_msg)
                    print(f"    ⚠️  {error_msg}")
            else:
                # Track unmapped brands for reporting
                self.import_stats['unmapped_brands'].add(brand_name)
                print(f"    ⚠️  Unmapped vaccine brand: {brand_name}")
        
        return imported_count
    
    def get_import_stats(self) -> Dict:
        """Get statistics from the import process."""
        return {
            'standard_vaccines_imported': self.import_stats['standard_vaccines_imported'],
            'nonstandard_vaccines_imported': self.import_stats['nonstandard_vaccines_imported'],
            'total_vaccines_imported': self.import_stats['standard_vaccines_imported'] + self.import_stats['nonstandard_vaccines_imported'],
            'unmapped_brands': list(self.import_stats['unmapped_brands']),
            'errors': self.import_stats['errors']
        }
    
    def print_import_summary(self):
        """Print a summary of the import process."""
        stats = self.get_import_stats()
        
        print("\n📊 UNIFIED IMMUNIZATION IMPORT SUMMARY")
        print("-" * 50)
        print(f"Standard vaccines imported: {stats['standard_vaccines_imported']}")
        print(f"Non-standard vaccines imported: {stats['nonstandard_vaccines_imported']}")
        print(f"Total vaccines imported: {stats['total_vaccines_imported']}")
        
        if stats['unmapped_brands']:
            print(f"\n⚠️  Unmapped vaccine brands ({len(stats['unmapped_brands'])}):")
            for brand in sorted(stats['unmapped_brands']):
                print(f"   - {brand}")
        
        if stats['errors']:
            print(f"\n❌ Import errors ({len(stats['errors'])}):")
            for error in stats['errors']:
                print(f"   - {error}")
        
        if not stats['errors'] and not stats['unmapped_brands']:
            print("\n✅ All vaccines imported successfully!")
        
        print("-" * 50)


# Replacement function for existing populate_db.py vaccine import
def import_vaccines_unified(patient_id: int, patient_xml_data: Dict, db_path: str) -> int:
    """
    Unified vaccine import function to replace the existing _insert_non_standard_vaccines_unified
    and standard vaccine column processing.
    
    This function:
    1. Processes both standard and non-standard vaccines
    2. Uses comprehensive mapping to convert brands to canonical diseases  
    3. Stores everything in the unified Immunizations table
    """
    importer = UnifiedImmunizationImporter(db_path)
    return importer.import_patient_vaccines(patient_id, patient_xml_data) 