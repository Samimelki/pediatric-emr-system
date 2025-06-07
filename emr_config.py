import os
import json
from enum import Enum
from typing import Dict, Any, Optional, List

class EMRMode(Enum):
    """EMR operating modes"""
    ADULT = "adult"
    PEDIATRIC = "pediatric" 
    MIXED = "mixed"  # Both adult and pediatric

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

# Default unified configuration
DEFAULT_CONFIG = {
    # Core EMR Settings
    'emr_mode': EMRMode.MIXED.value,
    'primary_language': 'en',  # 'en' or 'fr'
    'secondary_language': 'fr',  # Optional secondary language
    'practice_name': 'Medical Practice',
    'practice_type': 'general',  # 'pediatric', 'adult', 'family', 'general'
    
    # Feature Toggles - Pediatric Features
    'features': {
        'vaccines': {
            'enabled': True,
            'show_in_adult_mode': False,
            'show_in_pediatric_mode': True,
            'show_in_mixed_mode': True,
            'mandatory_vaccines': ['DTCP', 'MMR', 'Hepatitis B'],
            'track_non_standard': True
        },
        'growth_charts': {
            'enabled': True,
            'show_in_adult_mode': False,
            'show_in_pediatric_mode': True,
            'show_in_mixed_mode': True,
            'use_who_standards': True,
            'show_percentiles': True
        },
        'birth_info': {
            'enabled': True,
            'show_in_adult_mode': False,
            'show_in_pediatric_mode': True,
            'show_in_mixed_mode': True,
            'required_fields': ['birth_weight_g', 'birth_height_cm']
        },
        'pediatric_measurements': {
            'enabled': True,
            'show_in_adult_mode': False,
            'show_in_pediatric_mode': True,
            'show_in_mixed_mode': True,
            'weight_unit': 'grams',  # 'grams' or 'kg'
            'include_head_circumference': True
        },
        
        # Adult Features
        'adult_vitals': {
            'enabled': True,
            'show_in_adult_mode': True,
            'show_in_pediatric_mode': False,
            'show_in_mixed_mode': True,
            'include_blood_pressure': True,
            'include_heart_rate': True,
            'include_temperature': True,
            'weight_unit': 'kg'  # 'kg' or 'lbs'
        },
        'soap_notes': {
            'enabled': True,
            'show_in_adult_mode': True,
            'show_in_pediatric_mode': False,
            'show_in_mixed_mode': True,
            'structured_format': True
        },
        'social_history': {
            'enabled': True,
            'show_in_adult_mode': True,
            'show_in_pediatric_mode': False,
            'show_in_mixed_mode': True,
            'include_smoking': True,
            'include_alcohol': True
        },
        
        # Shared Features
        'statistics': {
            'enabled': True,
            'show_outliers': True,
            'background_calculation': True
        },
        'custom_demographics': {
            'enabled': True,
            'max_fields': 20
        },
        'document_management': {
            'enabled': True,
            'word_integration': True,
            'pdf_export': True
        }
    },
    
    # Visit Configuration
    'visit_config': {
        'default_fields_adult': ['vital_signs', 'chief_complaint', 'subjective', 'objective', 'assessment', 'plan'],
        'default_fields_pediatric': ['weight_g', 'height_cm', 'head_circumference_cm', 'notes'],
        'allow_custom_fields': True,
        'require_visit_notes': True
    },
    
    # Patient Form Configuration
    'patient_form': {
        'adult_required_fields': ['first_name', 'last_name', 'date_of_birth'],
        'pediatric_required_fields': ['prenom', 'nom', 'naissance_date'],
        'mixed_mode_field_mapping': {
            'use_adult_naming': True,  # If true, use English field names, otherwise French
            'show_both_languages': False
        },
        'parental_info': {
            'enabled_in_adult_mode': False,
            'enabled_in_pediatric_mode': True,
            'enabled_in_mixed_mode': True
        }
    },
    
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
        'show_mode_indicator': True,
        'quick_mode_switch': True,
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
        'footer_alignment': 'center',
        'include_vaccines_pediatric': True,
        'include_growth_charts_pediatric': True,
        'include_vitals_adult': True
    }
}

class EMRConfig:
    """Unified EMR Configuration Manager"""
    
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
            try:
                if not os.path.exists(directory):
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory: {directory}")
            except Exception as e:
                print(f"Error creating directory {directory}: {e}")
    
    def load_config(self):
        """Load configuration from file or create default"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = json.load(f)
                self.config = self.deep_merge(DEFAULT_CONFIG.copy(), loaded_config)
            except Exception as e:
                print(f"Error loading config: {e} - Using default.")
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()
        
        # Save to ensure any new defaults are persisted
        self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def deep_merge(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    # EMR Mode Management
    def get_emr_mode(self) -> EMRMode:
        """Get current EMR mode"""
        mode_str = self.config.get('emr_mode', EMRMode.MIXED.value)
        return EMRMode(mode_str)
    
    def set_emr_mode(self, mode: EMRMode):
        """Set EMR mode"""
        self.config['emr_mode'] = mode.value
        self.save_config()
    
    def is_mode_active(self, mode: EMRMode) -> bool:
        """Check if a specific mode is active or included in mixed mode"""
        current_mode = self.get_emr_mode()
        if current_mode == EMRMode.MIXED:
            return True
        return current_mode == mode
    
    # Feature Management
    def is_feature_enabled(self, feature_name: str, current_mode: Optional[EMRMode] = None) -> bool:
        """Check if a feature is enabled for the current or specified mode"""
        if current_mode is None:
            current_mode = self.get_emr_mode()
        
        feature_config = self.config.get('features', {}).get(feature_name, {})
        
        if not feature_config.get('enabled', False):
            return False
        
        mode_key = f'show_in_{current_mode.value}_mode'
        return feature_config.get(mode_key, False)
    
    def enable_feature(self, feature_name: str, enabled: bool = True):
        """Enable or disable a feature"""
        if 'features' not in self.config:
            self.config['features'] = {}
        if feature_name not in self.config['features']:
            self.config['features'][feature_name] = {}
        
        self.config['features'][feature_name]['enabled'] = enabled
        self.save_config()
    
    def get_feature_config(self, feature_name: str) -> Dict[str, Any]:
        """Get configuration for a specific feature"""
        return self.config.get('features', {}).get(feature_name, {})
    
    def get_enabled_features(self):
        """Get a structured object of enabled features for easy template access"""
        from collections import namedtuple
        
        Features = namedtuple('Features', [
            'vaccines_enabled',
            'growth_charts_enabled', 
            'vitals_tracking_enabled',
            'document_management_enabled',
            'statistics_reports_enabled',
            'custom_fields_enabled',
            'multi_language_support',
            'simplified_interface'
        ])
        
        return Features(
            vaccines_enabled=self.should_show_vaccines(),
            growth_charts_enabled=self.should_show_growth_charts(),
            vitals_tracking_enabled=self.should_show_adult_vitals(),
            document_management_enabled=self.is_feature_enabled('document_management'),
            statistics_reports_enabled=self.is_feature_enabled('statistics_reports'),
            custom_fields_enabled=self.is_feature_enabled('custom_fields'),
            multi_language_support=self.is_feature_enabled('multi_language'),
            simplified_interface=self.is_feature_enabled('simplified_interface')
        )
    
    def update_features(self, features_data: Dict[str, bool]):
        """Update multiple features at once"""
        if 'features' not in self.config:
            self.config['features'] = {}
            
        # Map simplified names to our feature config structure
        feature_mapping = {
            'vaccines_enabled': 'vaccines',
            'growth_charts_enabled': 'growth_charts',
            'vitals_tracking_enabled': 'adult_vitals',
            'document_management_enabled': 'document_management',
            'statistics_reports_enabled': 'statistics_reports',
            'custom_fields_enabled': 'custom_fields',
            'multi_language_support': 'multi_language',
            'simplified_interface': 'simplified_interface'
        }
        
        for simple_name, enabled in features_data.items():
            feature_name = feature_mapping.get(simple_name, simple_name)
            if feature_name not in self.config['features']:
                self.config['features'][feature_name] = {}
            self.config['features'][feature_name]['enabled'] = enabled
        
        self.save_config()
    
    # Visit Configuration
    def get_visit_fields(self, mode: Optional[EMRMode] = None) -> List[str]:
        """Get appropriate visit fields for the current mode"""
        if mode is None:
            mode = self.get_emr_mode()
        
        visit_config = self.config.get('visit_config', {})
        
        if mode == EMRMode.ADULT:
            return visit_config.get('default_fields_adult', [])
        elif mode == EMRMode.PEDIATRIC:
            return visit_config.get('default_fields_pediatric', [])
        else:  # MIXED mode
            adult_fields = visit_config.get('default_fields_adult', [])
            pediatric_fields = visit_config.get('default_fields_pediatric', [])
            return adult_fields + pediatric_fields
    
    def get_patient_required_fields(self, mode: Optional[EMRMode] = None) -> List[str]:
        """Get required patient fields for the current mode"""
        if mode is None:
            mode = self.get_emr_mode()
        
        patient_config = self.config.get('patient_form', {})
        
        if mode == EMRMode.ADULT:
            return patient_config.get('adult_required_fields', [])
        elif mode == EMRMode.PEDIATRIC:
            return patient_config.get('pediatric_required_fields', [])
        else:  # MIXED mode
            # In mixed mode, use the mapping preference
            mapping_config = patient_config.get('mixed_mode_field_mapping', {})
            if mapping_config.get('use_adult_naming', True):
                return patient_config.get('adult_required_fields', [])
            else:
                return patient_config.get('pediatric_required_fields', [])
    
    # Convenience methods
    def should_show_vaccines(self) -> bool:
        """Check if vaccines should be shown in current mode"""
        return self.is_feature_enabled('vaccines')
    
    def should_show_growth_charts(self) -> bool:
        """Check if growth charts should be shown in current mode"""
        return self.is_feature_enabled('growth_charts')
    
    def should_show_adult_vitals(self) -> bool:
        """Check if adult vital signs should be shown in current mode"""
        return self.is_feature_enabled('adult_vitals')
    
    def should_show_pediatric_measurements(self) -> bool:
        """Check if pediatric measurements should be shown in current mode"""
        return self.is_feature_enabled('pediatric_measurements')
    
    def get_weight_unit(self, context: str = 'adult') -> str:
        """Get appropriate weight unit based on context"""
        if context == 'pediatric' and self.should_show_pediatric_measurements():
            return self.get_feature_config('pediatric_measurements').get('weight_unit', 'grams')
        elif context == 'adult' and self.should_show_adult_vitals():
            return self.get_feature_config('adult_vitals').get('weight_unit', 'kg')
        else:
            # Default based on mode
            mode = self.get_emr_mode()
            if mode == EMRMode.PEDIATRIC:
                return 'grams'
            else:
                return 'kg'
    
    # Configuration getters
    def get_database_path(self) -> str:
        """Get database path"""
        return self.config.get('database_path', DEFAULT_DATABASE_PATH)
    
    def get_upload_folder(self) -> str:
        """Get upload folder path"""
        return UPLOAD_FOLDER
    
    def get_user_media_folder(self) -> str:
        """Get user media folder path"""
        return USER_MEDIA_FOLDER
    
    def get_word_docs_folder(self) -> str:
        """Get Word documents folder path"""
        return self.config.get('word_docs_folder', WORD_DOCS_FOLDER)
    
    def get_pdf_settings(self) -> Dict[str, Any]:
        """Get PDF export settings"""
        return self.config.get('pdf_settings', {})
    
    def get_practice_info(self) -> Dict[str, str]:
        """Get practice information"""
        return {
            'name': self.config.get('practice_name', 'Medical Practice'),
            'type': self.config.get('practice_type', 'general'),
            'primary_language': self.config.get('primary_language', 'en'),
            'secondary_language': self.config.get('secondary_language', 'fr')
        }
    
    # Language Configuration
    def get_primary_language(self) -> str:
        """Get primary language (en or fr)"""
        return self.config.get('primary_language', 'en')
    
    def set_primary_language(self, language: str):
        """Set primary language"""
        if language in ['en', 'fr']:
            self.config['primary_language'] = language
            self.save_config()
    
    def is_french_primary(self) -> bool:
        """Check if French is the primary language"""
        return self.get_primary_language() == 'fr'
    
    def is_english_primary(self) -> bool:
        """Check if English is the primary language"""
        return self.get_primary_language() == 'en'

# Global configuration instance
emr_config = EMRConfig()

# Convenience functions for backward compatibility
def load_config():
    """Load configuration (backward compatibility)"""
    return emr_config.config

def save_config(config):
    """Save configuration (backward compatibility)"""
    emr_config.config = config
    return emr_config.save_config()

# Configuration constants for easy access
APP_DATA_DIR = emr_config.get_user_media_folder().replace('/user_media', '')
UPLOAD_FOLDER = emr_config.get_upload_folder()
USER_MEDIA_FOLDER = emr_config.get_user_media_folder()
WORD_DOCS_FOLDER = emr_config.get_word_docs_folder() 