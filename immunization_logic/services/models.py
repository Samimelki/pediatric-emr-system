#!/usr/bin/env python3
"""
Immunization Data Models

Clean data models for the unified immunization system
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from enum import Enum

class ImmunizationStatus(Enum):
    """Status of an immunization dose"""
    COMPLETED = "completed"
    DUE = "due"
    OVERDUE = "overdue"
    UPCOMING = "upcoming"
    NOT_APPLICABLE = "not_applicable"

class ImmunizationCategory(Enum):
    """Category of immunization"""
    MANDATORY = "mandatory"
    RECOMMENDED = "recommended"
    TRAVEL = "travel"

@dataclass
class ImmunizationRecord:
    """Individual immunization record from database"""
    patient_id: int
    immunization: str              # Canonical disease name
    administered_date: str         # YYYY-MM-DD format
    source: str = "manual"         # 'import', 'manual', 'migration'
    id: Optional[int] = None       # Database ID (auto-generated)
    brand_name: Optional[str] = None      # Original vaccine brand
    dose_number: Optional[int] = None     # Dose sequence
    notes: Optional[str] = None           # Provider notes
    created_at: Optional[str] = None      # Auto-generated timestamp
    updated_at: Optional[str] = None      # Auto-generated timestamp

@dataclass
class ImmunizationDose:
    """Single dose in an immunization schedule"""
    dose_number: int
    label: str                     # "Dose 1", "Booster 1", etc.
    age_months: int                # When due (in months from birth)
    age_display: str               # "2M", "1Y6M", etc.
    status: ImmunizationStatus
    due_date: Optional[str] = None          # When due for this patient
    overdue_date: Optional[str] = None      # When becomes overdue
    administered_date: Optional[str] = None # When actually given
    brand_name: Optional[str] = None        # Brand used if administered
    days_until_due: Optional[int] = None    # Days until due
    days_overdue: Optional[int] = None      # Days overdue
    record_id: Optional[int] = None         # Database record ID if administered

@dataclass
class ImmunizationScheduleItem:
    """Complete immunization schedule item for a patient"""
    immunization: str              # Canonical disease name
    category: ImmunizationCategory
    doses: List[ImmunizationDose]
    completion_percentage: float   # 0-100
    total_doses: int
    completed_doses: int
    next_due_dose: Optional[ImmunizationDose] = None

@dataclass
class PatientImmunizationSummary:
    """Summary of patient's immunization status"""
    patient_id: int
    total_immunizations: int
    total_doses: int
    completed_doses: int
    due_doses: int
    overdue_doses: int
    completion_percentage: float
    immunizations: List[ImmunizationScheduleItem]
    
    # Category breakdowns
    mandatory_completion: float
    recommended_completion: float
    travel_completion: float

@dataclass
class ImmunizationAdministration:
    """Data for administering a new immunization"""
    patient_id: int
    immunization: str              # Canonical disease name
    administered_date: str         # YYYY-MM-DD
    brand_name: Optional[str] = None        # Optional brand name
    dose_number: Optional[int] = None       # Auto-calculated if None
    notes: Optional[str] = None             # Provider notes
    source: str = "manual"                  # Source of entry 