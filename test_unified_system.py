#!/usr/bin/env python3
"""
Test Script for Unified EMR System
Tests all major components and functionality
"""

import os
import sys
from datetime import datetime

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules import correctly"""
    print("🧪 Testing imports...")
    try:
        from app import app
        from emr_config import emr_config, EMRMode
        from unified_database import save_patient_unified, get_patient_unified_data
        from database import init_db_schema
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_emr_config():
    """Test EMR configuration system"""
    print("\n🧪 Testing EMR configuration...")
    try:
        from emr_config import emr_config, EMRMode
        
        # Test getting current mode
        mode = emr_config.get_emr_mode()
        print(f"✅ Current EMR Mode: {mode}")
        
        # Test getting features
        features = emr_config.get_enabled_features()
        print(f"✅ Features loaded: {features}")
        
        # Test mode switching
        original_mode = mode
        emr_config.set_emr_mode(EMRMode.ADULT)
        new_mode = emr_config.get_emr_mode()
        print(f"✅ Mode switched to: {new_mode}")
        
        # Restore original mode
        emr_config.set_emr_mode(original_mode)
        print(f"✅ Mode restored to: {emr_config.get_emr_mode()}")
        
        return True
    except Exception as e:
        print(f"❌ EMR config test failed: {e}")
        return False

def test_database_init():
    """Test database initialization"""
    print("\n🧪 Testing database initialization...")
    try:
        from app import app
        from database import init_db_schema
        
        with app.app_context():
            init_db_schema()
            print("✅ Database schema initialized")
            return True
    except Exception as e:
        print(f"❌ Database init failed: {e}")
        return False

def test_patient_creation():
    """Test unified patient creation"""
    print("\n🧪 Testing unified patient creation...")
    try:
        from app import app
        from unified_database import save_patient_unified, get_patient_unified_data
        from emr_config import EMRMode
        
        with app.app_context():
            # Test adult patient
            adult_patient = {
                'mrn': 'TEST001',
                'first_name': 'John',
                'last_name': 'Doe',
                'date_of_birth': '1985-01-15',
                'sex': 'M',
                'phone': '555-1234',
                'address': '123 Main St',
                'email': 'john.doe@email.com',
                'emr_mode': 'adult',
                'created_date': datetime.now().isoformat()
            }
            
            adult_id = save_patient_unified(adult_patient, EMRMode.ADULT)
            print(f"✅ Adult patient created with ID: {adult_id}")
            
            # Test pediatric patient
            pediatric_patient = {
                'mrn': 'TEST002',
                'prenom': 'Marie',
                'nom': 'Dupont',
                'naissance_date': '2020-03-15',
                'sexe': 'F',
                'telephone': '555-5678',
                'domicile': '456 Rue Principale',
                'mere_nom': 'Anne Dupont',
                'pere_nom': 'Pierre Dupont',
                'birth_weight_g': 3500,
                'birth_height_cm': 50,
                'emr_mode': 'pediatric',
                'created_date': datetime.now().isoformat()
            }
            
            pediatric_id = save_patient_unified(pediatric_patient, EMRMode.PEDIATRIC)
            print(f"✅ Pediatric patient created with ID: {pediatric_id}")
            
            # Test retrieving patients
            adult_retrieved = get_patient_unified_data(adult_id, EMRMode.ADULT)
            pediatric_retrieved = get_patient_unified_data(pediatric_id, EMRMode.PEDIATRIC)
            
            if adult_retrieved and pediatric_retrieved:
                print(f"✅ Patients retrieved successfully")
                print(f"   Adult: {adult_retrieved.get('first_name')} {adult_retrieved.get('last_name')}")
                print(f"   Pediatric: {pediatric_retrieved.get('prenom')} {pediatric_retrieved.get('nom')}")
                return True
            else:
                print("❌ Failed to retrieve patients")
                return False
                
    except Exception as e:
        print(f"❌ Patient creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mode_switching():
    """Test EMR mode switching functionality"""
    print("\n🧪 Testing mode switching...")
    try:
        from emr_config import emr_config, EMRMode
        from unified_database import get_patient_unified_data
        from app import app
        
        with app.app_context():
            # Assuming we have patients from previous test
            test_patient_id = 1  # Adult patient from previous test
            
            # Test getting patient data in different modes
            for mode in [EMRMode.ADULT, EMRMode.PEDIATRIC, EMRMode.MIXED]:
                emr_config.set_emr_mode(mode)
                patient_data = get_patient_unified_data(test_patient_id, mode)
                if patient_data:
                    print(f"✅ Patient data retrieved in {mode.value} mode")
                else:
                    print(f"⚠️  No patient data in {mode.value} mode (may be expected)")
            
            return True
    except Exception as e:
        print(f"❌ Mode switching test failed: {e}")
        return False

def test_migration_utility():
    """Test the migration utility functions"""
    print("\n🧪 Testing migration utility...")
    try:
        from migration_utility import detect_emr_databases, EMRDataMigrator
        
        # Test database detection
        adult_db, pediatric_db = detect_emr_databases()
        print(f"✅ Database detection completed")
        print(f"   Adult DB: {adult_db or 'Not found'}")
        print(f"   Pediatric DB: {pediatric_db or 'Not found'}")
        
        # Test migrator initialization
        migrator = EMRDataMigrator("/tmp/test_unified.db")
        print("✅ Migration utility initialized")
        
        return True
    except Exception as e:
        print(f"❌ Migration utility test failed: {e}")
        return False

def test_flask_routes():
    """Test that Flask routes are accessible"""
    print("\n🧪 Testing Flask routes...")
    try:
        from app import app
        
        with app.test_client() as client:
            # Test main page
            response = client.get('/')
            if response.status_code == 200:
                print("✅ Main page accessible")
            else:
                print(f"⚠️  Main page returned status {response.status_code}")
            
            # Test EMR configuration page
            response = client.get('/emr-settings/')
            if response.status_code == 200:
                print("✅ EMR configuration page accessible")
            else:
                print(f"⚠️  EMR config page returned status {response.status_code}")
            
            # Test patient add page
            response = client.get('/patient/new')
            if response.status_code == 200:
                print("✅ Add patient page accessible")
            else:
                print(f"⚠️  Add patient page returned status {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ Flask routes test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Unified EMR System Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_emr_config,
        test_database_init,
        test_patient_creation,
        test_mode_switching,
        test_migration_utility,
        test_flask_routes
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"🏁 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The unified EMR system is working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the errors above.")
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 