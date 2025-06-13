"""
Vaccine Schedule Engine

This module provides:
- Configurable vaccine schedule system
- Support for flexible schedule formats ("2M", "4M", "5Y", "Yearly", etc.)
- Patient-specific timeline calculations
- Status determination (due, overdue, completed, upcoming)
- Visual timeline data preparation
"""

import json
import re
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict
from emr_config import emr_config

class VaccineStatus(Enum):
    """Vaccine dose status enumeration"""
    COMPLETED = "completed"
    DUE = "due"
    OVERDUE = "overdue"
    UPCOMING = "upcoming"
    NOT_APPLICABLE = "not_applicable"

@dataclass
class VaccineDose:
    """Individual vaccine dose information"""
    dose_key: str
    label: str
    age_months: int
    age_display: str
    status: VaccineStatus
    due_date: Optional[str] = None
    overdue_date: Optional[str] = None
    completed_date: Optional[str] = None
    days_until_due: Optional[int] = None
    days_overdue: Optional[int] = None
    vaccine_id: Optional[int] = None  # For non-standard vaccines

@dataclass
class VaccineScheduleItem:
    """Complete vaccine schedule item with all doses"""
    vaccine_name: str
    category: str
    doses: List[VaccineDose]
    completion_percentage: float
    next_due_dose: Optional[VaccineDose] = None
    vaccine_id: Optional[int] = None  # For non-standard vaccines

class VaccineScheduleEngine:
    """Vaccine schedule engine for calculating patient-specific vaccine timelines"""
    
    def __init__(self, config_file_path=None):
        """Initialize the vaccine schedule engine with configuration."""
        self.config_file_path = config_file_path or emr_config.get_vaccine_config_path()
        self.config = emr_config.load_vaccine_config()
        self.debug = True
        self.grace_period_days = 30  # Days after due date before marking overdue
        self.upcoming_window_days = 30  # Days before due date to mark as upcoming
    
    def _load_schedule_config(self) -> Dict:
        """Load vaccine schedule configuration from file or use defaults"""
        config_data = emr_config.load_vaccine_config()
        if config_data:
            return self._parse_json_schedule(config_data)
        else:
            print("No vaccine config found, using defaults")
            return self._load_default_schedule()
    
    def _load_default_schedule(self) -> Dict:
        """Load the medically accurate default vaccine schedule configuration"""
        json_schedule = {
            "DTaP - IPV": {
                "category": "mandatory",
                "doses": [
                    {"age": "2M", "interval_to_next": "2M"},
                    {"age": "4M", "interval_to_next": "2M"}, 
                    {"age": "6M", "interval_to_next": "12M"},
                    {"age": "18M", "interval_to_next": "3Y7M"},
                    {"age": "5Y", "interval_to_next": "6Y"},
                    {"age": "11Y", "interval_to_next": "4Y"},
                    {"age": "15Y", "interval_to_next": None}
                ]
            },
            "Hepatitis B": {
                "category": "mandatory", 
                "doses": [
                    {"age": "Birth", "interval_to_next": "2M"},
                    {"age": "2M", "interval_to_next": "4M"},
                    {"age": "6M", "interval_to_next": None}
                ]
            },
            "Hib (Haemophilus influenzae b)": {
                "category": "mandatory",
                "doses": [
                    {"age": "2M", "interval_to_next": "2M"},
                    {"age": "4M", "interval_to_next": "2M"},
                    {"age": "6M", "interval_to_next": "12M"},
                    {"age": "18M", "interval_to_next": None}
                ]
            },
            "MMR (Measles, Mumps, Rubella)": {
                "category": "mandatory",
                "doses": [
                    {"age": "9M", "interval_to_next": "3M"},
                    {"age": "12M", "interval_to_next": "6M"},
                    {"age": "18M", "interval_to_next": None}
                ]
            },
            "Pneumococcal PCV": {
                "category": "mandatory",
                "doses": [
                    {"age": "2M", "interval_to_next": "2M"},
                    {"age": "4M", "interval_to_next": "2M"},
                    {"age": "6M", "interval_to_next": "6M"},
                    {"age": "12M", "interval_to_next": None}
                ]
            },
            "Rotavirus": {
                "category": "mandatory",
                "doses": [
                    {"age": "2M", "interval_to_next": "2M"},
                    {"age": "4M", "interval_to_next": "2M"},
                    {"age": "6M", "interval_to_next": None}
                ]
            },
            "Varicella": {
                "category": "recommended",
                "doses": [
                    {"age": "12M", "interval_to_next": "6M"},
                    {"age": "18M", "interval_to_next": None}
                ]
            },
            "Hepatitis A": {
                "category": "recommended",
                "doses": [
                    {"age": "16M", "interval_to_next": "6M"},
                    {"age": "22M", "interval_to_next": None}
                ]
            },
            "Typhoid": {
                "category": "recommended",
                "doses": [
                    {"age": "24M", "interval_to_next": None}
                ]
            },
            "HPV (Human Papillomavirus)": {
                "category": "recommended",
                "note": "Age-dependent dosing: 2-dose series if <15Y, 3-dose series if ≥15Y",
                "doses": [
                    {"age": "11Y", "interval_to_next": "6M"},
                    {"age": "11Y6M", "interval_to_next": None}
                ]
            },
            "Influenza": {
                "category": "recommended",
                "doses": [
                    {"age": "1Y", "interval_to_next": "1Y", "repeating": True}
                ]
            },
            "Meningococcal ACWY": {
                "category": "recommended",
                "doses": [
                    {"age": "11Y", "interval_to_next": "5Y"},
                    {"age": "16Y", "interval_to_next": None}
                ]
            }
        }
        
        return self._parse_json_schedule(json_schedule)
    
    def save_schedule_config(self) -> None:
        """Save current schedule configuration to file"""
        try:
            # Convert internal format back to JSON format for saving
            json_format = {}
            for vaccine_name, vaccine_info in self.config.items():
                dose_list = []
                sorted_dose_keys = sorted(vaccine_info["doses"].keys())
                
                for dose_key in sorted_dose_keys:
                    dose_info = vaccine_info["doses"][dose_key]
                    
                    # Check if this dose has interval information
                    if "interval_to_next_months" in dose_info:
                        interval_to_next = None
                        if dose_info["interval_to_next_months"] is not None:
                            interval_to_next = self._format_age_display(dose_info["interval_to_next_months"])
                        
                        dose_obj = {
                            "age": dose_info["age_display"],
                            "interval_to_next": interval_to_next
                        }
                        
                        # Check if this is a repeating dose (only for vaccines like Influenza)
                        if (dose_key == "d1" and len(sorted_dose_keys) > 1 and 
                            vaccine_name in ["Influenza"]):
                            next_dose_key = sorted_dose_keys[1]
                            next_dose_info = vaccine_info["doses"][next_dose_key]
                            # Check if the intervals are consistent (indicating a repeating pattern)
                            if (dose_info.get("interval_to_next_months") == 
                                next_dose_info.get("interval_to_next_months")):
                                dose_obj["repeating"] = True
                                dose_list.append(dose_obj)
                                break  # Only add the first dose for repeating vaccines
                        
                        dose_list.append(dose_obj)
                    else:
                        # Legacy format - just the age string
                        dose_list.append(dose_info["age_display"])
                
                json_format[vaccine_name] = {
                    "category": vaccine_info["category"],
                    "doses": dose_list
                }
                if "note" in vaccine_info:
                    json_format[vaccine_name]["note"] = vaccine_info["note"]
                if "flexible" in vaccine_info:
                    json_format[vaccine_name]["flexible"] = vaccine_info["flexible"]
            
            emr_config.save_vaccine_config(json_format)
            print("Vaccine schedule configuration saved")
        except Exception as e:
            print(f"Error saving vaccine schedule configuration: {e}")
    
    def _parse_json_schedule(self, json_schedule: Dict) -> Dict:
        """Parse JSON schedule format into internal format"""
        parsed_schedule = {}
        
        for vaccine_name, vaccine_info in json_schedule.items():
            category = vaccine_info.get("category", "recommended")
            doses_list = vaccine_info.get("doses", [])
            note = vaccine_info.get("note", "")
            
            # Check if this is a flexible vaccine (can start at any age)
            flexible_config = vaccine_info.get("flexible", None)
            
            doses_dict = {}
            
            # Handle different dose formats
            for i, dose_item in enumerate(doses_list):
                # Handle new interval-based format
                if isinstance(dose_item, dict):
                    age_str = dose_item.get("age", "")
                    interval_to_next = dose_item.get("interval_to_next", None)
                    is_repeating = dose_item.get("repeating", False)
                    
                    if is_repeating and interval_to_next:
                        # Handle repeating vaccines (like flu) - create multiple annual dose slots
                        interval_months = self._parse_age_string(interval_to_next) if interval_to_next else 12
                        start_age_months = self._parse_age_string(age_str)
                        
                        for year in range(1, 6):  # Create 5 repeating dose slots
                            dose_key = f"d{year}"
                            age_months = start_age_months + (year - 1) * interval_months
                            doses_dict[dose_key] = {
                                "age_months": age_months,
                                "age_display": self._format_age_display(age_months),
                                "label": f"Year {year}",
                                "interval_to_next_months": interval_months if year < 5 else None
                            }
                        continue
                    
                    try:
                        age_months = self._parse_age_string(age_str)
                        interval_months = self._parse_age_string(interval_to_next) if interval_to_next else None
                        
                        # Use simple d1,d2,d3,d4... format for most vaccines
                        # Only use booster format for vaccines that explicitly need it
                        if vaccine_name in ["DTaP - IPV", "Hib (Haemophilus influenzae b)", "PPD (TB Skin Test)"]:
                            # These vaccines have boosters after primary series
                            dose_key = f"d{i+1}" if i < 3 else f"r{i-2}"
                            label = f"Dose {i+1}" if i < 3 else f"Booster {i-2}"
                        else:
                            # Most vaccines use simple dose numbering
                            dose_key = f"d{i+1}"
                            label = f"Dose {i+1}"
                        
                        doses_dict[dose_key] = {
                            "age_months": age_months,
                            "age_display": self._format_age_display(age_months),
                            "label": label,
                            "interval_to_next_months": interval_months
                        }
                    except (ValueError, KeyError) as e:
                        print(f"Warning: Could not parse dose '{dose_item}' for {vaccine_name}: {e}")
                        continue
                
                # Handle legacy string format for backward compatibility
                elif isinstance(dose_item, str):
                    age_str = dose_item
                    
                    if age_str == "Yearly":
                        # Handle yearly vaccines (like flu) - create multiple annual dose slots
                        for year in range(1, 6):  # Create 5 yearly dose slots
                            dose_key = f"d{year}"
                            doses_dict[dose_key] = {
                                "age_months": year * 12,  # 1Y, 2Y, 3Y, 4Y, 5Y
                                "age_display": f"{year}Y",
                                "label": f"Year {year}",
                                "interval_to_next_months": 12 if year < 5 else None
                            }
                        continue
                    
                    try:
                        age_months = self._parse_age_string(age_str)
                        
                        # Use simple d1,d2,d3,d4... format for most vaccines
                        if vaccine_name in ["DTaP - IPV", "Hib (Haemophilus influenzae b)", "PPD (TB Skin Test)"]:
                            dose_key = f"d{i+1}" if i < 3 else f"r{i-2}"
                            label = f"Dose {i+1}" if i < 3 else f"Booster {i-2}"
                        else:
                            dose_key = f"d{i+1}"
                            label = f"Dose {i+1}"
                        
                        doses_dict[dose_key] = {
                            "age_months": age_months,
                            "age_display": self._format_age_display(age_months),
                            "label": label,
                            "interval_to_next_months": None  # No interval info in legacy format
                        }
                    except (ValueError, KeyError) as e:
                        print(f"Warning: Could not parse age '{age_str}' for {vaccine_name}: {e}")
                        continue
            
            # Auto-calculate missing intervals from age differences
            dose_keys_sorted = sorted(doses_dict.keys(), key=lambda k: doses_dict[k]["age_months"])
            for i, dose_key in enumerate(dose_keys_sorted[:-1]):  # All but the last dose
                current_dose = doses_dict[dose_key]
                next_dose = doses_dict[dose_keys_sorted[i+1]]
                
                # If interval is not set, calculate it from age difference
                if current_dose.get("interval_to_next_months") is None:
                    interval_months = next_dose["age_months"] - current_dose["age_months"]
                    current_dose["interval_to_next_months"] = interval_months
                    print(f"DEBUG: Auto-calculated interval for {vaccine_name} {dose_key}: {interval_months} months")
            
            parsed_schedule[vaccine_name] = {
                "category": category,
                "doses": doses_dict
            }
            if note:
                parsed_schedule[vaccine_name]["note"] = note
            if flexible_config:
                parsed_schedule[vaccine_name]["flexible"] = flexible_config
            
            # Preserve database_fields and brand_names for comprehensive mapping
            if "database_fields" in vaccine_info:
                parsed_schedule[vaccine_name]["database_fields"] = vaccine_info["database_fields"]
            if "brand_names" in vaccine_info:
                parsed_schedule[vaccine_name]["brand_names"] = vaccine_info["brand_names"]
        
        return parsed_schedule
    
    def _parse_age_string(self, age_str: str) -> int:
        """Parse age string (e.g., '2M', '5Y', '11Y+2M', '12Y2M') into months"""
        if age_str == "Birth":
            return 0
        elif age_str == "Yearly":
            return -1  # Special marker for yearly vaccines
        
        # Handle compound ages like "11Y+2M" or "12Y2M"
        if '+' in age_str:
            parts = age_str.split('+')
            total_months = 0
            for part in parts:
                total_months += self._parse_simple_age(part.strip())
            return total_months
        elif self._is_compound_age(age_str):
            # Handle formats like "12Y2M" (without plus)
            return self._parse_compound_age(age_str)
        else:
            return self._parse_simple_age(age_str)
    
    def _is_compound_age(self, age_str: str) -> bool:
        """Check if age string is a compound format like '12Y2M'"""
        return re.match(r'^\d+[YM]\d+[YM]$', age_str) is not None
    
    def _parse_compound_age(self, age_str: str) -> int:
        """Parse compound age string (e.g., '12Y2M', '1Y6M') into months"""
        # Extract all number-unit pairs
        matches = re.findall(r'(\d+)([YM])', age_str)
        if not matches:
            raise ValueError(f"Invalid compound age format: {age_str}")
        
        total_months = 0
        for number_str, unit in matches:
            number = int(number_str)
            if unit == 'M':
                total_months += number
            elif unit == 'Y':
                total_months += number * 12
        
        return total_months
    
    def _parse_simple_age(self, age_str: str) -> int:
        """Parse simple age string (e.g., '2M', '5Y') into months"""
        # Extract number and unit
        match = re.match(r'^(\d+)([YM])$', age_str)
        if not match:
            raise ValueError(f"Invalid age format: {age_str}")
        
        number = int(match.group(1))
        unit = match.group(2)
        
        if unit == 'M':
            return number
        elif unit == 'Y':
            return number * 12
        else:
            raise ValueError(f"Invalid age unit: {unit}")
    
    def _format_age_display(self, age_months: int) -> str:
        """Format age in months to display string"""
        if age_months == 0:
            return "Birth"
        elif age_months < 12:
            return f"{age_months}M"
        elif age_months % 12 == 0:
            return f"{age_months // 12}Y"
        else:
            years = age_months // 12
            months = age_months % 12
            return f"{years}Y{months}M"
    
    def calculate_patient_timeline(self, patient_dob: str,
                                 administered_immunizations: List[Dict],
                                 current_date: Optional[str] = None) -> List[VaccineScheduleItem]:
        """Calculate complete vaccine timeline for a patient"""
        if current_date is None:
            current_date = datetime.now().strftime('%Y-%m-%d')
        
        patient_dob_obj = datetime.strptime(patient_dob, '%Y-%m-%d')
        current_date_obj = datetime.strptime(current_date, '%Y-%m-%d')
        
        # Use shared vaccine name utilities for consistent behavior
        from utils.vaccine_name_utils import get_canonical_vaccine_name
        
        # Prepare a detailed lookup dictionary for administered immunizations with consolidation
        administered_lookup = defaultdict(list)
        for record in administered_immunizations:
            # Skip records with null/None/empty administered_date
            administered_date = record['administered_date']
            if not administered_date or administered_date == 'None' or administered_date.strip() == '':
                if self.debug:
                    print(f"DEBUG ENGINE: Skipping '{record['immunization']}' - null/empty date: {administered_date}")
                continue
                
            # Use shared utility to get canonical name
            canonical_name = get_canonical_vaccine_name(record['immunization'], debug=self.debug)
            # Store the full record, not just the date
            administered_lookup[canonical_name].append({
                'administered_date': administered_date,
                'dose_number': record['dose_number'] if 'dose_number' in record.keys() else None,
                'original_name': record['immunization']
            })
            if self.debug:
                print(f"DEBUG ENGINE: '{record['immunization']}' -> '{canonical_name}' on {administered_date}")
        
        # Sort administered doses by date for each vaccine
        for vaccine in administered_lookup:
            administered_lookup[vaccine].sort(key=lambda x: x['administered_date'] if x['administered_date'] else '1900-01-01')
            
        timeline = []
        
        for vaccine_name, vaccine_info in self.config.items():
            if vaccine_name == 'name_mappings':  # Skip the name_mappings entry
                continue
                
            doses = []
            completed_doses = 0
            next_due_dose = None
            
            if self.debug:
                print(f"DEBUG ENGINE: Processing vaccine '{vaccine_name}' with {len(administered_lookup.get(vaccine_name, []))} administered doses")
            
            # Special handling for HPV vaccine (age-dependent dosing)
            if vaccine_name == "HPV (Human Papillomavirus)":
                doses_dict = self._get_hpv_schedule(patient_dob_obj, current_date_obj)
            else:
                doses_dict = vaccine_info["doses"]
                
            # Debug: Check if doses_dict is actually a dictionary
            if self.debug:
                print(f"DEBUG DOSES STRUCTURE: {vaccine_name} doses type: {type(doses_dict)}")
                if isinstance(doses_dict, dict):
                    print(f"  - Dose keys: {list(doses_dict.keys())}")
                else:
                    print(f"  - Doses content: {doses_dict}")
                    # If it's a list, skip this vaccine for now to avoid crashes
                    if isinstance(doses_dict, list):
                        print(f"  - ERROR: doses_dict is a list, not dict. Skipping {vaccine_name}")
                        continue
            
            # Track completed doses for interval-based calculation
            dose_keys_ordered = ['d1', 'd2', 'd3', 'd4', 'r1', 'r2', 'r3', 'r4']
            administered_records = administered_lookup.get(vaccine_name, [])
            
            # Create actual_dose_dates mapping, but also track if we have extra doses
            actual_dose_dates = {}
            extra_doses = []
            
            if self.debug:
                print(f"DEBUG DOSE ASSIGNMENT: {vaccine_name} has {len(administered_records)} administered doses")
                print(f"  - Available schedule positions: {list(doses_dict.keys())}")
                print(f"  - Standard order template: {dose_keys_ordered}")
            
            # Map administered doses to schedule positions in chronological order
            # This prevents late doses from creating duplicates 
            available_positions = sorted(doses_dict.keys(), key=lambda k: dose_keys_ordered.index(k) if k in dose_keys_ordered else 999)
            
            for i, record in enumerate(administered_records):
                date = record['administered_date']
                if i < len(available_positions):
                    dose_key = available_positions[i]
                    actual_dose_dates[dose_key] = date
                    if self.debug:
                        print(f"DEBUG DOSE ASSIGNMENT: Dose {i+1} ({date}) -> {dose_key}")
                else:
                    # This is an extra dose beyond the configured schedule
                    extra_dose_key = f"extra_{i - len(available_positions) + 1}"
                    extra_doses.append((extra_dose_key, date))
                    if self.debug:
                        print(f"DEBUG DOSE ASSIGNMENT: Extra dose {i+1} ({date}) -> {extra_dose_key}")
            
            if self.debug and extra_doses:
                print(f"DEBUG EXTRA DOSES: {vaccine_name} has {len(extra_doses)} extra doses: {extra_doses}")
            
            # Strategy: Only show administered doses, plus scheduled doses that haven't been given yet
            # This prevents duplicate entries for late doses and keeps timeline clean
            
            # First, process all administered doses (these always get shown)
            administered_dose_keys = set(actual_dose_dates.keys())
            
            # Then, add scheduled doses that haven't been administered yet
            scheduled_not_given = set(doses_dict.keys()) - administered_dose_keys
            
            all_dose_keys = administered_dose_keys | scheduled_not_given
            sorted_dose_keys = sorted(all_dose_keys, key=lambda k: dose_keys_ordered.index(k) if k in dose_keys_ordered else 999)
            
            if self.debug:
                print(f"DEBUG DOSE PROCESSING: {vaccine_name}")
                print(f"  - Administered: {list(administered_dose_keys)}")
                print(f"  - Scheduled but not given: {list(scheduled_not_given)}")
                print(f"  - Processing order: {sorted_dose_keys}")
            
            for dose_key in sorted_dose_keys:
                # Get dose info from schedule, or create minimal info for extra doses
                dose_info = doses_dict.get(dose_key, {
                    'label': f"Dose {dose_keys_ordered.index(dose_key) + 1}" if dose_key in dose_keys_ordered else dose_key,
                    'age_months': 0  # Will be calculated from actual date
                })
                
                # Check if patient has received this dose from the actual patient data
                completed_date = actual_dose_dates.get(dose_key)
                
                # Calculate due date using interval-based logic if available
                # For doses not in configured schedule, use the actual administered date as due date
                if dose_key in doses_dict:
                    due_date_obj = self._calculate_dose_due_date(
                        dose_key, dose_info, doses_dict, actual_dose_dates, 
                        patient_dob_obj, dose_keys_ordered
                    )
                elif completed_date:
                    # For administered doses not in schedule, use administered date as due date
                    try:
                        due_date_obj = datetime.strptime(completed_date, '%Y-%m-%d')
                    except (ValueError, TypeError):
                        # Skip doses with invalid dates
                        if self.debug:
                            print(f"DEBUG: Skipping dose {dose_key} with invalid date: {completed_date}")
                        continue
                else:
                    # Skip doses that are neither in schedule nor administered
                    continue
                due_date = due_date_obj.strftime('%Y-%m-%d')
                
                # Calculate actual age in months for this dose
                # For completed doses, use the actual administered date; for others, use the due date
                if completed_date:
                    # Use actual administered date for completed doses
                    try:
                        administered_date_obj = datetime.strptime(completed_date, '%Y-%m-%d')
                        calculated_age_months = ((administered_date_obj - patient_dob_obj).days / 30.44)
                    except (ValueError, TypeError):
                        # Fall back to due date if administered date is invalid
                        if self.debug:
                            print(f"DEBUG: Invalid administered date {completed_date}, using due date for age calculation")
                        calculated_age_months = ((due_date_obj - patient_dob_obj).days / 30.44)
                else:
                    # Use calculated due date for non-completed doses
                    calculated_age_months = ((due_date_obj - patient_dob_obj).days / 30.44)
                
                calculated_age_months = round(calculated_age_months)
                calculated_age_display = self._format_age_display(calculated_age_months)
                
                # Calculate overdue date (due date + grace period)
                overdue_date_obj = due_date_obj + timedelta(days=self.grace_period_days)
                overdue_date = overdue_date_obj.strftime('%Y-%m-%d')
                
                # Determine status
                status = self._determine_dose_status(
                    due_date_obj, overdue_date_obj, current_date_obj, completed_date
                )
                
                # Calculate days until due or overdue
                days_until_due = None
                days_overdue = None
                
                if status == VaccineStatus.UPCOMING:
                    days_until_due = (due_date_obj - current_date_obj).days
                elif status == VaccineStatus.OVERDUE:
                    days_overdue = (current_date_obj - overdue_date_obj).days
                
                dose = VaccineDose(
                    dose_key=dose_key,
                    label=dose_info["label"],
                    age_months=calculated_age_months,  # Use calculated age instead of original scheduled age
                    age_display=calculated_age_display,  # Use calculated age display
                    status=status,
                    due_date=due_date,
                    overdue_date=overdue_date,
                    completed_date=completed_date,
                    days_until_due=days_until_due,
                    days_overdue=days_overdue,
                    vaccine_id=None  # Use None for standard vaccines
                )
                
                doses.append(dose)
                
                if status == VaccineStatus.COMPLETED:
                    completed_doses += 1
                elif status in [VaccineStatus.DUE, VaccineStatus.OVERDUE] and next_due_dose is None:
                    next_due_dose = dose
            
            # Process extra doses that were administered beyond the configured schedule
            for extra_dose_key, extra_date in extra_doses:
                # Calculate dose number for display
                extra_dose_number = len(doses_dict) + int(extra_dose_key.split('_')[1])
                
                # Parse the date
                try:
                    extra_date_obj = datetime.strptime(extra_date, '%Y-%m-%d')
                    # Calculate age at time of vaccination
                    age_at_vaccination_months = ((extra_date_obj - patient_dob_obj).days / 30.44)
                    age_at_vaccination_months = round(age_at_vaccination_months)
                    age_display = self._format_age_display(age_at_vaccination_months)
                    
                    extra_dose = VaccineDose(
                        dose_key=extra_dose_key,
                        label=f"Dose {extra_dose_number}",
                        age_months=age_at_vaccination_months,
                        age_display=age_display,
                        status=VaccineStatus.COMPLETED,
                        due_date=extra_date,  # Use the actual date as due date
                        overdue_date=None,
                        completed_date=extra_date,
                        days_until_due=None,
                        days_overdue=None,
                        vaccine_id=None
                    )
                    
                    doses.append(extra_dose)
                    completed_doses += 1
                    
                except (ValueError, TypeError):
                    # Skip invalid dates
                    continue
            
            # Calculate completion percentage (including extra doses)
            completion_percentage = (completed_doses / len(doses)) * 100 if doses else 0
            
            # Sort doses by age
            doses.sort(key=lambda d: d.age_months)
            
            vaccine_schedule_item = VaccineScheduleItem(
                vaccine_name=vaccine_name,
                category=vaccine_info["category"],
                doses=doses,
                completion_percentage=completion_percentage,
                next_due_dose=next_due_dose,
                vaccine_id=None  # Use None for standard vaccines
            )
            
            timeline.append(vaccine_schedule_item)
        
        # Sort by category (mandatory first) then by name
        timeline.sort(key=lambda v: (v.category != "mandatory", v.vaccine_name))
        
        return timeline
    
    def _calculate_dose_due_date(self, dose_key: str, dose_info: Dict, doses_dict: Dict, 
                               actual_dose_dates: Dict, patient_dob_obj: datetime, 
                               dose_keys_ordered: List[str]) -> datetime:
        """Calculate due date for a dose using interval-based logic when available"""
        
        # Find the previous dose in the sequence
        try:
            current_dose_index = dose_keys_ordered.index(dose_key)
        except ValueError:
            # If dose key not in standard order, fall back to age-based calculation
            return patient_dob_obj + relativedelta(months=dose_info["age_months"])
        
        # For the first dose, always use age-based calculation (unless already completed)
        if current_dose_index == 0:
            return patient_dob_obj + relativedelta(months=dose_info["age_months"])
        
        # For subsequent doses, check if the vaccine series has been started
        # Look for the earliest completed dose in this vaccine series
        earliest_completed_dose = None
        earliest_completed_date = None
        
        for i in range(current_dose_index):
            check_dose_key = dose_keys_ordered[i]
            if check_dose_key in actual_dose_dates:
                dose_date = actual_dose_dates[check_dose_key]
                # Skip None, empty, or invalid dates
                if not dose_date or dose_date == 'None' or dose_date.strip() == '':
                    continue
                try:
                    check_date = datetime.strptime(dose_date, '%Y-%m-%d')
                    if earliest_completed_date is None or check_date < earliest_completed_date:
                        earliest_completed_date = check_date
                        earliest_completed_dose = check_dose_key
                except (ValueError, TypeError):
                    continue
        
        # If we found a completed dose, calculate from there using intervals
        if earliest_completed_dose is not None:
            print(f"DEBUG: Found completed dose {earliest_completed_dose} on {earliest_completed_date}")
            # Calculate cumulative interval from the earliest completed dose to current dose
            cumulative_interval = 0
            
            # Find the index of the earliest completed dose
            earliest_index = dose_keys_ordered.index(earliest_completed_dose)
            
            # Sum up intervals from earliest completed dose to current dose
            for i in range(earliest_index, current_dose_index):
                interval_dose_key = dose_keys_ordered[i]
                if (interval_dose_key in doses_dict and 
                    "interval_to_next_months" in doses_dict[interval_dose_key] and
                    doses_dict[interval_dose_key]["interval_to_next_months"] is not None):
                    interval_months = doses_dict[interval_dose_key]["interval_to_next_months"]
                    cumulative_interval += interval_months
                    print(f"DEBUG: Adding {interval_months} months from {interval_dose_key}, cumulative: {cumulative_interval}")
                else:
                    print(f"DEBUG: No interval info for {interval_dose_key}, falling back to age-based")
                    # If no interval info, fall back to age-based calculation
                    return patient_dob_obj + relativedelta(months=dose_info["age_months"])
            
            # Calculate due date from earliest completed dose + cumulative interval
            try:
                calculated_date = earliest_completed_date + relativedelta(months=cumulative_interval)
                print(f"DEBUG: Calculated {dose_key} due date: {calculated_date} (from {earliest_completed_date} + {cumulative_interval} months)")
                return calculated_date
            except (ValueError, TypeError):
                pass
        
        # Fall back to age-based calculation if:
        # - No doses completed in series
        # - No interval information available
        # - Date parsing failed
        return patient_dob_obj + relativedelta(months=dose_info["age_months"])
    
    def _get_hpv_schedule(self, patient_dob: datetime, current_date: datetime) -> Dict:
        """Get age-appropriate HPV vaccine schedule"""
        # Calculate age at 11 years (typical start age)
        age_11_date = patient_dob + relativedelta(years=11)
        
        # If patient is currently younger than 15, use 2-dose series
        # If patient is 15 or older, use 3-dose series
        current_age_years = (current_date - patient_dob).days / 365.25
        
        if current_age_years < 15:
            # 2-dose series
            return {
                "d1": {
                    "age_months": 11 * 12,  # 11 years
                    "age_display": "11Y",
                    "label": "Dose 1"
                },
                "d2": {
                    "age_months": 11 * 12 + 6,  # 11 years + 6 months
                    "age_display": "11Y6M",
                    "label": "Dose 2"
                }
            }
        else:
            # 3-dose series for 15+ or immunocompromised
            return {
                "d1": {
                    "age_months": 11 * 12,  # 11 years
                    "age_display": "11Y",
                    "label": "Dose 1"
                },
                "d2": {
                    "age_months": 11 * 12 + 2,  # 11 years + 2 months
                    "age_display": "11Y2M",
                    "label": "Dose 2"
                },
                "d3": {
                    "age_months": 11 * 12 + 6,  # 11 years + 6 months
                    "age_display": "11Y6M",
                    "label": "Dose 3"
                }
            }
    
    def _determine_dose_status(self, due_date: datetime, overdue_date: datetime,
                             current_date: datetime, completed_date: Optional[str]) -> VaccineStatus:
        """Determine the status of a vaccine dose"""
        if completed_date:
            return VaccineStatus.COMPLETED
        
        if current_date >= overdue_date:
            return VaccineStatus.OVERDUE
        elif current_date >= due_date:
            return VaccineStatus.DUE
        elif (due_date - current_date).days <= self.upcoming_window_days:
            return VaccineStatus.UPCOMING
        else:
            return VaccineStatus.NOT_APPLICABLE
    
    def get_summary_stats(self, timeline: List[VaccineScheduleItem]) -> Dict:
        """Get summary statistics for a patient's vaccine timeline"""
        total_doses = sum(len(vaccine.doses) for vaccine in timeline)
        completed_doses = sum(
            len([d for d in vaccine.doses if d.status == VaccineStatus.COMPLETED])
            for vaccine in timeline
        )
        overdue_doses = sum(
            len([d for d in vaccine.doses if d.status == VaccineStatus.OVERDUE])
            for vaccine in timeline
        )
        due_doses = sum(
            len([d for d in vaccine.doses if d.status == VaccineStatus.DUE])
            for vaccine in timeline
        )
        
        completion_percentage = (completed_doses / total_doses * 100) if total_doses > 0 else 0
        
        return {
            "total_doses": total_doses,
            "completed_doses": completed_doses,
            "due_doses": due_doses,
            "overdue_doses": overdue_doses,
            "completion_percentage": completion_percentage,
            "mandatory_vaccines": [v for v in timeline if v.category == "mandatory"],
            "recommended_vaccines": [v for v in timeline if v.category == "recommended"]
        }
    
    def export_schedule_config(self) -> str:
        """Export current schedule configuration as JSON"""
        return json.dumps(self.config, indent=2)
    
    def import_schedule_config(self, json_config: str) -> None:
        """Import schedule configuration from JSON"""
        try:
            config = json.loads(json_config)
            self.config = self._parse_json_schedule(config)
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid schedule configuration: {e}")

# Global instance
vaccine_schedule_engine = VaccineScheduleEngine()

# Force reload of config to pick up database_fields and brand_names
vaccine_schedule_engine.config = vaccine_schedule_engine._load_schedule_config()

def get_patient_vaccine_timeline(patient_dob: str,
                               administered_immunizations: List[Dict],
                               current_date: Optional[str] = None) -> List[VaccineScheduleItem]:
    """
    High-level function to get the vaccine timeline for a patient.
    
    This is the primary entry point from the routes.
    """
    return vaccine_schedule_engine.calculate_patient_timeline(
        patient_dob=patient_dob,
        administered_immunizations=administered_immunizations,
        current_date=current_date
    )

def get_vaccine_schedule_config() -> Dict:
    """Get current vaccine schedule configuration"""
    return vaccine_schedule_engine.config

def update_vaccine_schedule_config(config_data: dict) -> None:
    """Saves a dictionary of config data to the config file."""
    engine = VaccineScheduleEngine()
    # The new config is parsed and then saved in the correct format by the engine
    engine.config = engine._parse_json_schedule(config_data)
    engine.save_schedule_config()

def reset_vaccine_schedule_to_defaults() -> None:
    """Resets the schedule to the internal default and saves it."""
    engine = VaccineScheduleEngine()
    engine.config = engine._load_default_schedule()
    engine.save_schedule_config()

def save_vaccine_schedule_config() -> None:
    """Save current vaccine schedule configuration to file"""
    vaccine_schedule_engine.save_schedule_config() 