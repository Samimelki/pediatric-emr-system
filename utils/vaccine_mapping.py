#!/usr/bin/env python3
"""
Vaccine Mapping Utilities

Centralized vaccine mapping functionality that loads from vaccine_schedule_config.json
and provides mapping services for brand names to diseases and database fields.
"""

import json
import os
from typing import Dict, List, Optional, Tuple, Set
from functools import lru_cache
# Removed old config_manager import - now using emr_config
from emr_config import emr_config
from dataclasses import dataclass
from datetime import datetime

@dataclass
class VaccineMapping:
    """Represents a vaccine name mapping."""
    original_name: str
    canonical_name: str
    category: str = "unknown"
    
class VaccineMapper:
    """Centralized vaccine mapping manager"""
    
    def __init__(self, config_file_path: str = None):
        self.config_file_path = config_file_path  # Keep for compatibility but not used
        self._comprehensive_mapping = None
        self._brand_to_disease_map_en = None
        self._brand_to_disease_map_fr = None
    
    @property
    def comprehensive_mapping(self) -> Dict:
        """Lazy load comprehensive vaccine mapping"""
        if self._comprehensive_mapping is None:
            self._comprehensive_mapping = self._load_vaccine_mapping()
        return self._comprehensive_mapping
    
    def _load_vaccine_mapping(self) -> Dict:
        """Load comprehensive vaccine mapping from config manager"""
        try:
            mapping = emr_config.load_vaccine_config()
            return mapping if mapping else {}
        except Exception as e:
            print(f"Warning: Error loading vaccine config: {e}")
            return {}
    
    def get_brand_to_disease_mapping(self, language: str = 'en') -> Dict[str, str]:
        """Get brand name to disease mapping for specified language"""
        if language == 'fr':
            if self._brand_to_disease_map_fr is None:
                self._brand_to_disease_map_fr = self._create_brand_to_disease_mapping('fr')
            return self._brand_to_disease_map_fr
        else:
            if self._brand_to_disease_map_en is None:
                self._brand_to_disease_map_en = self._create_brand_to_disease_mapping('en')
            return self._brand_to_disease_map_en
    
    def _create_brand_to_disease_mapping(self, language: str = 'en') -> Dict[str, str]:
        """Create brand name to disease mapping for specified language"""
        brand_to_disease = {}
        
        # French disease name translations
        disease_translations = {
            'Varicella': 'Varicelle',
            'Rotavirus': 'Rotavirus',
            'Pneumococcal PCV': 'Pneumocoque PCV',
            'MMR (Measles, Mumps, Rubella)': 'ROR (Rougeole, Oreillons, Rubéole)',
            'Meningococcal ACWY': 'Méningocoque ACWY',
            'Influenza': 'Grippe',
            'Hepatitis A': 'Hépatite A',
            'Hepatitis B': 'Hépatite B',
            'Meningococcal B': 'Méningocoque B',
            'Meningococcal C': 'Méningocoque C',
            'HPV (Human Papillomavirus)': 'HPV (Papillomavirus humain)',
            'DTaP - IPV': 'DTCP (Diphtérie,Tétanos,Polio,Coqueluche)',
            'Hib (Haemophilus influenzae b)': 'Hib (Hæmophilus influenzæ b)',
            'Measles (single)': 'Anti-Rougeole (seule)',
            'PPD (TB Skin Test)': 'IDR (Test Tuberculinique)'
        }
        
        for disease_name, disease_info in self.comprehensive_mapping.items():
            # Use appropriate disease name based on language
            if language == 'fr' and disease_name in disease_translations:
                canonical_name = disease_translations[disease_name]
            else:
                canonical_name = disease_name
            
            # Add all brand names for this disease
            for brand_name in disease_info.get('brand_names', []):
                # Store both original and uppercase for robust matching
                brand_to_disease[brand_name] = canonical_name
                brand_to_disease[brand_name.upper()] = canonical_name
        
        return brand_to_disease
    
    def map_brand_to_disease(self, brand_name: str, language: str = 'en') -> Optional[str]:
        """Map a single brand name to its disease"""
        mapping = self.get_brand_to_disease_mapping(language)
        return mapping.get(brand_name) or mapping.get(brand_name.upper())
    
    def get_database_field_mappings(self, language: str = 'en') -> List[Tuple[str, str, str]]:
        """Get database field mappings in the format expected by existing code"""
        mappings = []
        
        for disease_name, disease_info in self.comprehensive_mapping.items():
            database_fields = disease_info.get('database_fields', [])
            
            if database_fields:
                # Use appropriate disease name for the language
                if language == 'fr':
                    disease_translations = {
                        'DTaP - IPV': 'DTCP (Diphtérie,Tétanos,Polio,Coqueluche)',
                        'Hib (Haemophilus influenzae b)': 'Hib (Hæmophilus influenzæ b)',
                        'Hepatitis B': 'Hépatite B',
                        'MMR (Measles, Mumps, Rubella)': 'ROR (Rougeole, Oreillons, Rubéole)',
                        'Measles (single)': 'Anti-Rougeole (seule)',
                        'PPD (TB Skin Test)': 'IDR (Test Tuberculinique)'
                    }
                    canonical_name = disease_translations.get(disease_name, disease_name)
                else:
                    canonical_name = disease_name
                
                # Map database fields to dose keys based on field names
                for i, field_name in enumerate(database_fields):
                    if 'rappel' in field_name:
                        # Extract rappel number
                        if 'rappel1' in field_name:
                            dose_key = 'r1'
                        elif 'rappel2' in field_name:
                            dose_key = 'r2'
                        elif 'rappel3' in field_name:
                            dose_key = 'r3'
                        elif 'rappel4' in field_name:
                            dose_key = 'r4'
                        elif 'rappel' in field_name and 'rappel1' not in field_name:
                            dose_key = 'r1'  # Default single rappel
                        else:
                            dose_key = f'r{i+1}'
                    elif field_name.endswith('_date'):
                        # Extract dose number from field name
                        if '1' in field_name:
                            dose_key = 'd1'
                        elif '2' in field_name:
                            dose_key = 'd2'
                        elif '3' in field_name:
                            dose_key = 'd3'
                        else:
                            # Handle special cases like 'ror_date', 'monotest1', etc.
                            if field_name in ['ror_date', 'rougeole_seule_date']:
                                dose_key = 'd1'
                            elif 'monotest1' in field_name:
                                dose_key = 'd1'
                            elif 'monotest2' in field_name:
                                dose_key = 'd2'
                            elif 'monotest3' in field_name:
                                dose_key = 'd3'
                            else:
                                dose_key = f'd{i+1}'
                    else:
                        # Handle monotest fields
                        if 'monotest1' in field_name:
                            dose_key = 'd1'
                        elif 'monotest2' in field_name:
                            dose_key = 'd2'
                        elif 'monotest3' in field_name:
                            dose_key = 'd3'
                        else:
                            dose_key = f'd{i+1}'
                    
                    mappings.append((canonical_name, field_name, dose_key))
        
        return mappings
    
    def get_field_mapping_dict(self, language: str = 'en') -> Dict[str, Dict[str, str]]:
        """Get field mapping as nested dictionary for JavaScript usage"""
        mapping_dict = {}
        
        for canonical_name, field_name, dose_key in self.get_database_field_mappings(language):
            if canonical_name not in mapping_dict:
                mapping_dict[canonical_name] = {}
            mapping_dict[canonical_name][dose_key] = field_name
        
        return mapping_dict
    
    def get_javascript_mapping(self, language: str = 'en') -> str:
        """Generate JavaScript object string for field mappings"""
        mapping_dict = self.get_field_mapping_dict(language)
        return json.dumps(mapping_dict, indent=4)
    
    def get_brand_name_aliases(self, language: str = 'en') -> Dict[str, str]:
        """Get brand name aliases for backward compatibility"""
        brand_mapping = self.get_brand_to_disease_mapping(language)
        
        # Convert to format expected by existing code (brand -> canonical)
        aliases = {}
        for brand_name, disease_name in brand_mapping.items():
            if brand_name != brand_name.upper():  # Only include original case versions
                aliases[brand_name.upper()] = disease_name
        
        return aliases


# Global instance for easy access
vaccine_mapper = VaccineMapper()

# Convenience functions for backward compatibility
def get_comprehensive_mapping() -> Dict:
    """Get comprehensive vaccine mapping"""
    return vaccine_mapper.comprehensive_mapping

def get_brand_to_disease_mapping(language: str = 'en') -> Dict[str, str]:
    """Get brand to disease mapping for specified language"""
    return vaccine_mapper.get_brand_to_disease_mapping(language)

def map_brand_to_disease(brand_name: str, language: str = 'en') -> Optional[str]:
    """Map brand name to disease"""
    return vaccine_mapper.map_brand_to_disease(brand_name, language)

def get_database_field_mappings(language: str = 'en') -> List[Tuple[str, str, str]]:
    """Get database field mappings"""
    return vaccine_mapper.get_database_field_mappings(language)

def get_field_mapping_dict(language: str = 'en') -> Dict[str, Dict[str, str]]:
    """Get field mapping as dictionary"""
    return vaccine_mapper.get_field_mapping_dict(language)

def get_javascript_mapping(language: str = 'en') -> str:
    """Get JavaScript mapping string"""
    return vaccine_mapper.get_javascript_mapping(language)

class VaccineMappingService:
    """Service for managing vaccine name mappings and consolidation."""
    
    def __init__(self):
        self._config_cache = None
        self._name_mappings_cache = None
    
    def _get_config(self) -> Dict:
        """Get vaccine configuration with caching."""
        if self._config_cache is None:
            self._config_cache = emr_config.load_vaccine_config()
        return self._config_cache
    
    def get_name_mappings(self) -> Dict[str, str]:
        """Get name mappings from configuration."""
        if self._name_mappings_cache is None:
            config = self._get_config()
            self._name_mappings_cache = config.get('name_mappings', {})
        return self._name_mappings_cache
    
    def consolidate_vaccine_name(self, vaccine_name: str) -> str:
        """
        Consolidate vaccine name using configuration mappings.
        
        Args:
            vaccine_name: Original vaccine name
            
        Returns:
            Consolidated vaccine name (canonical form)
        """
        mappings = self.get_name_mappings()
        return mappings.get(vaccine_name, vaccine_name)
    
    def get_canonical_vaccines(self) -> Set[str]:
        """Get set of all canonical vaccine names from configuration."""
        config = self._get_config()
        # Filter out non-vaccine keys
        return {name for name in config.keys() 
                if not name.startswith('_') and name != 'name_mappings'}
    
    def is_standard_vaccine(self, vaccine_name: str) -> bool:
        """
        Check if a vaccine is part of the standard schedule.
        
        Args:
            vaccine_name: Vaccine name to check
            
        Returns:
            True if vaccine is in standard schedule
        """
        consolidated_name = self.consolidate_vaccine_name(vaccine_name)
        canonical_vaccines = self.get_canonical_vaccines()
        return consolidated_name in canonical_vaccines
    
    def get_vaccine_category(self, vaccine_name: str) -> str:
        """
        Get the category of a vaccine (mandatory, recommended, etc.).
        
        Args:
            vaccine_name: Vaccine name
            
        Returns:
            Category string or 'unknown'
        """
        consolidated_name = self.consolidate_vaccine_name(vaccine_name)
        config = self._get_config()
        vaccine_info = config.get(consolidated_name, {})
        return vaccine_info.get('category', 'unknown')
    
    def clear_cache(self):
        """Clear cached configuration data."""
        self._config_cache = None
        self._name_mappings_cache = None

# Global instance
vaccine_mapping_service = VaccineMappingService() 