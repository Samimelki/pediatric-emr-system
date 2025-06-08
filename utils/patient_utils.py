"""
Patient-related utility functions extracted from routes for better organization.
These functions are pure utility functions with no Flask dependencies.
"""

from collections import defaultdict
from datetime import datetime
from dateutil.relativedelta import relativedelta


def convert_weight_to_kg(weight_raw):
    """
    Convert weight value to kg according to the storage format rules:
    - 2 digits (10-99): Already in kg, display as-is
    - 500-9999: In grams, divide by 1000 to display as kg
    - 10000+: Would be stored as kg value (e.g., 10 for 10kg), display as-is
    """
    if weight_raw is None:
        return None
    
    try:
        weight_val = float(weight_raw)
        
        # 2 digits (10-99): already in kg
        if 10 <= weight_val <= 99:
            return weight_val
        
        # 500-9999: stored in grams, convert to kg
        elif 500 <= weight_val <= 9999:
            return weight_val / 1000.0
        
        # 10000+: this shouldn't happen as per user, but if it does, treat as kg
        elif weight_val >= 10000:
            return weight_val / 1000.0
        
        # Less than 10: assume kg (edge case)
        else:
            return weight_val
            
    except (ValueError, TypeError):
        return None


def convert_kg_to_storage_format(weight_kg):
    """
    Convert weight from kg input to storage format according to rules:
    - If weight is very low (likely infant/baby): store in grams (multiply by 1000)
    - If weight is normal child/adult range: store as kg (2 digits)
    """
    if weight_kg is None:
        return None
    
    try:
        weight_kg_val = float(weight_kg)
        
        # For very small weights (newborns/infants), store in grams
        if weight_kg_val < 10:
            return int(weight_kg_val * 1000)
        
        # For normal weights (children/adults), keep as kg but ensure integer if possible
        else:
            return int(weight_kg_val) if weight_kg_val == int(weight_kg_val) else weight_kg_val
            
    except (ValueError, TypeError):
        return None


def calculate_age_at_visit(birth_date_iso: str, visit_date_iso: str) -> str:
    """Calculates age at visit and returns a human-readable string.
       Expects dates in 'YYYY-MM-DD' format.
    """
    if not birth_date_iso or not isinstance(birth_date_iso, str) or not birth_date_iso.strip():
        print(f"Debug: calculate_age_at_visit - Invalid or missing birth_date_iso: '{birth_date_iso}'")
        return "N/A (No DOB)"
    if not visit_date_iso or not isinstance(visit_date_iso, str) or not visit_date_iso.strip():
        print(f"Debug: calculate_age_at_visit - Invalid or missing visit_date_iso: '{visit_date_iso}'")
        return "N/A (No Visit Date)"

    try:
        # Directly parse YYYY-MM-DD format
        birth_date = datetime.strptime(birth_date_iso, '%Y-%m-%d').date()
        visit_date = datetime.strptime(visit_date_iso, '%Y-%m-%d').date()
    except ValueError as e_main:
        # Fallback for full ISO strings if somehow passed (e.g., 'YYYY-MM-DDTHH:MM:SS')
        try:
            birth_date_cleaned = birth_date_iso.split('T')[0]
            visit_date_cleaned = visit_date_iso.split('T')[0]
            birth_date = datetime.strptime(birth_date_cleaned, '%Y-%m-%d').date()
            visit_date = datetime.strptime(visit_date_cleaned, '%Y-%m-%d').date()
        except ValueError as e_fallback:
            print(f"Error: Could not parse dates for age calculation after multiple attempts. ")
            print(f"  Initial Birth ISO: '{birth_date_iso}', Initial Visit ISO: '{visit_date_iso}'")
            print(f"  Main parsing error: {e_main}")
            print(f"  Fallback parsing error: {e_fallback}")
            return "Invalid date format"

    if visit_date < birth_date:
        return "Visit before birth"

    delta = relativedelta(visit_date, birth_date)

    years = delta.years
    months = delta.months
    days = delta.days

    if years > 0:
        age_str = f"{years}y"
        if months > 0:
            age_str += f" {months}m"
        return age_str
    elif months > 0:
        age_str = f"{months}m"
        if days > 0:
            age_str += f" {days}d"
        return age_str
    elif days >= 0:
        return f"{days}d"
    else:
        return "N/A" # Should not happen


def prepare_vaccine_data_for_emr(patient_data_row, autres_vaccins_query_results, patient_id_for_urls):
    """
    Prepare vaccine data for EMR display (adapted from foxpro2025)
    
    Note: This function needs Flask's url_for, so it requires Flask app context.
    Consider refactoring further to separate data preparation from URL generation.
    """
    from flask import url_for
    from routes.pdf_export_routes import (
        PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN,
        VACCINE_ALIAS_MAP_EN,
        ALL_POSSIBLE_DOSE_KEYS
    )
    
    all_vaccine_data_by_display_name = defaultdict(lambda: {
        'dose_dates': {},
        'edit_urls': {},
        'canonical_name_for_check': '', 
        'sort_key_brand': '' # For secondary sort: brand name or empty string
    })

    # 1. Process defined patient fields (Standard Vaccines)
    for canonical_name, patient_field_key, dose_key in PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN:
        # Handle both dict and Row objects
        try:
            if hasattr(patient_data_row, 'keys'):
                # It's a Row object
                date_val = patient_data_row[patient_field_key] if patient_field_key in patient_data_row.keys() else None
            else:
                # It's a dict or dict-like
                date_val = patient_data_row.get(patient_field_key) if patient_data_row else None
        except (KeyError, TypeError):
            date_val = None
            
        display_name = canonical_name # Standard vaccines usually don't have a separate brand name in this context
        
        if date_val: # Only process if there's a date
            data_entry = all_vaccine_data_by_display_name[display_name]
            data_entry['dose_dates'][dose_key] = date_val
            data_entry['edit_urls'][dose_key] = url_for('vaccine.edit_standard_vaccine_form', patient_id=patient_id_for_urls, field_name=patient_field_key)
            data_entry['canonical_name_for_check'] = canonical_name # Store the base canonical name for mandatory check
            # 'sort_key_brand' remains empty for these as display_name is canonical

    # 2. Process non-standard vaccine entries ("autres_vaccins")
    # These are often brand names, try to map to canonical and format as "Canonical (Brand)"
    dose_keys_for_filling = ALL_POSSIBLE_DOSE_KEYS # Use the global list for filling order

    for v_row in autres_vaccins_query_results:
        original_brand_name = v_row['vaccine_name']
        date_val = v_row['vaccine_date']
        original_edit_url = url_for('vaccine.edit_other_vaccine_form', vaccine_id=v_row['id'])

        if not date_val: # Skip if no date
            continue

        # Try to find a canonical name using the alias map (case-insensitive key check)
        canonical_name_from_alias = None
        for alias_key, mapped_canonical in VACCINE_ALIAS_MAP_EN.items():
            if alias_key.upper() == original_brand_name.upper():
                canonical_name_from_alias = mapped_canonical
                break
        
        final_canonical_name = canonical_name_from_alias if canonical_name_from_alias else original_brand_name
        sort_key_brand_val = ''

        if canonical_name_from_alias and canonical_name_from_alias.upper() != original_brand_name.upper():
            # We found an alias, and it's different from the original name (implying original was a brand)
            display_name = f"{final_canonical_name} ({original_brand_name})"
            sort_key_brand_val = original_brand_name # For sorting by brand name after canonical
        else:
            # No alias found, or alias is same as original (treat original as canonical or unmapped brand)
            display_name = final_canonical_name
            # If final_canonical_name IS original_brand_name, this might be an unmapped brand or already canonical.
            # If we want to distinguish for sorting, this could be refined.

        data_entry = all_vaccine_data_by_display_name[display_name]
        if not data_entry['canonical_name_for_check']: # Set if not already (e.g. by standard vaccine processing)
             data_entry['canonical_name_for_check'] = final_canonical_name # Important for mandatory check
        if not data_entry['sort_key_brand'] and sort_key_brand_val: # Set sort key if available
            data_entry['sort_key_brand'] = sort_key_brand_val

        # Find first available dose slot to place this non-standard vaccine instance
        assigned_to_slot = False
        for dose_key_to_fill in dose_keys_for_filling:
            if dose_key_to_fill not in data_entry['dose_dates'] or data_entry['dose_dates'][dose_key_to_fill] is None:
                # Check if this specific date is already recorded for this vaccine group from another source (unlikely but safeguard)
                is_duplicate_date_in_group = False
                for existing_dose, existing_date in data_entry['dose_dates'].items():
                    if existing_date == date_val:
                        # Potentially also check edit_urls[existing_dose] to see if it's the same source
                        # For now, if date matches, assume it's a duplicate entry for this group for simplicity
                        is_duplicate_date_in_group = True 
                        break
                if not is_duplicate_date_in_group:
                    data_entry['dose_dates'][dose_key_to_fill] = date_val
                    data_entry['edit_urls'][dose_key_to_fill] = original_edit_url
                    assigned_to_slot = True
                    break
        # If not assigned (e.g. all slots full or duplicate dates), it's currently skipped.
        # This matches PDF logic where additional doses beyond available slots or duplicate dates are not repeatedly shown.

    # 3. Convert to list format for template
    final_table_data = []
    for dn, data_dict in all_vaccine_data_by_display_name.items():
        if data_dict['dose_dates']: # Only include if there are any doses
            final_table_data.append({
                'vaccine_display_name': dn,
                'dose_dates': data_dict['dose_dates'],
                'edit_urls': data_dict['edit_urls'],
                'canonical_name_for_check': data_dict['canonical_name_for_check'],
                'sort_key_brand': data_dict['sort_key_brand']
            })
    
    # Sort: Primary by canonical name part of display name, secondary by brand name part
    final_table_data.sort(key=lambda x: (x['canonical_name_for_check'].lower(), x['sort_key_brand'].lower()))

    return final_table_data 