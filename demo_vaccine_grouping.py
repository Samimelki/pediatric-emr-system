#!/usr/bin/env python3
"""
Demonstration of vaccine grouping for timeline display vs PDF export

This script shows how we can:
1. Group vaccines for simplified timeline display (Hexaxim/Pentaxim)
2. Keep individual vaccines for detailed PDF export
3. Maintain clinical accuracy while improving UX
"""

import sqlite3
import os
from utils.vaccine_grouping import vaccine_grouper, VaccineGroup
from typing import List, Dict

def get_db_connection():
    """Create a database connection"""
    db_path = os.path.expanduser('~/Documents/UnifiedEMR/unified_emr.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_patient_vaccines(patient_id: int) -> tuple:
    """Get patient vaccines and DOB"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get patient DOB
    cursor.execute("SELECT naissance_date FROM Patients WHERE id = ?", (patient_id,))
    dob_result = cursor.fetchone()
    if not dob_result:
        return None, []
    
    patient_dob = dob_result[0]
    
    # Get vaccines
    cursor.execute("""
        SELECT patient_id, immunization, administered_date, dose_number
        FROM Immunizations
        WHERE patient_id = ? AND administered_date IS NOT NULL
        ORDER BY administered_date
    """, (patient_id,))
    
    vaccines = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return patient_dob, vaccines

def demonstrate_timeline_vs_pdf(patient_id: int):
    """Demonstrate how timeline and PDF views would differ"""
    print(f"\n=== PATIENT {patient_id} VACCINE DISPLAY COMPARISON ===")
    
    patient_dob, vaccines = get_patient_vaccines(patient_id)
    if not patient_dob:
        print(f"Patient {patient_id} not found")
        return
    
    print(f"Patient DOB: {patient_dob}")
    print(f"Total vaccine records: {len(vaccines)}")
    
    # Get grouped vaccines
    grouped_vaccines = vaccine_grouper.group_vaccines_by_date_and_patient(vaccines, patient_dob)
    patient_groups = grouped_vaccines.get(patient_id, [])
    
    # Sort by date
    patient_groups.sort(key=lambda x: x.administered_date)
    
    print(f"\n📱 TIMELINE VIEW (Simplified for Dashboard):")
    print(f"{'Date':<12} {'Age':<6} {'Vaccine':<35} {'Type'}")
    print("-" * 70)
    
    for group in patient_groups:
        vaccine_type = "🔗 Combination" if len(group.component_vaccines) > 1 else "💉 Single"
        print(f"{group.administered_date:<12} {group.age_display:<6} {group.display_name:<35} {vaccine_type}")
    
    print(f"\n📄 PDF EXPORT VIEW (Detailed for Clinical Records):")
    print(f"{'Date':<12} {'Age':<6} {'Vaccine':<35} {'Dose'}")
    print("-" * 70)
    
    # For PDF, we show individual vaccines from the original records
    for group in patient_groups:
        for record in group.individual_records:
            dose_info = f"Dose {record.get('dose_number', 1)}"
            print(f"{record['administered_date']:<12} {group.age_display:<6} {record['immunization']:<35} {dose_info}")
    
    # Show the benefit
    original_count = len(vaccines)
    grouped_count = len(patient_groups)
    reduction = ((original_count - grouped_count) / original_count * 100) if original_count > 0 else 0
    
    print(f"\n📊 SUMMARY:")
    print(f"Original vaccine entries: {original_count}")
    print(f"Grouped timeline entries: {grouped_count}")
    print(f"Timeline simplification: {reduction:.1f}% reduction")
    
    # Show combinations found
    combinations = [g for g in patient_groups if len(g.component_vaccines) > 1]
    if combinations:
        print(f"Combinations identified: {len(combinations)}")
        for combo in combinations:
            print(f"  • {combo.display_name} on {combo.administered_date}")

def find_best_examples():
    """Find patients with good examples of combinations"""
    print("🔍 FINDING PATIENTS WITH COMBINATION VACCINES...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Find patients with Hexaxim combinations
    cursor.execute("""
        SELECT patient_id, administered_date, COUNT(*) as vaccine_count
        FROM Immunizations 
        WHERE immunization IN ('DTaP - IPV', 'Hib (Haemophilus influenzae b)', 'Hepatitis B')
        AND administered_date IS NOT NULL
        GROUP BY patient_id, administered_date
        HAVING COUNT(*) = 3
        ORDER BY administered_date DESC
        LIMIT 5
    """)
    
    hexaxim_examples = cursor.fetchall()
    
    # Find patients with Pentaxim combinations
    cursor.execute("""
        SELECT patient_id, administered_date, COUNT(*) as vaccine_count
        FROM Immunizations 
        WHERE immunization IN ('DTaP - IPV', 'Hib (Haemophilus influenzae b)')
        AND administered_date IS NOT NULL
        GROUP BY patient_id, administered_date
        HAVING COUNT(*) = 2
        AND patient_id NOT IN (
            SELECT DISTINCT patient_id FROM Immunizations 
            WHERE immunization = 'Hepatitis B' 
            AND administered_date = Immunizations.administered_date
        )
        ORDER BY administered_date DESC
        LIMIT 3
    """)
    
    pentaxim_examples = cursor.fetchall()
    conn.close()
    
    print(f"\nFound {len(hexaxim_examples)} Hexaxim examples:")
    for example in hexaxim_examples:
        print(f"  Patient {example[0]} on {example[1]}")
    
    print(f"\nFound {len(pentaxim_examples)} Pentaxim examples:")
    for example in pentaxim_examples:
        print(f"  Patient {example[0]} on {example[1]}")
    
    return hexaxim_examples, pentaxim_examples

def main():
    """Main demonstration"""
    print("🧬 VACCINE GROUPING DEMONSTRATION")
    print("=" * 50)
    print("This demo shows how we can simplify vaccine timelines")
    print("while preserving detailed clinical records for PDF export.")
    
    # Find good examples
    hexaxim_examples, pentaxim_examples = find_best_examples()
    
    # Demo with Hexaxim example
    if hexaxim_examples:
        patient_id = hexaxim_examples[0][0]
        demonstrate_timeline_vs_pdf(patient_id)
    
    # Demo with Pentaxim example if we have one
    if pentaxim_examples:
        patient_id = pentaxim_examples[0][0]
        demonstrate_timeline_vs_pdf(patient_id)
    
    print(f"\n✅ IMPLEMENTATION BENEFITS:")
    print(f"• Cleaner timeline view with combination vaccines")
    print(f"• Maintains individual vaccine records for clinical accuracy")
    print(f"• Reduces visual clutter in dashboard")
    print(f"• Preserves detailed information for PDF exports")
    print(f"• Reflects real-world vaccine administration patterns")

if __name__ == "__main__":
    main() 