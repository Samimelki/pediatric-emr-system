#!/usr/bin/env python3
import sqlite3
from utils.vaccine_schedule_engine import get_patient_vaccine_timeline

# Get patient data
conn = sqlite3.connect('/Users/samimelki/Documents/UnifiedEMR/unified_emr.db')
conn.row_factory = sqlite3.Row
patient_row = conn.execute('SELECT * FROM Patients WHERE mrn = ?', ('01675',)).fetchone()
patient = dict(patient_row)
autres_vaccins_rows = conn.execute('SELECT * FROM NonStandardVaccines WHERE patient_id = ?', (patient['id'],)).fetchall()
autres_vaccins = [dict(row) for row in autres_vaccins_rows]
conn.close()

print(f"Patient: {patient['prenom']} {patient['nom']}")
print(f"Standard vaccine dates from database:")
print(f"  dtcp1_date: {patient.get('dtcp1_date')}")
print(f"  dtcp2_date: {patient.get('dtcp2_date')}")
print(f"  hep_b1_date: {patient.get('hep_b1_date')}")
print(f"  hep_b2_date: {patient.get('hep_b2_date')}")
print(f"  ror_date: {patient.get('ror_date')}")

# Test timeline
print(f"\nGenerating timeline...")
timeline = get_patient_vaccine_timeline(patient['naissance_date'], patient, autres_vaccins)

print(f"\nTimeline results for key vaccines:")
for vaccine in timeline:
    if vaccine.vaccine_name in ['DTaP - IPV', 'Hepatitis B', 'MMR (Measles, Mumps, Rubella)']:
        completed = [d for d in vaccine.doses if d.status.value == 'completed']
        print(f"\n{vaccine.vaccine_name} ({vaccine.category}):")
        print(f"  Total doses: {len(vaccine.doses)}")
        print(f"  Completed: {len(completed)}")
        
        if len(completed) > 0:
            for dose in vaccine.doses:
                if dose.status.value == 'completed':
                    print(f"    {dose.label}: COMPLETED on {dose.completed_date}")
        else:
            print(f"    ❌ NO DOSES SHOWING AS COMPLETED")
            # Show first few doses for debugging
            for dose in vaccine.doses[:3]:
                print(f"    {dose.label}: {dose.status.value} (due: {dose.due_date})") 