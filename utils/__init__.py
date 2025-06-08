"""
Utilities package for the EMR system.

Contains utility functions extracted from routes for better code organization.
"""

import datetime

# Helper function to reformat date from YYYY-MM-DD to DD/MM/YY or DD/MM/YYYY
def format_date_for_pdf(date_str, output_format='%d/%m/%y'):
    if not date_str: # Handles None, empty string
        return None # Return None for missing dates
    try:
        dt_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return dt_obj.strftime(output_format)
    except ValueError:
        # If it's not YYYY-MM-DD, it might already be in a displayable format or be 'N/A' textually
        # For the PDF, we might want to be stricter or return None too
        return date_str # Or consider returning None if format is unexpected to force 'Non effectué' 

def format_datetime(dt_obj, output_format='%d/%m/%y %H:%M'):
    if not isinstance(dt_obj, datetime.datetime):
        return dt_obj # Return as is if not a datetime object, or handle error
    try:
        return dt_obj.strftime(output_format)
    except Exception: # Broad exception to catch any formatting issues
        return str(dt_obj) # Fallback to string representation 