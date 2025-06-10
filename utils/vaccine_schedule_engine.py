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
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

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

@dataclass
class VaccineScheduleItem:
    """Complete vaccine schedule item with all doses"""
    vaccine_name: str
    category: str
    doses: List[VaccineDose]
    completion_percentage: float
    next_due_dose: Optional[VaccineDose] = None

class VaccineScheduleEngine:
    """Vaccine schedule engine for calculating patient-specific vaccine timelines"""
    
    def __init__(self, schedule_config: Optional[Dict] = None, config_file_path: Optional[str] = None):
        self.config_file_path = config_file_path or "vaccine_schedule_config.json"
        self.schedule_config = schedule_config or self._load_schedule_config()
        self.grace_period_days = 30  # Days after due date before marking overdue
        self.upcoming_window_days = 30  # Days before due date to mark as upcoming
    
    def _load_schedule_config(self) -> Dict:
        """Load vaccine schedule configuration from file or use defaults"""
        # Try to load from config file first
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r') as f:
                    config_data = json.load(f)
                    return self._parse_json_schedule(config_data)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load vaccine config from {self.config_file_path}: {e}")
        
        # Fall back to medically accurate default schedule
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
            for vaccine_name, vaccine_info in self.schedule_config.items():
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
            
            with open(self.config_file_path, 'w') as f:
                json.dump(json_format, f, indent=2)
                
            print(f"Vaccine schedule configuration saved to {self.config_file_path}")
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
                        dose_key = f"d{i+1}" if i < 3 else f"r{i-2}"  # d1,d2,d3,r1,r2,r3,r4
                        
                        doses_dict[dose_key] = {
                            "age_months": age_months,
                            "age_display": self._format_age_display(age_months),
                            "label": f"Dose {i+1}" if i < 3 else f"Booster {i-2}",
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
                        dose_key = f"d{i+1}" if i < 3 else f"r{i-2}"  # d1,d2,d3,r1,r2,r3,r4
                        
                        doses_dict[dose_key] = {
                            "age_months": age_months,
                            "age_display": self._format_age_display(age_months),
                            "label": f"Dose {i+1}" if i < 3 else f"Booster {i-2}",
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
    
    def calculate_patient_timeline(self, patient_dob: str, patient_vaccines: Dict, 
                                 autres_vaccins: List = None, current_date: Optional[str] = None) -> List[VaccineScheduleItem]:
        """Calculate complete vaccine timeline for a patient"""
        if current_date is None:
            current_date = datetime.now().strftime('%Y-%m-%d')
        
        patient_dob_obj = datetime.strptime(patient_dob, '%Y-%m-%d')
        current_date_obj = datetime.strptime(current_date, '%Y-%m-%d')
        
        # Import the vaccine mapping constants and data preparation function
        try:
            from routes.pdf_export_routes import (
                PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN,
                VACCINE_ALIAS_MAP_EN,
                MANDATORY_CANONICAL_VACCINE_NAMES_EN
            )
            from utils.patient_utils import prepare_vaccine_data_for_emr
        except ImportError:
            print("Warning: Could not import vaccine mapping constants")
            # Fallback to basic field mapping
            PATIENT_FIELD_TO_CANONICAL_DOSE_MAP_EN = [
                ("DTaP - IPV", 'dtcp1_date', 'd1'),
                ("DTaP - IPV", 'dtcp2_date', 'd2'),
                ("DTaP - IPV", 'dtcp3_date', 'd3'),
                ("DTaP - IPV", 'dtcp_rappel1_date', 'r1'),
                ("Hepatitis B", 'hep_b1_date', 'd1'),
                ("Hepatitis B", 'hep_b2_date', 'd2'),
                ("Hepatitis B", 'hep_b3_date', 'd3'),
                ("Hib (Haemophilus influenzae b)", 'hib1_date', 'd1'),
                ("Hib (Haemophilus influenzae b)", 'hib2_date', 'd2'),
                ("Hib (Haemophilus influenzae b)", 'hib3_date', 'd3'),
                ("MMR (Measles, Mumps, Rubella)", 'ror_date', 'd1'),
            ]
            VACCINE_ALIAS_MAP_EN = {}
            MANDATORY_CANONICAL_VACCINE_NAMES_EN = ["DTaP - IPV", "Hepatitis B", "Hib (Haemophilus influenzae b)", "MMR (Measles, Mumps, Rubella)"]
            prepare_vaccine_data_for_emr = None
        
        # Use the existing vaccine data preparation system
        if autres_vaccins is None:
            autres_vaccins = []
        
        try:
            if prepare_vaccine_data_for_emr:
                # Use the same function that patient detail view uses
                all_vaccine_table_data = prepare_vaccine_data_for_emr(patient_vaccines, autres_vaccins, 0)  # patient_id not needed for this use
            else:
                all_vaccine_table_data = []
        except Exception as e:
            print(f"Warning: Could not use existing vaccine data preparation: {e}")
            all_vaccine_table_data = []
        
        timeline = []
        
        for vaccine_name, vaccine_info in self.schedule_config.items():
            doses = []
            completed_doses = 0
            next_due_dose = None
            
            # Special handling for HPV vaccine (age-dependent dosing)
            if vaccine_name == "HPV (Human Papillomavirus)":
                doses_dict = self._get_hpv_schedule(patient_dob_obj, current_date_obj)
            else:
                doses_dict = vaccine_info["doses"]
            
            # Find and consolidate all patient vaccine data for this vaccine (using same logic as PDF)
            consolidated_dose_dates = {}
            all_dates_for_vaccine = []
            
            # Collect all dates from all brand entries for this canonical vaccine
            for vaccine_row in all_vaccine_table_data:
                if vaccine_row['canonical_name_for_check'] == vaccine_name:
                    for dose_key, dose_date in vaccine_row['dose_dates'].items():
                        if dose_date and dose_date != '-':
                            try:
                                # Parse date to ensure it's valid and not in the future
                                if '/' in dose_date:
                                    # Convert from DD/MM/YYYY to YYYY-MM-DD for parsing
                                    date_parts = dose_date.split('/')
                                    if len(date_parts) == 3:
                                        try:
                                            parsed_date_obj = datetime.strptime(f"{date_parts[2]}-{date_parts[1].zfill(2)}-{date_parts[0].zfill(2)}", '%Y-%m-%d')
                                            # Skip future dates beyond a reasonable buffer (1 month)
                                            if parsed_date_obj > current_date_obj + timedelta(days=30):
                                                continue
                                            parsed_date = parsed_date_obj.strftime('%Y-%m-%d')
                                        except ValueError:
                                            continue
                                    else:
                                        continue
                                else:
                                    try:
                                        parsed_date_obj = datetime.strptime(dose_date, '%Y-%m-%d')
                                        # Skip future dates beyond a reasonable buffer (1 month)
                                        if parsed_date_obj > current_date_obj + timedelta(days=30):
                                            continue
                                        parsed_date = dose_date
                                    except ValueError:
                                        continue
                                
                                # Add to list with parsed date for sorting, avoiding duplicates
                                date_tuple = (parsed_date_obj, dose_date)
                                if date_tuple not in all_dates_for_vaccine:
                                    all_dates_for_vaccine.append(date_tuple)
                            except:
                                # Skip invalid dates
                                continue
            
            # Sort dates chronologically and assign to dose slots
            if all_dates_for_vaccine:
                # Sort by actual date object for proper chronological order
                all_dates_for_vaccine.sort(key=lambda x: x[0])
                
                # Assign to dose slots in chronological order (same as PDF logic)
                dose_keys = ['d1', 'd2', 'd3', 'r1', 'r2', 'r3', 'r4']
                for i, (parsed_date_obj, original_date) in enumerate(all_dates_for_vaccine):
                    if i < len(dose_keys):
                        consolidated_dose_dates[dose_keys[i]] = original_date
            
            # Create a consolidated patient vaccine data structure
            patient_vaccine_data = None
            if consolidated_dose_dates:
                patient_vaccine_data = {
                    'dose_dates': consolidated_dose_dates,
                    'canonical_name_for_check': vaccine_name
                }
            
            # Track completed doses for interval-based calculation
            dose_keys_ordered = ['d1', 'd2', 'd3', 'r1', 'r2', 'r3', 'r4']
            actual_dose_dates = {}
            
            # Sort doses by their original scheduled age to process in order
            sorted_doses = sorted(doses_dict.items(), key=lambda x: x[1]['age_months'])
            
            for dose_key, dose_info in sorted_doses:
                # Check if patient has received this dose from the actual patient data
                completed_date = None
                if patient_vaccine_data and dose_key in patient_vaccine_data['dose_dates']:
                    completed_date = patient_vaccine_data['dose_dates'][dose_key]
                    if completed_date and completed_date != '-':
                        # Convert date format if needed
                        try:
                            if '/' in completed_date:
                                # Convert from DD/MM/YYYY to YYYY-MM-DD
                                date_parts = completed_date.split('/')
                                if len(date_parts) == 3:
                                    completed_date = f"{date_parts[2]}-{date_parts[1].zfill(2)}-{date_parts[0].zfill(2)}"
                        except:
                            pass
                        actual_dose_dates[dose_key] = completed_date
                    else:
                        completed_date = None
                
                # Calculate due date using interval-based logic if available
                due_date_obj = self._calculate_dose_due_date(
                    dose_key, dose_info, doses_dict, actual_dose_dates, 
                    patient_dob_obj, dose_keys_ordered
                )
                due_date = due_date_obj.strftime('%Y-%m-%d')
                
                # Calculate actual age in months for this dose based on the calculated due date
                # This ensures vaccines show at their correct calculated ages, not original scheduled ages
                calculated_age_months = ((due_date_obj - patient_dob_obj).days / 30.44)  # More accurate than months calc
                calculated_age_months = round(calculated_age_months)
                
                # Update age display if it differs significantly from original
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
                    days_overdue=days_overdue
                )
                
                doses.append(dose)
                
                if status == VaccineStatus.COMPLETED:
                    completed_doses += 1
                elif status in [VaccineStatus.DUE, VaccineStatus.OVERDUE] and next_due_dose is None:
                    next_due_dose = dose
            
            # Calculate completion percentage
            completion_percentage = (completed_doses / len(doses)) * 100 if doses else 0
            
            # Sort doses by age
            doses.sort(key=lambda d: d.age_months)
            
            vaccine_schedule_item = VaccineScheduleItem(
                vaccine_name=vaccine_name,
                category=vaccine_info["category"],
                doses=doses,
                completion_percentage=completion_percentage,
                next_due_dose=next_due_dose
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
                try:
                    check_date = datetime.strptime(actual_dose_dates[check_dose_key], '%Y-%m-%d')
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
        return json.dumps(self.schedule_config, indent=2)
    
    def import_schedule_config(self, json_config: str) -> None:
        """Import schedule configuration from JSON"""
        try:
            config = json.loads(json_config)
            self.schedule_config = self._parse_json_schedule(config)
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid schedule configuration: {e}")

# Global instance
vaccine_schedule_engine = VaccineScheduleEngine()

def get_patient_vaccine_timeline(patient_dob: str, patient_vaccines: Dict, 
                               autres_vaccins: List = None, current_date: Optional[str] = None) -> List[VaccineScheduleItem]:
    """Get vaccine timeline for a patient using the global engine"""
    return vaccine_schedule_engine.calculate_patient_timeline(patient_dob, patient_vaccines, autres_vaccins, current_date)

def get_vaccine_schedule_config() -> Dict:
    """Get current vaccine schedule configuration"""
    return vaccine_schedule_engine.schedule_config

def update_vaccine_schedule_config(json_config: str) -> None:
    """Update vaccine schedule configuration"""
    vaccine_schedule_engine.import_schedule_config(json_config)
    vaccine_schedule_engine.save_schedule_config()

def save_vaccine_schedule_config() -> None:
    """Save current vaccine schedule configuration to file"""
    vaccine_schedule_engine.save_schedule_config() 