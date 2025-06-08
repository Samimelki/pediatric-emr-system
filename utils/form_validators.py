"""
Form validation and processing utilities for the EMR system.

Contains functions for validating and processing form data that are reused across routes.
"""

from datetime import datetime
from emr_config import emr_config


def parse_user_date_input(date_str, field_name="date"):
    """
    Parse user date input according to EMR configuration settings.
    
    Args:
        date_str (str): Date string from user input
        field_name (str): Name of the field for error messages
        
    Returns:
        dict: {
            'success': bool,
            'parsed_date': datetime object (if successful),
            'iso_date': str in YYYY-MM-DD format (if successful), 
            'error_message': str (if failed)
        }
    """
    if not date_str or not isinstance(date_str, str) or not date_str.strip():
        return {
            'success': False,
            'error_message': f'{field_name.capitalize()} is required.'
        }
    
    date_str = date_str.strip()
    
    try:
        user_date_format = emr_config.get_date_format()
        
        if '/' in date_str:
            # Handle user-formatted date input (DD/MM/YYYY or MM/DD/YYYY)
            parts = date_str.split('/')
            if len(parts) == 3:
                if user_date_format == 'dd/mm/yyyy':
                    # DD/MM/YYYY format
                    day, month, year = parts
                else:
                    # MM/DD/YYYY format (default)
                    month, day, year = parts
                # Create standardized format
                parsed_date = datetime.strptime(f"{year}-{month.zfill(2)}-{day.zfill(2)}", '%Y-%m-%d')
            else:
                raise ValueError("Invalid date format - expected 3 parts separated by /")
        else:
            # Try to parse as YYYY-MM-DD (already standard format)
            parsed_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        return {
            'success': True,
            'parsed_date': parsed_date,
            'iso_date': parsed_date.strftime('%Y-%m-%d')
        }
        
    except ValueError:
        expected_format = emr_config.get_date_format().upper()
        return {
            'success': False,
            'error_message': f'Invalid {field_name} format. Please use {expected_format}.'
        }


def validate_date_not_before_birth(visit_date_obj, birth_date_str, visit_date_str):
    """
    Validate that a visit/event date is not before patient's birth date.
    
    Args:
        visit_date_obj (datetime): Parsed visit date object
        birth_date_str (str): Birth date in YYYY-MM-DD format
        visit_date_str (str): Original visit date string for error messages
        
    Returns:
        dict: {
            'success': bool,
            'error_message': str (if failed)
        }
    """
    if not birth_date_str:
        return {'success': True}  # No birth date to validate against
    
    try:
        birth_date_obj = datetime.strptime(birth_date_str, '%Y-%m-%d')
        
        if visit_date_obj.date() < birth_date_obj.date():
            return {
                'success': False,
                'error_message': f"Date ({visit_date_str}) cannot be before patient's birth date ({birth_date_str})."
            }
        
        return {'success': True}
        
    except ValueError:
        # If birth date is invalid, skip validation
        return {'success': True}


def validate_required_fields(form_data, required_fields):
    """
    Validate that required form fields are present and not empty.
    
    Args:
        form_data (dict): Form data (usually request.form)
        required_fields (list): List of required field names
        
    Returns:
        dict: {
            'success': bool,
            'missing_fields': list of missing field names (if failed),
            'error_message': str (if failed)
        }
    """
    missing_fields = []
    
    for field in required_fields:
        value = form_data.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            missing_fields.append(field)
    
    if missing_fields:
        field_list = ", ".join(missing_fields)
        return {
            'success': False,
            'missing_fields': missing_fields,
            'error_message': f'Required fields are missing: {field_list}.'
        }
    
    return {'success': True}


def sanitize_form_input(form_data, field_name, default_value=None):
    """
    Safely extract and sanitize form input.
    
    Args:
        form_data (dict): Form data (usually request.form)
        field_name (str): Name of the field to extract
        default_value: Default value if field is missing or empty
        
    Returns:
        Sanitized field value or default_value
    """
    value = form_data.get(field_name, default_value)
    
    if isinstance(value, str):
        value = value.strip()
        if value == '':
            return default_value
    
    return value 