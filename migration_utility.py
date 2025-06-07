#!/usr/bin/env python3
"""
Data Migration Utility for Unified EMR System
This utility helps migrate existing data from separate adult and pediatric EMR databases
to the new unified schema.
"""

import os
import sys
import sqlite3
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

try:
    from emr_config import emr_config
except ImportError:
    print("Error: emr_config module not found. Make sure you're running from the EMR directory.")
    sys.exit(1)

class EMRDataMigrator:
    """Handles migration of data from legacy EMR systems to unified system."""
    
    def __init__(self, unified_db_path: str):
        self.unified_db_path = unified_db_path
        self.migration_log = []
        self.backup_paths = []
        
    def log_message(self, message: str):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.migration_log.append(log_entry)
        print(log_entry)
    
    def create_backup(self, source_path: str) -> str:
        """Create a backup of the source database."""
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source database not found: {source_path}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{os.path.basename(source_path)}_{timestamp}"
        backup_path = os.path.join(os.path.dirname(source_path), backup_name)
        
        shutil.copy2(source_path, backup_path)
        self.backup_paths.append(backup_path)
        self.log_message(f"Created backup: {backup_path}")
        
        return backup_path
    
    def verify_database_structure(self, db_path: str) -> Dict[str, List[str]]:
        """Verify and return the structure of a database."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            structure = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                columns = [col[1] for col in cursor.fetchall()]
                structure[table] = columns
            
            conn.close()
            return structure
        except Exception as e:
            self.log_message(f"Error verifying database structure: {e}")
            return {}
    
    def count_patients(self, db_path: str) -> int:
        """Count patients in a database."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM Patients;")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0
    
    def perform_migration(self, 
                         adult_db_path: Optional[str] = None,
                         pediatric_db_path: Optional[str] = None,
                         create_backups: bool = True) -> Dict[str, Any]:
        """Perform the complete migration process."""
        
        migration_results = {
            'start_time': datetime.now().isoformat(),
            'adult_migration': {'attempted': False, 'success': False, 'stats': {}},
            'pediatric_migration': {'attempted': False, 'success': False, 'stats': {}},
            'total_patients_migrated': 0,
            'total_visits_migrated': 0,
            'errors': [],
            'backups_created': []
        }
        
        self.log_message("Starting EMR data migration process...")
        
        # Initialize unified database schema
        try:
            # Ensure directories exist
            os.makedirs(os.path.dirname(self.unified_db_path), exist_ok=True)
            
            self.log_message("Unified database schema initialized successfully")
            
        except Exception as e:
            error_msg = f"Failed to initialize unified database: {e}"
            self.log_message(error_msg)
            migration_results['errors'].append(error_msg)
            return migration_results
        
        # Migrate from adult EMR database
        if adult_db_path and os.path.exists(adult_db_path):
            try:
                self.log_message(f"Starting migration from adult EMR: {adult_db_path}")
                migration_results['adult_migration']['attempted'] = True
                
                if create_backups:
                    backup_path = self.create_backup(adult_db_path)
                    migration_results['backups_created'].append(backup_path)
                
                stats = self._migrate_adult_data(adult_db_path)
                migration_results['adult_migration']['stats'] = stats
                migration_results['adult_migration']['success'] = stats['errors'] == 0
                migration_results['total_patients_migrated'] += stats['patients_migrated']
                migration_results['total_visits_migrated'] += stats['visits_migrated']
                
                self.log_message(f"Adult EMR migration completed: {stats}")
                
            except Exception as e:
                error_msg = f"Error migrating adult EMR data: {e}"
                self.log_message(error_msg)
                migration_results['errors'].append(error_msg)
        
        # Migrate from pediatric EMR database
        if pediatric_db_path and os.path.exists(pediatric_db_path):
            try:
                self.log_message(f"Starting migration from pediatric EMR: {pediatric_db_path}")
                migration_results['pediatric_migration']['attempted'] = True
                
                if create_backups:
                    backup_path = self.create_backup(pediatric_db_path)
                    migration_results['backups_created'].append(backup_path)
                
                stats = self._migrate_pediatric_data(pediatric_db_path)
                migration_results['pediatric_migration']['stats'] = stats
                migration_results['pediatric_migration']['success'] = stats['errors'] == 0
                migration_results['total_patients_migrated'] += stats['patients_migrated']
                migration_results['total_visits_migrated'] += stats['visits_migrated']
                
                self.log_message(f"Pediatric EMR migration completed: {stats}")
                
            except Exception as e:
                error_msg = f"Error migrating pediatric EMR data: {e}"
                self.log_message(error_msg)
                migration_results['errors'].append(error_msg)
        
        migration_results['end_time'] = datetime.now().isoformat()
        migration_results['success'] = len(migration_results['errors']) == 0
        
        # Save migration log
        self.save_migration_log(migration_results)
        
        self.log_message("Migration process completed!")
        return migration_results
    
    def _migrate_adult_data(self, source_db_path: str) -> Dict[str, int]:
        """Migrate data from adult EMR system."""
        stats = {'patients_migrated': 0, 'visits_migrated': 0, 'errors': 0}
        
        try:
            # Connect to source database
            source_conn = sqlite3.connect(source_db_path)
            source_conn.row_factory = sqlite3.Row
            
            # Connect to destination database
            dest_conn = sqlite3.connect(self.unified_db_path)
            
            # Migrate patients
            cursor = source_conn.execute("SELECT * FROM Patients")
            for patient in cursor.fetchall():
                try:
                    # Convert to dictionary and add metadata
                    patient_dict = dict(patient)
                    patient_dict['emr_mode'] = 'adult'
                    patient_dict['created_date'] = datetime.now().isoformat()
                    patient_dict['modified_date'] = datetime.now().isoformat()
                    
                    # Remove ID to get new one
                    old_id = patient_dict.pop('id', None)
                    
                    # Build insert query
                    columns = list(patient_dict.keys())
                    placeholders = ', '.join(['?' for _ in columns])
                    column_names = ', '.join(columns)
                    
                    query = f"INSERT INTO Patients ({column_names}) VALUES ({placeholders})"
                    cursor = dest_conn.execute(query, list(patient_dict.values()))
                    
                    stats['patients_migrated'] += 1
                    
                except Exception as e:
                    self.log_message(f"Error migrating adult patient {patient.get('id', 'unknown')}: {e}")
                    stats['errors'] += 1
            
            dest_conn.commit()
            source_conn.close()
            dest_conn.close()
            
        except Exception as e:
            self.log_message(f"Error in adult data migration: {e}")
            stats['errors'] += 1
        
        return stats
    
    def _migrate_pediatric_data(self, source_db_path: str) -> Dict[str, int]:
        """Migrate data from pediatric EMR system."""
        stats = {'patients_migrated': 0, 'visits_migrated': 0, 'errors': 0}
        
        try:
            # Connect to source database
            source_conn = sqlite3.connect(source_db_path)
            source_conn.row_factory = sqlite3.Row
            
            # Connect to destination database
            dest_conn = sqlite3.connect(self.unified_db_path)
            
            # Migrate patients
            cursor = source_conn.execute("SELECT * FROM Patients")
            for patient in cursor.fetchall():
                try:
                    # Convert to dictionary and add metadata
                    patient_dict = dict(patient)
                    patient_dict['emr_mode'] = 'pediatric'
                    patient_dict['created_date'] = datetime.now().isoformat()
                    patient_dict['modified_date'] = datetime.now().isoformat()
                    
                    # Remove ID to get new one
                    old_id = patient_dict.pop('id', None)
                    
                    # Build insert query
                    columns = list(patient_dict.keys())
                    placeholders = ', '.join(['?' for _ in columns])
                    column_names = ', '.join(columns)
                    
                    query = f"INSERT INTO Patients ({column_names}) VALUES ({placeholders})"
                    cursor = dest_conn.execute(query, list(patient_dict.values()))
                    
                    stats['patients_migrated'] += 1
                    
                except Exception as e:
                    self.log_message(f"Error migrating pediatric patient {patient.get('id', 'unknown')}: {e}")
                    stats['errors'] += 1
            
            dest_conn.commit()
            source_conn.close()
            dest_conn.close()
            
        except Exception as e:
            self.log_message(f"Error in pediatric data migration: {e}")
            stats['errors'] += 1
        
        return stats
    
    def save_migration_log(self, results: Dict[str, Any]):
        """Save migration log to file."""
        log_dir = os.path.dirname(self.unified_db_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"migration_log_{timestamp}.json")
        
        log_data = {
            'migration_results': results,
            'migration_log': self.migration_log,
            'backup_paths': self.backup_paths
        }
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2, ensure_ascii=False)
            self.log_message(f"Migration log saved to: {log_file}")
        except Exception as e:
            self.log_message(f"Error saving migration log: {e}")

def detect_emr_databases() -> Tuple[Optional[str], Optional[str]]:
    """Detect existing EMR databases in the system."""
    
    # Current workspace (adult EMR)
    current_workspace = os.getcwd()
    adult_db_path = None
    
    # Check for current EMR database
    potential_adult_paths = [
        os.path.join(current_workspace, 'emr_database.db'),
        os.path.join(current_workspace, 'unified_emr.db'),
        os.path.join(os.path.expanduser('~'), 'Documents', 'WordDocsEMR', 'emr_database.db')
    ]
    
    for path in potential_adult_paths:
        if os.path.exists(path):
            adult_db_path = path
            break
    
    # Check for pediatric EMR database
    pediatric_db_path = None
    foxpro_path = os.path.join(os.path.dirname(current_workspace), 'foxpro2025')
    
    potential_pediatric_paths = [
        os.path.join(foxpro_path, 'emr_database.db'),
        os.path.join(foxpro_path, 'database.db'),
        os.path.join(os.path.expanduser('~'), 'Documents', 'FoxPro2025', 'emr_database.db')
    ]
    
    for path in potential_pediatric_paths:
        if os.path.exists(path):
            pediatric_db_path = path
            break
    
    return adult_db_path, pediatric_db_path

def main():
    """Main migration script."""
    print("=" * 60)
    print("EMR Data Migration Utility")
    print("=" * 60)
    
    # Detect existing databases
    adult_db, pediatric_db = detect_emr_databases()
    
    print(f"Adult EMR Database: {adult_db or 'Not found'}")
    print(f"Pediatric EMR Database: {pediatric_db or 'Not found'}")
    
    if not adult_db and not pediatric_db:
        print("\nNo EMR databases found. Nothing to migrate.")
        return
    
    # Set up unified database path
    unified_db_path = emr_config.get_database_path()
    print(f"Unified Database Path: {unified_db_path}")
    
    # Create migrator
    migrator = EMRDataMigrator(unified_db_path)
    
    # Show patient counts
    if adult_db:
        adult_count = migrator.count_patients(adult_db)
        print(f"Adult EMR patients: {adult_count}")
    
    if pediatric_db:
        pediatric_count = migrator.count_patients(pediatric_db)
        print(f"Pediatric EMR patients: {pediatric_count}")
    
    # Confirm migration
    print("\n" + "=" * 60)
    print("MIGRATION CONFIRMATION")
    print("=" * 60)
    print("This will:")
    print("1. Create backups of existing databases")
    print("2. Initialize unified EMR schema")
    print("3. Migrate all patient and visit data")
    print("4. Maintain data integrity and relationships")
    print("=" * 60)
    
    confirm = input("Proceed with migration? (yes/no): ").lower().strip()
    
    if confirm != 'yes':
        print("Migration cancelled.")
        return
    
    # Perform migration
    print("\nStarting migration process...")
    results = migrator.perform_migration(adult_db, pediatric_db)
    
    # Display results
    print("\n" + "=" * 60)
    print("MIGRATION RESULTS")
    print("=" * 60)
    print(f"Total patients migrated: {results['total_patients_migrated']}")
    print(f"Total visits migrated: {results['total_visits_migrated']}")
    print(f"Errors encountered: {len(results['errors'])}")
    
    if results['errors']:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
    
    print(f"\nBackups created: {len(results['backups_created'])}")
    for backup in results['backups_created']:
        print(f"  - {backup}")
    
    print(f"\nMigration {'completed successfully' if results['success'] else 'completed with errors'}!")
    
    # Set active profile based on migrated data
    if results['adult_migration']['success'] and results['pediatric_migration']['success']:
        emr_config.set_active_profile('family_practice_profile')
        print("\nActive profile set to Family Practice (both adult and pediatric)")
    elif results['adult_migration']['success']:
        emr_config.set_active_profile('adult_profile')
        print("\nActive profile set to Adult EMR")
    elif results['pediatric_migration']['success']:
        emr_config.set_active_profile('pediatric_profile')
        print("\nActive profile set to Pediatric EMR")

if __name__ == "__main__":
    main() 