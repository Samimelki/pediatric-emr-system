#!/usr/bin/env python3
"""
Core Immunization Service

Unified service for all immunization operations, replacing separate
vaccine tracking systems with a single source of truth.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from .models import (
    ImmunizationRecord, ImmunizationDose, ImmunizationScheduleItem,
    PatientImmunizationSummary, ImmunizationAdministration,
    ImmunizationStatus, ImmunizationCategory
)
from .config_service import ImmunizationConfigService
from .database_manager import get_db_manager

class ImmunizationService:
    """Core service for all immunization operations"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or '/Users/samimelki/Documents/UnifiedEMR/unified_emr.db'
        self.config_service = ImmunizationConfigService()
        self.db_manager = get_db_manager(self.db_path)
    
    def get_patient_immunizations(self, patient_id: int) -> List[ImmunizationRecord]:
        """Get all immunization records for a patient"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT id, patient_id, immunization, administered_date, 
                           brand_name, dose_number, notes, source, 
                           created_at, updated_at
                    FROM Immunizations 
                    WHERE patient_id = ?
                    ORDER BY immunization, dose_number
                """, (patient_id,))
                
                records = []
                for row in cursor.fetchall():
                    record = ImmunizationRecord(
                        id=row['id'],
                        patient_id=row['patient_id'],
                        immunization=row['immunization'],
                        administered_date=row['administered_date'], 
                        brand_name=row['brand_name'],
                        dose_number=row['dose_number'],
                        notes=row['notes'],
                        source=row['source'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    records.append(record)
                
                return records
        except sqlite3.Error as e:
            print(f"Database error in get_patient_immunizations: {e}")
            return []
    
    def get_patient_immunization_summary(self, patient_id: int, patient_dob: str) -> PatientImmunizationSummary:
        """Get complete immunization summary for a patient"""
        # Get all immunization records
        records = self.get_patient_immunizations(patient_id)
        
        # Group records by immunization type
        records_by_immunization = {}
        for record in records:
            if record.immunization not in records_by_immunization:
                records_by_immunization[record.immunization] = []
            records_by_immunization[record.immunization].append(record)
        
        # Calculate schedule for each immunization
        schedule_items = []
        total_doses = 0
        completed_doses = 0
        due_doses = 0
        overdue_doses = 0
        
        # Get current date
        current_date = datetime.now()
        patient_dob_obj = datetime.strptime(patient_dob, '%Y-%m-%d')
        
        # Process each immunization from comprehensive mapping
        for immunization, disease_info in self.config_service.comprehensive_mapping.items():
            category = ImmunizationCategory(disease_info.get('category', 'recommended'))
            dose_schedule = disease_info.get('doses', [])
            
            if not dose_schedule:
                continue
            
            # Get patient's records for this immunization
            patient_records = records_by_immunization.get(immunization, [])
            patient_records.sort(key=lambda r: r.administered_date)
            
            # Calculate doses
            doses = []
            for i, dose_info in enumerate(dose_schedule):
                dose_number = i + 1
                age_months = self._parse_age_to_months(dose_info.get('age', '0M'))
                age_display = dose_info.get('age', f'{dose_number}')
                
                # Calculate due dates
                due_date = patient_dob_obj + timedelta(days=age_months * 30.44)  # Average month
                overdue_date = due_date + timedelta(days=30)  # 1 month grace period
                
                # Check if this dose is administered
                administered_record = None
                if dose_number <= len(patient_records):
                    administered_record = patient_records[dose_number - 1]
                
                # Determine status
                if administered_record:
                    status = ImmunizationStatus.COMPLETED
                    administered_date = administered_record.administered_date
                    brand_name = administered_record.brand_name
                    record_id = administered_record.id
                    completed_doses += 1
                elif current_date >= overdue_date:
                    status = ImmunizationStatus.OVERDUE
                    administered_date = None
                    brand_name = None
                    record_id = None
                    overdue_doses += 1
                elif current_date >= due_date:
                    status = ImmunizationStatus.DUE
                    administered_date = None
                    brand_name = None
                    record_id = None
                    due_doses += 1
                elif (due_date - current_date).days <= 30:  # Upcoming within 30 days
                    status = ImmunizationStatus.UPCOMING
                    administered_date = None
                    brand_name = None
                    record_id = None
                else:
                    status = ImmunizationStatus.NOT_APPLICABLE
                    administered_date = None
                    brand_name = None
                    record_id = None
                
                # Calculate days until due/overdue
                days_until_due = (due_date - current_date).days if status == ImmunizationStatus.UPCOMING else None
                days_overdue = (current_date - overdue_date).days if status == ImmunizationStatus.OVERDUE else None
                
                dose = ImmunizationDose(
                    dose_number=dose_number,
                    label=f"Dose {dose_number}" if dose_number <= 3 else f"Booster {dose_number - 3}",
                    age_months=age_months,
                    age_display=age_display,
                    status=status,
                    due_date=due_date.strftime('%Y-%m-%d'),
                    overdue_date=overdue_date.strftime('%Y-%m-%d'),
                    administered_date=administered_date,
                    brand_name=brand_name,
                    days_until_due=days_until_due,
                    days_overdue=days_overdue,
                    record_id=record_id
                )
                doses.append(dose)
                total_doses += 1
            
            # Find next due dose
            next_due_dose = None
            for dose in doses:
                if dose.status in [ImmunizationStatus.DUE, ImmunizationStatus.OVERDUE, ImmunizationStatus.UPCOMING]:
                    next_due_dose = dose
                    break
            
            # Calculate completion percentage
            immunization_completed = len([d for d in doses if d.status == ImmunizationStatus.COMPLETED])
            completion_percentage = (immunization_completed / len(doses) * 100) if doses else 0
            
            schedule_item = ImmunizationScheduleItem(
                immunization=immunization,
                category=category,
                doses=doses,
                completion_percentage=completion_percentage,
                total_doses=len(doses),
                completed_doses=immunization_completed,
                next_due_dose=next_due_dose
            )
            schedule_items.append(schedule_item)
        
        # Calculate category-specific completion rates
        mandatory_items = [item for item in schedule_items if item.category == ImmunizationCategory.MANDATORY]
        recommended_items = [item for item in schedule_items if item.category == ImmunizationCategory.RECOMMENDED]
        travel_items = [item for item in schedule_items if item.category == ImmunizationCategory.TRAVEL]
        
        mandatory_completion = self._calculate_category_completion(mandatory_items)
        recommended_completion = self._calculate_category_completion(recommended_items)
        travel_completion = self._calculate_category_completion(travel_items)
        
        overall_completion = (completed_doses / total_doses * 100) if total_doses > 0 else 0
        
        return PatientImmunizationSummary(
            patient_id=patient_id,
            total_immunizations=len(schedule_items),
            total_doses=total_doses,
            completed_doses=completed_doses,
            due_doses=due_doses,
            overdue_doses=overdue_doses,
            completion_percentage=overall_completion,
            immunizations=schedule_items,
            mandatory_completion=mandatory_completion,
            recommended_completion=recommended_completion,
            travel_completion=travel_completion
        )
    
    def add_immunization(self, administration: ImmunizationAdministration) -> int:
        """Add a new immunization record"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Auto-calculate dose number if not provided
                if administration.dose_number is None:
                    cursor.execute("""
                        SELECT COALESCE(MAX(dose_number), 0) + 1
                        FROM Immunizations 
                        WHERE patient_id = ? AND immunization = ?
                    """, (administration.patient_id, administration.immunization))
                    result = cursor.fetchone()
                    administration.dose_number = result[0] if result else 1
                
                cursor.execute("""
                    INSERT INTO Immunizations 
                    (patient_id, immunization, administered_date, brand_name, 
                     dose_number, notes, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    administration.patient_id,
                    administration.immunization,
                    administration.administered_date,
                    administration.brand_name,
                    administration.dose_number,
                    administration.notes,
                    administration.source
                ))
                
                record_id = cursor.lastrowid
                conn.commit()  # Explicitly commit the transaction
                return record_id
        except sqlite3.Error as e:
            print(f"Database error in add_immunization: {e}")
            raise
    
    def update_immunization(self, record_id: int, administered_date: str, 
                          brand_name: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update an existing immunization record"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE Immunizations 
                    SET administered_date = ?, brand_name = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (administered_date, brand_name, notes, record_id))
                
                result = cursor.rowcount > 0
                conn.commit()  # Explicitly commit the transaction
                return result
        except sqlite3.Error as e:
            print(f"Database error in update_immunization: {e}")
            return False
    
    def delete_immunization(self, record_id: int) -> bool:
        """Delete an immunization record"""
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("DELETE FROM Immunizations WHERE id = ?", (record_id,))
                result = cursor.rowcount > 0
                conn.commit()  # Explicitly commit the transaction
                return result
        except sqlite3.Error as e:
            print(f"Database error in delete_immunization: {e}")
            return False
    
    def _parse_age_to_months(self, age_str: str) -> int:
        """Parse age string to months"""
        if age_str == "Birth":
            return 0
        
        # Handle compound ages like "1Y6M"
        if 'Y' in age_str and 'M' in age_str:
            parts = age_str.replace('Y', 'Y ').replace('M', 'M ').split()
            months = 0
            for part in parts:
                if part.endswith('Y'):
                    months += int(part[:-1]) * 12
                elif part.endswith('M'):
                    months += int(part[:-1])
            return months
        
        # Handle simple ages
        if age_str.endswith('M'):
            return int(age_str[:-1])
        elif age_str.endswith('Y'):
            return int(age_str[:-1]) * 12
        
        return 0
    
    def _calculate_category_completion(self, items: List[ImmunizationScheduleItem]) -> float:
        """Calculate completion percentage for a category of immunizations"""
        if not items:
            return 100.0
        
        total_doses = sum(item.total_doses for item in items)
        completed_doses = sum(item.completed_doses for item in items)
        
        return (completed_doses / total_doses * 100) if total_doses > 0 else 100.0

# Global instance
immunization_service = ImmunizationService() 