#!/usr/bin/env python3
"""
Migration script to convert existing vaccine data to the unified Immunizations system.

This script:
1. Reads existing standard vaccine columns (dtcp_date, hep_b_date, etc.)
2. Reads NonStandardVaccines table entries
3. Uses comprehensive vaccine mapping to convert to canonical disease names
4. Inserts all data into the new Immunizations table
5. Provides detailed migration report

Run this ONCE after creating the Immunizations table.
"""

import sqlite3
import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional

# Add parent directory to path to import our services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.config_service import ImmunizationConfigService

class VaccineMigrator:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.config_service = ImmunizationConfigService()
        self.comprehensive_mapping = self.config_service.get_comprehensive_mapping()
        
        # Standard vaccine column mappings
        self.standard_columns = {
            'dtcp_date': 'DTaP - IPV',
            'hep_b_date': 'Hepatitis B',
            'polio_date': 'Polio',
            'hib_date': 'Haemophilus influenzae type b (Hib)',
            'pcv_date': 'Pneumococcal Conjugate Vaccine (PCV)',
            'rotavirus_date': 'Rotavirus',
            'mmr_date': 'Measles - Mumps - Rubella (MMR)',
            'varicella_date': 'Varicella (Chickenpox)',
            'hep_a_date': 'Hepatitis A',
            'meningococcal_date': 'Meningococcal',
            'hpv_date': 'Human Papillomavirus (HPV)',
            'tdap_date': 'Tetanus - Diphtheria - Pertussis (Tdap)',
            'influenza_date': 'Influenza',
            'covid_date': 'COVID-19'
        }
        
        self.migration_stats = {
            'standard_vaccines_migrated': 0,
            'nonstandard_vaccines_migrated': 0,
            'unmapped_brands': set(),
            'errors': [],
            'patients_processed': 0
        }
    
    def connect_db(self) -> sqlite3.Connection:
        """Create database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_patients_with_vaccines(self) -> List[sqlite3.Row]:
        """Get all patients who have vaccine data."""
        conn = self.connect_db()
        try:
            # Build dynamic query for patients with any standard vaccine dates
            standard_conditions = [f"{col} IS NOT NULL" for col in self.standard_columns.keys()]
            query = f"""
            SELECT DISTINCT p.id, p.first_name, p.last_name, p.mrn
            FROM Patients p
            WHERE {' OR '.join(standard_conditions)}
            
            UNION
            
            SELECT DISTINCT p.id, p.first_name, p.last_name, p.mrn
            FROM Patients p
            JOIN NonStandardVaccines nsv ON p.id = nsv.patient_id
            
            ORDER BY p.mrn
            """
            
            cursor = conn.cursor()
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def migrate_standard_vaccines(self, patient_id: int) -> int:
        """Migrate standard vaccine columns for a patient."""
        conn = self.connect_db()
        migrated_count = 0
        
        try:
            # Get patient's standard vaccine dates
            columns = ', '.join(self.standard_columns.keys())
            cursor = conn.cursor()
            cursor.execute(f"SELECT {columns} FROM Patients WHERE id = ?", (patient_id,))
            patient_vaccines = cursor.fetchone()
            
            if not patient_vaccines:
                return 0
            
            # Convert to dict for easier access
            vaccine_data = dict(patient_vaccines)
            
            # Insert each non-null vaccine date
            for column, canonical_disease in self.standard_columns.items():
                vaccine_date = vaccine_data.get(column)
                if vaccine_date:
                    try:
                        cursor.execute("""
                            INSERT INTO Immunizations 
                            (patient_id, immunization, administered_date, dose_number, 
                             notes, source, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            patient_id,
                            canonical_disease,
                            vaccine_date,
                            1,  # Standard vaccines typically recorded as single dose
                            f"Migrated from {column}",
                            'migration',
                            datetime.now(),
                            datetime.now()
                        ))
                        migrated_count += 1
                        
                    except Exception as e:
                        error_msg = f"Error migrating {column} for patient {patient_id}: {str(e)}"
                        self.migration_stats['errors'].append(error_msg)
                        print(f"  ⚠️  {error_msg}")
            
            conn.commit()
            
        except Exception as e:
            error_msg = f"Error processing standard vaccines for patient {patient_id}: {str(e)}"
            self.migration_stats['errors'].append(error_msg)
            print(f"  ❌ {error_msg}")
            
        finally:
            conn.close()
            
        return migrated_count
    
    def migrate_nonstandard_vaccines(self, patient_id: int) -> int:
        """Migrate NonStandardVaccines entries for a patient."""
        conn = self.connect_db()
        migrated_count = 0
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT vaccine_name, vaccine_date, notes
                FROM NonStandardVaccines 
                WHERE patient_id = ?
                ORDER BY vaccine_date
            """, (patient_id,))
            
            nonstandard_vaccines = cursor.fetchall()
            
            for vaccine in nonstandard_vaccines:
                brand_name = vaccine['vaccine_name']
                vaccine_date = vaccine['vaccine_date']
                notes = vaccine['notes'] or ''
                
                # Look up canonical disease name
                canonical_disease = self.comprehensive_mapping.get('brand_names', {}).get(brand_name)
                
                if canonical_disease:
                    try:
                        cursor.execute("""
                            INSERT INTO Immunizations 
                            (patient_id, immunization, administered_date, brand_name, 
                             notes, source, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            patient_id,
                            canonical_disease,
                            vaccine_date,
                            brand_name,
                            f"Migrated from NonStandardVaccines. {notes}".strip(),
                            'migration',
                            datetime.now(),
                            datetime.now()
                        ))
                        migrated_count += 1
                        
                    except Exception as e:
                        error_msg = f"Error migrating {brand_name} for patient {patient_id}: {str(e)}"
                        self.migration_stats['errors'].append(error_msg)
                        print(f"    ⚠️  {error_msg}")
                        
                else:
                    self.migration_stats['unmapped_brands'].add(brand_name)
                    print(f"    ⚠️  Unmapped brand: {brand_name}")
            
            conn.commit()
            
        except Exception as e:
            error_msg = f"Error processing non-standard vaccines for patient {patient_id}: {str(e)}"
            self.migration_stats['errors'].append(error_msg)
            print(f"  ❌ {error_msg}")
            
        finally:
            conn.close()
            
        return migrated_count
    
    def run_migration(self) -> Dict:
        """Run the complete migration process."""
        print("🔄 Starting vaccine data migration...")
        print(f"📂 Database: {self.db_path}")
        print(f"🗺️  Comprehensive mapping loaded: {len(self.comprehensive_mapping.get('brand_names', {}))} brand names")
        print()
        
        # Get all patients with vaccine data
        patients = self.get_patients_with_vaccines()
        print(f"👥 Found {len(patients)} patients with vaccine data")
        print()
        
        # Process each patient
        for patient in patients:
            patient_id = patient['id']
            patient_name = f"{patient['first_name']} {patient['last_name']}"
            mrn = patient['mrn']
            
            print(f"Processing patient {mrn} - {patient_name}...")
            
            # Migrate standard vaccines
            standard_count = self.migrate_standard_vaccines(patient_id)
            self.migration_stats['standard_vaccines_migrated'] += standard_count
            print(f"  ✅ Standard vaccines: {standard_count}")
            
            # Migrate non-standard vaccines
            nonstandard_count = self.migrate_nonstandard_vaccines(patient_id)
            self.migration_stats['nonstandard_vaccines_migrated'] += nonstandard_count
            print(f"  ✅ Non-standard vaccines: {nonstandard_count}")
            
            self.migration_stats['patients_processed'] += 1
            print()
        
        return self.migration_stats
    
    def print_migration_report(self):
        """Print detailed migration report."""
        stats = self.migration_stats
        
        print("=" * 60)
        print("📊 MIGRATION REPORT")
        print("=" * 60)
        print(f"Patients processed: {stats['patients_processed']}")
        print(f"Standard vaccines migrated: {stats['standard_vaccines_migrated']}")
        print(f"Non-standard vaccines migrated: {stats['nonstandard_vaccines_migrated']}")
        print(f"Total vaccines migrated: {stats['standard_vaccines_migrated'] + stats['nonstandard_vaccines_migrated']}")
        print()
        
        if stats['unmapped_brands']:
            print(f"⚠️  Unmapped vaccine brands ({len(stats['unmapped_brands'])}):")
            for brand in sorted(stats['unmapped_brands']):
                print(f"   - {brand}")
            print()
        
        if stats['errors']:
            print(f"❌ Errors ({len(stats['errors'])}):")
            for error in stats['errors']:
                print(f"   - {error}")
            print()
        
        if not stats['errors'] and not stats['unmapped_brands']:
            print("✅ Migration completed successfully with no errors!")
        
        print("=" * 60)


def main():
    """Main migration execution."""
    db_path = "/Users/samimelki/Documents/UnifiedEMR/unified_emr.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    # Verify Immunizations table exists
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Immunizations'")
    if not cursor.fetchone():
        print("❌ Immunizations table not found. Please run create_immunizations_table.sql first.")
        conn.close()
        sys.exit(1)
    conn.close()
    
    # Run migration
    migrator = VaccineMigrator(db_path)
    
    try:
        migrator.run_migration()
        migrator.print_migration_report()
        
    except KeyboardInterrupt:
        print("\n🛑 Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main() 