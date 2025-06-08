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
    
    def __init__(self, schedule_config: Optional[Dict] = None):
        self.schedule_config = schedule_config or self._load_default_schedule()
        self.grace_period_days = 30  # Days after due date before marking overdue
        self.upcoming_window_days = 30  # Days before due date to mark as upcoming
    
    def _load_default_schedule(self) -> Dict:
        """Load the default vaccine schedule configuration"""
        json_schedule = {
            "DTaP - IPV": {
                "category": "mandatory",
                "doses": ["2M", "4M", "6M", "18M", "5Y", "11Y+2M", "15Y+2M"]
            },
            "Hepatitis B": {
                "category": "mandatory", 
                "doses": ["Birth", "2M", "6M"]
            },
            "Hib (Haemophilus influenzae b)": {
                "category": "mandatory",
                "doses": ["2M", "4M", "6M", "18M"]
            },
            "MMR (Measles, Mumps, Rubella)": {
                "category": "mandatory",
                "doses": ["9M", "12M", "18M"]
            },
            "Pneumococcal PCV": {
                "category": "mandatory",
                "doses": ["2M", "4M", "6M", "12M"]
            },
            "Rotavirus": {
                "category": "mandatory",
                "doses": ["2M", "4M", "6M"]
            },
            "Varicella": {
                "category": "recommended",
                "doses": ["12M", "18M"]
            },
            "Hepatitis A": {
                "category": "recommended",
                "doses": ["12M", "18M"]
            },
            "Typhoid": {
                "category": "recommended",
                "doses": ["2Y", "5Y", "8Y"]
            },
            "HPV (Human Papillomavirus)": {
                "category": "recommended",
                "doses": ["11Y", "11Y+2M", "11Y+6M"]
            },
            "Influenza": {
                "category": "recommended",
                "doses": ["Yearly"]
            },
            "Meningococcal ACWY": {
                "category": "recommended",
                "doses": ["11Y", "16Y"]
            }
        }
        
        return self._parse_json_schedule(json_schedule)
    
    def _parse_json_schedule(self, json_schedule: Dict) -> Dict:
        """Parse JSON schedule format into internal format"""
        parsed_schedule = {}
        
        for vaccine_name, vaccine_info in json_schedule.items():
            category = vaccine_info.get("category", "recommended")
            doses_list = vaccine_info.get("doses", [])
            
            doses_dict = {}
            for i, age_str in enumerate(doses_list):
                if age_str == "Yearly":
                    # Handle yearly vaccines (like flu) - create multiple annual dose slots
                    # Create dose slots for multiple years
                    for year in range(1, 6):  # Create 5 yearly dose slots
                        dose_key = f"d{year}"
                        doses_dict[dose_key] = {
                            "age_months": year * 12,  # 1Y, 2Y, 3Y, 4Y, 5Y
                            "age_display": f"{year}Y",
                            "label": f"Year {year}"
                        }
                    continue
                
                try:
                    age_months = self._parse_age_string(age_str)
                    dose_key = f"d{i+1}" if i < 3 else f"r{i-2}"  # d1,d2,d3,r1,r2,r3,r4
                    
                    doses_dict[dose_key] = {
                        "age_months": age_months,
                        "age_display": self._format_age_display(age_months),
                        "label": f"Dose {i+1}" if i < 3 else f"Booster {i-2}"
                    }
                except (ValueError, KeyError) as e:
                    print(f"Warning: Could not parse age '{age_str}' for {vaccine_name}: {e}")
                    continue
            
            parsed_schedule[vaccine_name] = {
                "category": category,
                "doses": doses_dict
            }
        
        return parsed_schedule
    
    def _parse_age_string(self, age_str: str) -> int:
        """Parse age string (e.g., '2M', '5Y', '11Y+2M') into months"""
        if age_str == "Birth":
            return 0
        elif age_str == "Yearly":
            return -1  # Special marker for yearly vaccines
        
        # Handle compound ages like "11Y+2M"
        if '+' in age_str:
            parts = age_str.split('+')
            total_months = 0
            for part in parts:
                total_months += self._parse_simple_age(part.strip())
            return total_months
        else:
            return self._parse_simple_age(age_str)
    
    def _parse_simple_age(self, age_str: str) -> int:
        """Parse simple age string (e.g., '2M', '5Y') into months"""
        # Extract number and unit
        match = re.match(r'^(\d+)([MY])$', age_str)
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
            
            # Find and consolidate all patient vaccine data for this vaccine (multiple brands/entries)
            all_dates_for_vaccine = []
            for vaccine_row in all_vaccine_table_data:
                if vaccine_row['canonical_name_for_check'] == vaccine_name:
                    # Collect all dates from all brand entries for this canonical vaccine
                    for dose_key, dose_date in vaccine_row['dose_dates'].items():
                        if dose_date and dose_date != '-':
                            try:
                                # Convert date for sorting
                                if '/' in dose_date:
                                    # Convert from DD/MM/YYYY to YYYY-MM-DD for parsing
                                    date_parts = dose_date.split('/')
                                    if len(date_parts) == 3:
                                        parsed_date = f"{date_parts[2]}-{date_parts[1].zfill(2)}-{date_parts[0].zfill(2)}"
                                    else:
                                        parsed_date = dose_date
                                else:
                                    parsed_date = dose_date
                                
                                # Add to list with parsed date for sorting
                                all_dates_for_vaccine.append((parsed_date, dose_date))
                            except:
                                # If date parsing fails, still include it
                                all_dates_for_vaccine.append((dose_date, dose_date))
            
            # Sort dates chronologically and assign to dose slots
            consolidated_dose_dates = {}
            if all_dates_for_vaccine:
                # Remove duplicates and sort
                unique_dates = list(set(all_dates_for_vaccine))
                unique_dates.sort(key=lambda x: x[0])  # Sort by parsed date
                
                # Assign to dose slots in chronological order
                dose_keys = ['d1', 'd2', 'd3', 'r1', 'r2', 'r3', 'r4']
                for i, (parsed_date, original_date) in enumerate(unique_dates):
                    if i < len(dose_keys):
                        consolidated_dose_dates[dose_keys[i]] = original_date
            
            # Create a consolidated patient vaccine data structure
            patient_vaccine_data = None
            if consolidated_dose_dates:
                patient_vaccine_data = {
                    'dose_dates': consolidated_dose_dates,
                    'canonical_name_for_check': vaccine_name
                }
            
            for dose_key, dose_info in vaccine_info["doses"].items():
                # Calculate due date
                due_date_obj = patient_dob_obj + relativedelta(months=dose_info["age_months"])
                due_date = due_date_obj.strftime('%Y-%m-%d')
                
                # Calculate overdue date (due date + grace period)
                overdue_date_obj = due_date_obj + timedelta(days=self.grace_period_days)
                overdue_date = overdue_date_obj.strftime('%Y-%m-%d')
                
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
                    else:
                        completed_date = None
                
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
                    age_months=dose_info["age_months"],
                    age_display=dose_info["age_display"],
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