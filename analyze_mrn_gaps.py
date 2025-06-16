#!/usr/bin/env python3

import sqlite3
import emr_config

def analyze_mrn_gaps():
    """Analyze MRN numbering patterns and identify gaps"""
    
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Analyzing MRN numbering patterns...")
    print("=" * 60)
    
    # Get all MRNs and sort them
    cursor.execute("SELECT id, mrn, first_name, last_name FROM Patients ORDER BY CAST(mrn AS INTEGER)")
    patients = cursor.fetchall()
    
    print(f"Total patients in database: {len(patients)}")
    
    # Convert MRNs to integers for analysis
    mrn_numbers = []
    mrn_to_patient = {}
    
    for patient in patients:
        db_id, mrn, first_name, last_name = patient
        try:
            mrn_num = int(mrn)
            mrn_numbers.append(mrn_num)
            mrn_to_patient[mrn_num] = {
                'db_id': db_id,
                'mrn': mrn,
                'name': f"{first_name} {last_name}"
            }
        except ValueError:
            print(f"Non-numeric MRN found: '{mrn}' for {first_name} {last_name}")
    
    mrn_numbers.sort()
    
    print(f"Numeric MRNs found: {len(mrn_numbers)}")
    print(f"Lowest MRN: {mrn_numbers[0] if mrn_numbers else 'None'}")
    print(f"Highest MRN: {mrn_numbers[-1] if mrn_numbers else 'None'}")
    
    # Find gaps in MRN sequence
    gaps = []
    expected_mrn = mrn_numbers[0] if mrn_numbers else 1
    
    for mrn in mrn_numbers:
        if mrn > expected_mrn:
            # Found a gap
            gap_start = expected_mrn
            gap_end = mrn - 1
            gaps.append((gap_start, gap_end))
            expected_mrn = mrn + 1
        elif mrn == expected_mrn:
            expected_mrn = mrn + 1
        # If mrn < expected_mrn, it's a duplicate (shouldn't happen with unique constraint)
    
    print(f"\nGaps found in MRN sequence: {len(gaps)}")
    
    if gaps:
        print("\nFirst 20 gaps:")
        total_missing = 0
        for i, (start, end) in enumerate(gaps[:20]):
            gap_size = end - start + 1
            total_missing += gap_size
            if start == end:
                print(f"  Gap {i+1}: Missing MRN {start}")
            else:
                print(f"  Gap {i+1}: Missing MRNs {start}-{end} ({gap_size} numbers)")
        
        if len(gaps) > 20:
            remaining_gaps = gaps[20:]
            remaining_missing = sum(end - start + 1 for start, end in remaining_gaps)
            total_missing += remaining_missing
            print(f"  ... and {len(remaining_gaps)} more gaps ({remaining_missing} missing MRNs)")
        
        print(f"\nTotal missing MRNs in sequence: {total_missing}")
        print(f"Expected total if no gaps: {mrn_numbers[-1] - mrn_numbers[0] + 1}")
        print(f"Actual patients: {len(mrn_numbers)}")
    
    # Check for duplicate MRNs (shouldn't exist due to unique constraint)
    cursor.execute("SELECT mrn, COUNT(*) FROM Patients GROUP BY mrn HAVING COUNT(*) > 1")
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"\nDuplicate MRNs found: {len(duplicates)}")
        for mrn, count in duplicates:
            print(f"  MRN '{mrn}' appears {count} times")
    else:
        print("\nNo duplicate MRNs found (good!)")
    
    # Show some examples around the "missing" patient IDs we found earlier
    missing_csv_ids = [4635, 10242, 10521, 10676, 10691, 10708, 10726, 10772, 11005, 11196, 11204]
    
    print(f"\nChecking MRNs around the 'missing' CSV patient IDs:")
    for csv_id in missing_csv_ids[:5]:  # Check first 5
        # Find patients with MRNs near this CSV ID
        cursor.execute("""
            SELECT id, mrn, first_name, last_name 
            FROM Patients 
            WHERE CAST(mrn AS INTEGER) BETWEEN ? AND ? 
            ORDER BY CAST(mrn AS INTEGER)
        """, (csv_id - 2, csv_id + 2))
        nearby = cursor.fetchall()
        
        print(f"\n  Around CSV ID {csv_id}:")
        for patient in nearby:
            db_id, mrn, first_name, last_name = patient
            print(f"    DB ID {db_id}, MRN {mrn}: {first_name} {last_name}")
    
    conn.close()

if __name__ == "__main__":
    analyze_mrn_gaps() 