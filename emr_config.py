import os
import json
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime

class FieldType(Enum):
    """Supported field types for dynamic forms"""
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    TEXTAREA = "textarea"
    CHECKBOX = "checkbox"

# Define application name and paths
APP_NAME = "UnifiedEMR"
USER_DOCUMENTS = os.path.join(os.path.expanduser('~'), 'Documents')
APP_DATA_DIR = os.path.join(USER_DOCUMENTS, APP_NAME)
DATABASE_NAME = 'unified_emr.db'
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'emr_config.json')
DEFAULT_DATABASE_PATH = os.path.join(APP_DATA_DIR, DATABASE_NAME)
UPLOAD_FOLDER = os.path.join(APP_DATA_DIR, 'uploads')
USER_MEDIA_FOLDER = os.path.join(APP_DATA_DIR, 'user_media')
WORD_DOCS_FOLDER = os.path.join(APP_DATA_DIR, 'word_documents')

# Available EMR Features
AVAILABLE_FEATURES = {
    'birth_measurements': {
        'name': 'Birth Measurements',
        'description': 'Show birth weight, height, and head circumference',
        'category': 'Pediatric'
    },
    'growth_charts': {
        'name': 'Growth Charts',
        'description': 'WHO growth charts with percentile calculations',
        'category': 'Pediatric'
    },
    'vaccines': {
        'name': 'Vaccination Tracking',
        'description': 'Track standard and non-standard vaccines',
        'category': 'Pediatric'
    },
    'head_circumference': {
        'name': 'Head Circumference',
        'description': 'Track head circumference measurements',
        'category': 'Pediatric'
    },
    'blood_pressure': {
        'name': 'Blood Pressure',
        'description': 'Track systolic and diastolic blood pressure',
        'category': 'Adult'
    },
    'heart_rate': {
        'name': 'Heart Rate',
        'description': 'Track heart rate measurements',
        'category': 'General'
    },
    'temperature': {
        'name': 'Temperature',
        'description': 'Track body temperature',
        'category': 'General'
    },
    'weight_tracking': {
        'name': 'Weight Tracking',
        'description': 'Smart weight tracking (kg/g conversion)',
        'category': 'General'
    },
    'height_tracking': {
        'name': 'Height Tracking',
        'description': 'Height measurements in centimeters',
        'category': 'General'
    },
    'visit_notes': {
        'name': 'Visit Notes',
        'description': 'Free-form visit notes and observations',
        'category': 'General'
    },
    'statistics_dashboard': {
        'name': 'Statistics Dashboard',
        'description': 'Patient statistics and data analysis',
        'category': 'General'
    },
    'document_export': {
        'name': 'Document Export',
        'description': 'Export patient data to PDF/Word documents',
        'category': 'General'
    },
    'parental_info': {
        'name': 'Parental Information',
        'description': 'Track parent/guardian information',
        'category': 'Pediatric'
    }
}

# Default EMR Profiles
DEFAULT_PROFILES = {
    'pediatric_profile': {
        'name': 'Pediatrics EMR',
        'description': 'Complete pediatric practice configuration',
        'features': {
            'birth_measurements': True,
            'growth_charts': True,
            'vaccines': True,
            'head_circumference': True,
            'blood_pressure': False,
            'heart_rate': True,
            'temperature': True,
            'weight_tracking': True,
            'height_tracking': True,
            'visit_notes': True,
            'statistics_dashboard': True,
            'document_export': True,
            'parental_info': True
        },
        'settings': {
            'weight_unit_preference': 'grams',
            'language': 'fr',
            'show_percentiles': True,
            'require_visit_notes': True
        }
    },
    'adult_profile': {
        'name': 'Adult Medicine EMR',
        'description': 'Adult medicine practice configuration',
        'features': {
            'birth_measurements': False,
            'growth_charts': False,
            'vaccines': False,
            'head_circumference': False,
            'blood_pressure': True,
            'heart_rate': True,
            'temperature': True,
            'weight_tracking': True,
            'height_tracking': True,
            'visit_notes': True,
            'statistics_dashboard': True,
            'document_export': True,
            'parental_info': False
        },
        'settings': {
            'weight_unit_preference': 'kg',
            'language': 'en',
            'show_percentiles': False,
            'require_visit_notes': True
        }
    },
    'family_practice_profile': {
        'name': 'Family Practice EMR',
        'description': 'Family medicine with pediatric and adult features',
        'features': {
            'birth_measurements': True,
            'growth_charts': True,
            'vaccines': True,
            'head_circumference': True,
            'blood_pressure': True,
            'heart_rate': True,
            'temperature': True,
            'weight_tracking': True,
            'height_tracking': True,
            'visit_notes': True,
            'statistics_dashboard': True,
            'document_export': True,
            'parental_info': True
        },
        'settings': {
            'weight_unit_preference': 'auto',
            'language': 'en',
            'show_percentiles': True,
            'require_visit_notes': True
        }
    }
}

# Default unified configuration
DEFAULT_CONFIG = {
    # Core EMR Settings
    'active_profile': 'family_practice_profile',
    'profiles': DEFAULT_PROFILES.copy(),
    'primary_language': 'en',  # 'en' or 'fr'
    'practice_name': 'Medical Practice',
    
    # Database and Storage
    'database_path': DEFAULT_DATABASE_PATH,
    'storage_type': 'local',
    'cloud_path': None,
    'word_docs_folder': WORD_DOCS_FOLDER,
    'auto_backup': True,
    'backup_frequency': 'daily',  # 'daily', 'weekly', 'monthly'
    
    # UI/UX Configuration
    'ui': {
        'theme': 'default',
        'show_profile_indicator': True,
        'quick_profile_switch': True,
        'field_grouping': True,
        'compact_forms': False
    },
    
    # PDF Export Configuration
    'pdf_settings': {
        'physician_details_fr': {
            'name': 'Dr. Votre Nom',
            'specialty': 'Votre Spécialité',
            'hospital_name': 'Nom de l\'Hôpital/Clinique',
            'faculty_name': 'Nom de la Faculté/Université',
            'contact_line1': 'Ligne de contact 1',
            'contact_line2': 'Ligne de contact 2'
        },
        'physician_details_en': {
            'name': 'Dr. Your Name',
            'specialty': 'Your Specialty',
            'hospital_name': 'Hospital/Clinic Name',
            'faculty_name': 'Faculty/University Name',
            'contact_line1': 'Contact Line 1',
            'contact_line2': 'Contact Line 2'
        },
        'footer_note_fr': 'Note de bas de page',
        'footer_note_en': 'Footer note',
        'signature_image_filename': None,
        'report_title_fr': 'Rapport Médical Complet',
        'report_title_en': 'Complete Medical Report',
        'logo_image_filename': None,
        'footer_alignment': 'center'
    }
}

class EMRConfig:
    """Profile-based EMR Configuration Manager"""
    
    def __init__(self):
        self.config = {}
        self.ensure_directories_exist()
        self.load_config()
    
    def ensure_directories_exist(self):
        """Ensure all necessary directories exist"""
        directories_to_create = [
            APP_DATA_DIR,
            UPLOAD_FOLDER,
            USER_MEDIA_FOLDER,
            WORD_DOCS_FOLDER
        ]
        
        for directory in directories_to_create:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory: {directory}")
                except OSError as e:
                    print(f"Error creating directory {directory}: {e}")

    def load_config(self):
        """Load configuration from file or create default"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    stored_config = json.load(f)
                # Merge with defaults to ensure new features are included
                self.config = self.deep_merge(DEFAULT_CONFIG.copy(), stored_config)
            else:
                self.config = DEFAULT_CONFIG.copy()
                self.save_config()
                print(f"Created default configuration at {CONFIG_FILE}")
        except (json.JSONDecodeError, FileNotFoundError) as e:
            print(f"Error loading config file: {e}")
            self.config = DEFAULT_CONFIG.copy()
            self.save_config()

    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def deep_merge(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    # Profile Management Methods
    def get_active_profile_name(self) -> str:
        """Get the name of the currently active profile"""
        return self.config.get('active_profile', 'family_practice_profile')

    def get_active_profile(self) -> Dict[str, Any]:
        """Get the currently active profile configuration"""
        profile_name = self.get_active_profile_name()
        return self.config.get('profiles', {}).get(profile_name, DEFAULT_PROFILES['family_practice_profile'])

    def set_active_profile(self, profile_name: str):
        """Set the active profile"""
        if profile_name in self.config.get('profiles', {}):
            self.config['active_profile'] = profile_name
            self.save_config()
            return True
        return False

    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get all available profiles"""
        return self.config.get('profiles', {})

    def create_profile(self, profile_name: str, profile_data: Dict[str, Any]) -> bool:
        """Create a new profile"""
        if 'profiles' not in self.config:
            self.config['profiles'] = {}
        
        # Add metadata
        profile_data['created_date'] = datetime.now().isoformat()
        profile_data['last_modified'] = datetime.now().isoformat()
        
        self.config['profiles'][profile_name] = profile_data
        self.save_config()
        return True

    def update_profile(self, profile_name: str, profile_data: Dict[str, Any]) -> bool:
        """Update an existing profile"""
        if profile_name in self.config.get('profiles', {}):
            profile_data['last_modified'] = datetime.now().isoformat()
            self.config['profiles'][profile_name].update(profile_data)
            self.save_config()
            return True
        return False

    def delete_profile(self, profile_name: str) -> bool:
        """Delete a profile (cannot delete default profiles)"""
        if profile_name in DEFAULT_PROFILES:
            return False  # Cannot delete default profiles
        
        if profile_name in self.config.get('profiles', {}):
            del self.config['profiles'][profile_name]
            
            # If this was the active profile, switch to family practice
            if self.get_active_profile_name() == profile_name:
                self.set_active_profile('family_practice_profile')
            
            self.save_config()
            return True
        return False

    # Feature Management Methods  
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled in the current profile"""
        active_profile = self.get_active_profile()
        return active_profile.get('features', {}).get(feature_name, False)

    def get_enabled_features(self) -> List[str]:
        """Get list of enabled features in current profile"""
        active_profile = self.get_active_profile()
        features = active_profile.get('features', {})
        return [feature for feature, enabled in features.items() if enabled]

    def get_feature_categories(self) -> Dict[str, List[str]]:
        """Get features grouped by category"""
        categories = {}
        for feature_key, feature_info in AVAILABLE_FEATURES.items():
            category = feature_info['category']
            if category not in categories:
                categories[category] = []
            categories[category].append(feature_key)
        return categories

    # Legacy compatibility methods (for backward compatibility during transition)
    def get_emr_mode(self):
        """Legacy method - determines mode based on active profile features"""
        profile = self.get_active_profile()
        features = profile.get('features', {})
        
        # Determine mode based on feature combinations
        has_pediatric = (features.get('birth_measurements', False) or 
                        features.get('growth_charts', False) or 
                        features.get('vaccines', False))
        has_adult = features.get('blood_pressure', False)
        
        if has_pediatric and has_adult:
            return type('EMRMode', (), {'value': 'mixed', 'MIXED': 'mixed'})()
        elif has_pediatric:
            return type('EMRMode', (), {'value': 'pediatric', 'PEDIATRIC': 'pediatric'})()
        else:
            return type('EMRMode', (), {'value': 'adult', 'ADULT': 'adult'})()

    # Utility Methods
    def get_database_path(self) -> str:
        return self.config.get('database_path', DEFAULT_DATABASE_PATH)

    def get_upload_folder(self) -> str:
        return UPLOAD_FOLDER

    def get_user_media_folder(self) -> str:
        return USER_MEDIA_FOLDER

    def get_word_docs_folder(self) -> str:
        return self.config.get('word_docs_folder', WORD_DOCS_FOLDER)

    def get_pdf_settings(self) -> Dict[str, Any]:
        return self.config.get('pdf_settings', {})

    def get_practice_info(self) -> Dict[str, str]:
        return {
            'name': self.config.get('practice_name', 'Medical Practice'),
            'language': self.config.get('primary_language', 'en')
        }

    def get_primary_language(self) -> str:
        return self.config.get('primary_language', 'en')

    def set_primary_language(self, language: str):
        if language in ['en', 'fr']:
            self.config['primary_language'] = language
            self.save_config()

    def is_french_primary(self) -> bool:
        return self.get_primary_language() == 'fr'

    def is_english_primary(self) -> bool:
        return self.get_primary_language() == 'en'

# Global configuration instance
emr_config = EMRConfig()

# Utility functions for backward compatibility
def load_config():
    return emr_config.config

def save_config(config):
    emr_config.config = config
    emr_config.save_config() 