#!/usr/bin/env python3
"""
Immunization Configuration Service

Manages loading and accessing immunization-related configuration files:
- Comprehensive vaccine mapping (protected from interface modifications)
- Uses unified vaccine schedule config from main system
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from functools import lru_cache
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from emr_config import emr_config

class ImmunizationConfigService:
    """Service for managing immunization configuration files"""
    
    def __init__(self, base_path: str = "immunization_logic/config"):
        self.base_path = base_path
        self.comprehensive_mapping_file = os.path.join(base_path, "comprehensive_vaccine_mapping.json")
        
        # Cache for loaded configs
        self._comprehensive_mapping = None
        self._unified_config = None
        self._brand_to_disease_map = None
        self._disease_to_brands_map = None
    
    @property
    def comprehensive_mapping(self) -> Dict:
        """Load comprehensive vaccine mapping (protected from interface changes)"""
        if self._comprehensive_mapping is None:
            self._comprehensive_mapping = self._load_json_file(self.comprehensive_mapping_file)
        return self._comprehensive_mapping
    
    @property
    def schedule_interface(self) -> Dict:
        """Load unified vaccine schedule config (replaces old schedule_interface)"""
        if self._unified_config is None:
            self._unified_config = emr_config.load_vaccine_config()
        return self._unified_config
    
    def get_brand_to_disease_mapping(self) -> Dict[str, str]:
        """Get mapping from brand names to canonical disease names"""
        if self._brand_to_disease_map is None:
            self._brand_to_disease_map = self._create_brand_to_disease_mapping()
        return self._brand_to_disease_map
    
    def get_disease_to_brands_mapping(self) -> Dict[str, List[str]]:
        """Get mapping from canonical disease names to brand names"""
        if self._disease_to_brands_map is None:
            self._disease_to_brands_map = self._create_disease_to_brands_mapping()
        return self._disease_to_brands_map
    
    def get_database_field_mappings(self) -> List[Tuple[str, str, int]]:
        """Get mappings from database fields to diseases for migration"""
        mappings = []
        
        for disease_name, disease_info in self.comprehensive_mapping.items():
            database_fields = disease_info.get('database_fields', [])
            
            for i, field_name in enumerate(database_fields):
                dose_number = self._extract_dose_number_from_field(field_name, i)
                mappings.append((disease_name, field_name, dose_number))
        
        return mappings
    
    def map_brand_to_disease(self, brand_name: str) -> Optional[str]:
        """Map a brand name to its canonical disease name"""
        brand_mapping = self.get_brand_to_disease_mapping()
        
        # Try exact match first
        if brand_name in brand_mapping:
            return brand_mapping[brand_name]
        
        # Try uppercase match
        brand_upper = brand_name.upper()
        if brand_upper in brand_mapping:
            return brand_mapping[brand_upper]
        
        # Return None if no mapping found (fallback to original name)
        return None
    
    def get_disease_category(self, disease_name: str) -> str:
        """Get category (mandatory/recommended) for a disease from unified config"""
        # First try unified config
        unified_config = self.schedule_interface
        if disease_name in unified_config:
            return unified_config[disease_name].get('category', 'recommended')
        
        # Fallback to comprehensive mapping
        disease_info = self.comprehensive_mapping.get(disease_name, {})
        return disease_info.get('category', 'recommended')
    
    def get_disease_schedule(self, disease_name: str) -> List[Dict]:
        """Get dose schedule for a disease from unified config"""
        # First try unified config
        unified_config = self.schedule_interface
        if disease_name in unified_config:
            doses_info = unified_config[disease_name].get('doses', {})
            # Convert to list format expected by legacy code
            schedule = []
            for dose_key, dose_info in doses_info.items():
                schedule.append({
                    'dose': dose_key,
                    'age': dose_info.get('age_display', ''),
                    'age_months': dose_info.get('age_months', 0)
                })
            return schedule
        
        # Fallback to comprehensive mapping
        disease_info = self.comprehensive_mapping.get(disease_name, {})
        return disease_info.get('doses', [])
    
    def _load_json_file(self, file_path: str) -> Dict:
        """Load JSON file with error handling"""
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"Warning: Config file {file_path} not found")
                return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing {file_path}: {e}")
            return {}
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return {}
    
    def _create_brand_to_disease_mapping(self) -> Dict[str, str]:
        """Create brand name to disease mapping from comprehensive config"""
        brand_to_disease = {}
        
        for disease_name, disease_info in self.comprehensive_mapping.items():
            brand_names = disease_info.get('brand_names', [])
            
            for brand_name in brand_names:
                # Store both original case and uppercase for robust matching
                brand_to_disease[brand_name] = disease_name
                brand_to_disease[brand_name.upper()] = disease_name
        
        return brand_to_disease
    
    def _create_disease_to_brands_mapping(self) -> Dict[str, List[str]]:
        """Create disease to brand names mapping"""
        disease_to_brands = {}
        
        for disease_name, disease_info in self.comprehensive_mapping.items():
            brand_names = disease_info.get('brand_names', [])
            disease_to_brands[disease_name] = brand_names
        
        return disease_to_brands
    
    def _extract_dose_number_from_field(self, field_name: str, fallback_index: int) -> int:
        """Extract dose number from database field name"""
        field_lower = field_name.lower()
        
        # Handle rappel (booster) fields
        if 'rappel' in field_lower:
            if 'rappel1' in field_lower:
                return 4  # First booster after 3 primary doses
            elif 'rappel2' in field_lower:
                return 5
            elif 'rappel3' in field_lower:
                return 6
            elif 'rappel4' in field_lower:
                return 7
            else:
                return 4  # Default single rappel
        
        # Handle numbered fields
        if '1' in field_name:
            return 1
        elif '2' in field_name:
            return 2
        elif '3' in field_name:
            return 3
        
        # Handle special cases
        if field_name in ['ror_date', 'rougeole_seule_date']:
            return 1
        elif 'monotest1' in field_lower:
            return 1
        elif 'monotest2' in field_lower:
            return 2
        elif 'monotest3' in field_lower:
            return 3
        
        # Fallback to index-based numbering
        return fallback_index + 1
    
    def reload_configs(self):
        """Force reload of all configuration files"""
        self._comprehensive_mapping = None
        self._unified_config = None
        self._brand_to_disease_map = None
        self._disease_to_brands_map = None

# Global instance
immunization_config = ImmunizationConfigService() 