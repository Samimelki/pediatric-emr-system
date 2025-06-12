"""
Vaccine Name Utilities

Shared functions for vaccine name consolidation and mapping across the application.
This ensures consistent behavior between patient routes, vaccine schedule engine, and other modules.
"""

from emr_config import emr_config


def consolidate_vaccine_name(vaccine_name, debug=False):
    """
    Consolidate vaccine name variations using config-driven mapping.
    
    Args:
        vaccine_name (str): Original vaccine name from database
        debug (bool): Whether to print debug information
        
    Returns:
        str: Canonical vaccine name after applying name mappings
    """
    # Load the full config to get name mappings
    config = emr_config.load_vaccine_config()
    name_mappings = config.get('name_mappings', {})
    
    result = name_mappings.get(vaccine_name, vaccine_name)
    
    if debug:
        print(f"DEBUG NAME UTILS: '{vaccine_name}' -> '{result}' | Available mappings: {list(name_mappings.keys())}")
    
    return result


def resolve_vaccine_alias(vaccine_name):
    """
    Resolve vaccine aliases to canonical names.
    
    Note: With the new name_mappings system, this function is largely redundant
    but kept for backward compatibility.
    
    Args:
        vaccine_name (str): Vaccine name to resolve
        
    Returns:
        str: Canonical vaccine name (currently just returns input)
    """
    return vaccine_name  # Name mappings handle this now


def get_canonical_vaccine_name(vaccine_name, debug=False):
    """
    Get the canonical vaccine name by applying both consolidation and alias resolution.
    
    Args:
        vaccine_name (str): Original vaccine name from database
        debug (bool): Whether to print debug information
        
    Returns:
        str: Final canonical vaccine name
    """
    # First consolidate using name mappings
    consolidated_name = consolidate_vaccine_name(vaccine_name, debug=debug)
    
    # Then resolve any remaining aliases (currently a no-op)
    canonical_name = resolve_vaccine_alias(consolidated_name)
    
    return canonical_name


def is_vaccine_in_standard_schedule(vaccine_name, debug=False):
    """
    Check if a vaccine is part of the standard vaccine schedule.
    
    Args:
        vaccine_name (str): Original vaccine name from database
        debug (bool): Whether to print debug information
        
    Returns:
        bool: True if vaccine is in standard schedule, False otherwise
    """
    # Get canonical name
    canonical_name = get_canonical_vaccine_name(vaccine_name, debug=debug)
    
    # Load config and check if canonical name exists
    config = emr_config.load_vaccine_config()
    
    # Skip the name_mappings entry when checking
    vaccine_configs = {k: v for k, v in config.items() if k != 'name_mappings'}
    
    is_standard = canonical_name in vaccine_configs
    
    if debug:
        print(f"DEBUG NAME UTILS: '{vaccine_name}' -> '{canonical_name}' | In standard schedule: {is_standard}")
    
    return is_standard 