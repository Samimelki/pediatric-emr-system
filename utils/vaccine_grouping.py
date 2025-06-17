"""
Vaccine Grouping Utility

This module provides intelligent vaccine grouping functionality to:
- Group DTaP, IPV, Hib, and Hepatitis B when given on the same date
- Identify Pentaxim (DTaP + IPV + Hib) and Hexaxim (DTaP + IPV + Hib + Hep B) combinations
- Maintain individual vaccine data for clinical records while providing grouped display
"""

from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class VaccineGroup:
    """Represents a grouped vaccine combination"""
    group_name: str
    display_name: str
    component_vaccines: List[str]
    administered_date: str
    dose_number: int
    age_months: int
    age_display: str
    status: str
    individual_records: List[Dict]  # Original individual vaccine records


class VaccineGrouper:
    """Handles intelligent grouping of vaccines based on administration patterns"""
    
    def __init__(self):
        # Define known combination vaccines
        self.combination_vaccines = {
            'Hexaxim': {
                'components': {'DTaP - IPV', 'Hib (Haemophilus influenzae b)', 'Hepatitis B'},
                'display_name': 'Hexaxim',
                'age_range': (0, 24)  # Typically given in first 2 years
            },
            'Pentaxim': {
                'components': {'DTaP - IPV', 'Hib (Haemophilus influenzae b)'},
                'display_name': 'Pentaxim',
                'age_range': (0, 24)  # Typically given in first 2 years
            }
        }
        
        # Vaccines that should never appear alone (always part of combinations)
        self.never_alone_vaccines = {'Hib (Haemophilus influenzae b)'}
        
        # Age thresholds for different vaccine patterns
        self.age_thresholds = {
            'infant_combination_max': 24,  # Months - after this, combinations are less likely
            'dtap_only_min': 60  # Months (5 years) - DTaP without IPV starts here
        }
    
    def group_vaccines_by_date_and_patient(self, vaccine_records: List[Dict], patient_dob: Optional[str] = None) -> Dict[str, List[VaccineGroup]]:
        """
        Group vaccines by date and patient, identifying combination vaccines.
        
        Args:
            vaccine_records: List of vaccine records with patient_id, immunization, administered_date
            patient_dob: Optional patient date of birth for age calculations
            
        Returns:
            Dictionary mapping patient_id to list of VaccineGroup objects
        """
        # Group by patient and date
        patient_date_groups = defaultdict(lambda: defaultdict(list))
        
        for record in vaccine_records:
            if record.get('administered_date'):
                patient_id = record['patient_id']
                date = record['administered_date']
                patient_date_groups[patient_id][date].append(record)
        
        # Process each patient's vaccine groups
        result = {}
        for patient_id, date_groups in patient_date_groups.items():
            result[patient_id] = self._process_patient_vaccine_groups(date_groups, patient_dob)
        
        return result
    
    def _process_patient_vaccine_groups(self, date_groups: Dict[str, List[Dict]], patient_dob: Optional[str] = None) -> List[VaccineGroup]:
        """Process vaccine groups for a single patient"""
        grouped_vaccines = []
        
        for date, vaccines in date_groups.items():
            if len(vaccines) == 1:
                # Single vaccine - check if it should be grouped
                vaccine = vaccines[0]
                if vaccine['immunization'] in self.never_alone_vaccines:
                    # This shouldn't happen in normal circumstances
                    # but we'll create a group anyway
                    group = self._create_single_vaccine_group(vaccine, patient_dob)
                    grouped_vaccines.append(group)
                else:
                    # Normal single vaccine
                    group = self._create_single_vaccine_group(vaccine, patient_dob)
                    grouped_vaccines.append(group)
            else:
                # Multiple vaccines on same date - check for combinations
                combination_group = self._identify_combination(vaccines, date, patient_dob)
                if combination_group:
                    grouped_vaccines.append(combination_group)
                else:
                    # No recognized combination, treat as individual vaccines
                    for vaccine in vaccines:
                        group = self._create_single_vaccine_group(vaccine, patient_dob)
                        grouped_vaccines.append(group)
        
        return grouped_vaccines
    
    def _identify_combination(self, vaccines: List[Dict], date: str, patient_dob: Optional[str] = None) -> Optional[VaccineGroup]:
        """Identify if vaccines form a known combination"""
        vaccine_names = {v['immunization'] for v in vaccines}
        
        # Check for Hexaxim (DTaP + IPV + Hib + Hep B)
        if self._is_combination_match(vaccine_names, 'Hexaxim'):
            return self._create_combination_group('Hexaxim', vaccines, date, patient_dob)
        
        # Check for Pentaxim (DTaP + IPV + Hib)
        elif self._is_combination_match(vaccine_names, 'Pentaxim'):
            return self._create_combination_group('Pentaxim', vaccines, date, patient_dob)
        
        return None
    
    def _is_combination_match(self, vaccine_names: Set[str], combination_name: str) -> bool:
        """Check if vaccine names match a known combination"""
        required_components = self.combination_vaccines[combination_name]['components']
        return required_components.issubset(vaccine_names)
    
    def _create_combination_group(self, combination_name: str, vaccines: List[Dict], date: str, patient_dob: Optional[str] = None) -> VaccineGroup:
        """Create a VaccineGroup for a recognized combination"""
        combo_info = self.combination_vaccines[combination_name]
        
        # Calculate age and dose information from the first vaccine
        # (they should all be the same date/age)
        first_vaccine = vaccines[0]
        age_months = self._calculate_age_months(first_vaccine, date, patient_dob)
        
        return VaccineGroup(
            group_name=combination_name,
            display_name=combo_info['display_name'],
            component_vaccines=list(combo_info['components']),
            administered_date=date,
            dose_number=first_vaccine.get('dose_number', 1),
            age_months=age_months,
            age_display=self._format_age_display(age_months),
            status='completed',
            individual_records=vaccines
        )
    
    def _create_single_vaccine_group(self, vaccine: Dict, patient_dob: Optional[str] = None) -> VaccineGroup:
        """Create a VaccineGroup for a single vaccine"""
        date = vaccine['administered_date']
        age_months = self._calculate_age_months(vaccine, date, patient_dob)
        
        return VaccineGroup(
            group_name=vaccine['immunization'],
            display_name=vaccine['immunization'],
            component_vaccines=[vaccine['immunization']],
            administered_date=date,
            dose_number=vaccine.get('dose_number', 1),
            age_months=age_months,
            age_display=self._format_age_display(age_months),
            status='completed',
            individual_records=[vaccine]
        )
    
    def _calculate_age_months(self, vaccine: Dict, date: str, patient_dob: Optional[str] = None) -> int:
        """Calculate age in months at vaccination"""
        if not patient_dob:
            return 0
        
        try:
            dob = datetime.strptime(patient_dob, '%Y-%m-%d')
            vaccine_date = datetime.strptime(date, '%Y-%m-%d')
            
            # Calculate age in months
            age_months = (vaccine_date.year - dob.year) * 12 + (vaccine_date.month - dob.month)
            
            # Adjust for day of month
            if vaccine_date.day < dob.day:
                age_months -= 1
                
            return max(0, age_months)
        except (ValueError, TypeError):
            return 0
    
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
    
    def should_group_for_timeline(self, age_months: int, vaccine_names: Set[str]) -> bool:
        """
        Determine if vaccines should be grouped for timeline display based on age and components.
        
        Args:
            age_months: Age in months when vaccines were given
            vaccine_names: Set of vaccine names given together
            
        Returns:
            True if vaccines should be grouped for display
        """
        # Don't group if age is beyond typical combination vaccine age
        if age_months > self.age_thresholds['infant_combination_max']:
            return False
        
        # Check if this matches a known combination
        for combo_name, combo_info in self.combination_vaccines.items():
            if combo_info['components'].issubset(vaccine_names):
                # Check age range
                min_age, max_age = combo_info['age_range']
                if min_age <= age_months <= max_age:
                    return True
        
        return False
    
    def get_grouped_timeline_data(self, timeline_data: List, patient_dob: str) -> List:
        """
        Process timeline data to group vaccines appropriately for display.
        
        Args:
            timeline_data: List of VaccineScheduleItem objects
            patient_dob: Patient date of birth for age calculations
            
        Returns:
            Modified timeline data with grouped vaccines
        """
        if not timeline_data:
            return timeline_data
        

        
        # Simple approach: find vaccines that were given on the same dates and should be grouped
        # Group by completion date of first doses
        date_groups = defaultdict(list)
        
        for vaccine in timeline_data:
            # Find the first completed dose for grouping
            first_completed = None
            for dose in vaccine.doses:
                # Import VaccineStatus to check correctly
                from utils.vaccine_schedule_engine import VaccineStatus
                if (hasattr(dose, 'status') and 
                    dose.status == VaccineStatus.COMPLETED and 
                    hasattr(dose, 'completed_date') and 
                    dose.completed_date):
                    first_completed = dose.completed_date
                    break
            
            if first_completed:
                date_groups[first_completed].append(vaccine)
        

        
        # Process each date group
        result_vaccines = []
        processed_vaccines = set()
        
        for date, vaccines_on_date in date_groups.items():
            if len(vaccines_on_date) >= 2:  # Multiple vaccines on same date
                vaccine_names = {v.vaccine_name for v in vaccines_on_date}

                
                # Calculate age at vaccination
                age_months = self._calculate_age_at_date(patient_dob, date)
                
                # Check if this should be grouped as a combination
                combination_name = should_display_as_combination(vaccine_names, age_months)
                if combination_name:

                    
                    # Create a new combined vaccine entry
                    combo_vaccine = self._create_simple_timeline_combination(
                        combination_name, vaccines_on_date, date, age_months
                    )
                    result_vaccines.append(combo_vaccine)
                    
                    # Mark these vaccines as processed
                    for v in vaccines_on_date:
                        processed_vaccines.add(v.vaccine_name)
                else:
                    # Keep individual vaccines
                    for v in vaccines_on_date:
                        if v.vaccine_name not in processed_vaccines:
                            result_vaccines.append(v)
                            processed_vaccines.add(v.vaccine_name)
            else:
                # Single vaccine on this date
                for v in vaccines_on_date:
                    if v.vaccine_name not in processed_vaccines:
                        result_vaccines.append(v)
                        processed_vaccines.add(v.vaccine_name)
        
        # Add any vaccines that weren't in any date group (no completed doses)
        for vaccine in timeline_data:
            if vaccine.vaccine_name not in processed_vaccines:
                result_vaccines.append(vaccine)
        

        return result_vaccines
    
    def _calculate_age_at_date(self, patient_dob: str, date: str) -> int:
        """Calculate age in months at a specific date"""
        try:
            dob = datetime.strptime(patient_dob, '%Y-%m-%d')
            vaccine_date = datetime.strptime(date, '%Y-%m-%d')
            age_months = (vaccine_date.year - dob.year) * 12 + (vaccine_date.month - dob.month)
            if vaccine_date.day < dob.day:
                age_months -= 1
            return max(0, age_months)
        except (ValueError, TypeError):
            return 0
    
    def _create_simple_timeline_combination(self, combination_name: str, vaccines_on_date: List, date: str, age_months: int):
        """Create a simplified timeline entry for a vaccine combination"""
        from utils.vaccine_schedule_engine import VaccineScheduleItem, VaccineDose, VaccineStatus
        
        combo_info = self.combination_vaccines[combination_name]
        
        # Instead of combining all individual doses (which creates duplicates),
        # create a logical combination schedule by finding matching doses across components
        
        # Group doses by date across all component vaccines
        dose_dates = set()
        for vaccine in vaccines_on_date:
            for dose in vaccine.doses:
                if hasattr(dose, 'completed_date') and dose.completed_date:
                    dose_dates.add(dose.completed_date)
                elif hasattr(dose, 'due_date') and dose.due_date:
                    dose_dates.add(dose.due_date)
        
        # Create combination doses for each unique date
        combination_doses = []
        dose_counter = 1
        
        for dose_date in sorted(dose_dates):
            # Find all component doses that match this date
            matching_doses = []
            for vaccine in vaccines_on_date:
                for dose in vaccine.doses:
                    if (hasattr(dose, 'completed_date') and dose.completed_date == dose_date) or \
                       (hasattr(dose, 'due_date') and dose.due_date == dose_date and not hasattr(dose, 'completed_date')):
                        matching_doses.append(dose)
                        break  # Only take the first matching dose per vaccine
            
            if matching_doses:
                # Use the first dose as template and determine status
                template_dose = matching_doses[0]
                
                # Determine combined status - if any component is completed, mark as completed
                is_completed = any(getattr(d, 'status', None) == VaccineStatus.COMPLETED for d in matching_doses)
                is_due = any(getattr(d, 'status', None) == VaccineStatus.DUE for d in matching_doses)
                is_overdue = any(getattr(d, 'status', None) == VaccineStatus.OVERDUE for d in matching_doses)
                
                if is_completed:
                    status = VaccineStatus.COMPLETED
                elif is_overdue:
                    status = VaccineStatus.OVERDUE
                elif is_due:
                    status = VaccineStatus.DUE
                else:
                    status = getattr(template_dose, 'status', VaccineStatus.NOT_APPLICABLE)
                
                # Create combination dose
                combo_dose = VaccineDose(
                    dose_key=f"d{dose_counter}",
                    label=f"Dose {dose_counter}",
                    age_months=getattr(template_dose, 'age_months', age_months),
                    age_display=getattr(template_dose, 'age_display', f"{age_months}M"),
                    status=status,
                    due_date=getattr(template_dose, 'due_date', None),
                    overdue_date=getattr(template_dose, 'overdue_date', None),
                    completed_date=dose_date if is_completed else None,
                    days_until_due=getattr(template_dose, 'days_until_due', None),
                    days_overdue=getattr(template_dose, 'days_overdue', None),
                    vaccine_id=f"combo_{combination_name}_{dose_counter}"
                )
                
                combination_doses.append(combo_dose)
                dose_counter += 1
        
        # Calculate completion percentage
        completed_count = sum(1 for dose in combination_doses if dose.status == VaccineStatus.COMPLETED)
        completion_percentage = (completed_count / len(combination_doses) * 100) if combination_doses else 0
        
        # Find next due dose
        next_due = None
        for dose in combination_doses:
            if dose.status in [VaccineStatus.DUE, VaccineStatus.OVERDUE]:
                next_due = dose
                break
        
        # Create the combination vaccine entry
        return VaccineScheduleItem(
            vaccine_name=combo_info['display_name'],
            category='mandatory',  # Most combinations are mandatory
            doses=combination_doses,
            completion_percentage=completion_percentage,
            next_due_dose=next_due,
            vaccine_id=f"combo_{combination_name}"
        )
    
    def _create_timeline_combination(self, combination_name: str, vaccine_dose_pairs: List, date: str, age_months: int):
        """Create a timeline entry for a vaccine combination (legacy method)"""
        from utils.vaccine_schedule_engine import VaccineScheduleItem, VaccineDose
        
        combo_info = self.combination_vaccines[combination_name]
        
        # Combine doses from all component vaccines
        all_doses = []
        for vaccine, dose in vaccine_dose_pairs:
            all_doses.extend(vaccine.doses)
        
        # Sort doses by age
        all_doses.sort(key=lambda d: d.age_months)
        
        # Create the combination vaccine entry
        return VaccineScheduleItem(
            vaccine_name=combo_info['display_name'],
            category='mandatory',  # Most combinations are mandatory
            doses=all_doses,
            completion_percentage=100.0,  # Will be recalculated
            next_due_dose=None,
            vaccine_id=None
        )


# Global instance
vaccine_grouper = VaccineGrouper()


def group_vaccines_for_patient(patient_id: int, vaccine_records: List[Dict], patient_dob: Optional[str] = None) -> List[VaccineGroup]:
    """
    Convenience function to group vaccines for a single patient.
    
    Args:
        patient_id: Patient ID
        vaccine_records: List of vaccine records for the patient
        patient_dob: Optional patient date of birth
        
    Returns:
        List of VaccineGroup objects
    """
    all_groups = vaccine_grouper.group_vaccines_by_date_and_patient(vaccine_records, patient_dob)
    return all_groups.get(str(patient_id), [])


def should_display_as_combination(vaccine_names: Set[str], age_months: int) -> Optional[str]:
    """
    Determine if a set of vaccines should be displayed as a combination.
    
    Args:
        vaccine_names: Set of vaccine names
        age_months: Age in months when vaccines were given
        
    Returns:
        Combination name if should be grouped, None otherwise
    """
    if vaccine_grouper.should_group_for_timeline(age_months, vaccine_names):
        for combo_name, combo_info in vaccine_grouper.combination_vaccines.items():
            if combo_info['components'].issubset(vaccine_names):
                return combo_name
    return None 