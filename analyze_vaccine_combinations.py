import sqlite3
from collections import defaultdict
from datetime import datetime
import pandas as pd
from typing import Dict, List, Tuple
import os

def get_db_connection():
    """Create a database connection"""
    db_path = os.path.expanduser('~/Documents/UnifiedEMR/unified_emr.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_vaccine_combinations() -> Dict[str, List[Tuple[str, str]]]:
    """
    Get all vaccine combinations given on the same date for each patient.
    Returns a dictionary mapping dates to lists of (vaccine_name, patient_id) tuples.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all vaccine records with dates
    cursor.execute("""
        SELECT patient_id, immunization, administered_date
        FROM Immunizations
        WHERE administered_date IS NOT NULL
        ORDER BY administered_date
    """)
    
    # Group vaccines by date and patient
    date_groups = defaultdict(list)
    for row in cursor.fetchall():
        date_groups[(row['administered_date'], row['patient_id'])].append(row['immunization'])
    
    conn.close()
    return date_groups

def analyze_combinations(date_groups: Dict[str, List[Tuple[str, str]]]) -> pd.DataFrame:
    """
    Analyze the frequency of vaccine combinations.
    Returns a DataFrame with combination frequencies.
    """
    # Count occurrences of each combination
    combination_counts = defaultdict(int)
    for vaccines in date_groups.values():
        if len(vaccines) > 1:  # Only look at combinations of 2 or more vaccines
            # Sort vaccines to ensure consistent ordering
            combination = tuple(sorted(vaccines))
            combination_counts[combination] += 1
    
    # Convert to DataFrame
    combinations = []
    for combo, count in combination_counts.items():
        combinations.append({
            'vaccines': ' + '.join(combo),
            'frequency': count,
            'vaccine_count': len(combo)
        })
    
    df = pd.DataFrame(combinations)
    if not df.empty:
        df = df.sort_values('frequency', ascending=False)
    
    return df

def main():
    print("Analyzing vaccine combinations...")
    
    # Get vaccine combinations
    date_groups = get_vaccine_combinations()
    
    # Analyze combinations
    df = analyze_combinations(date_groups)
    
    if df.empty:
        print("No vaccine combinations found.")
        return
    
    # Print results
    print("\nMost common vaccine combinations:")
    print("=================================")
    for _, row in df.iterrows():
        print(f"\n{row['vaccines']}")
        print(f"Frequency: {row['frequency']} times")
        print(f"Number of vaccines in combination: {row['vaccine_count']}")

if __name__ == "__main__":
    main() 