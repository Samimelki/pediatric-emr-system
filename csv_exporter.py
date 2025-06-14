import csv
import io

def generate_patient_csvs(patients_data, active_custom_fields_metadata):
    """
    Generates multiple CSV strings from patient data.
    - patients_data: List of patient dictionaries.
    - active_custom_fields_metadata: List of dictionaries for active custom fields 
                                     (from database.get_active_custom_demographic_fields).
    Returns: A dictionary {filename: csv_string}.
    """
    csv_files = {}

    # --- Generate patients.csv ---
    patients_output = io.StringIO()
    # Define standard patient headers (order can be adjusted)
    # Exclude complex nested data like 'visits', 'non_standard_vaccines', 'custom_fields' dict itself
    # Also exclude raw text fields if they are too large or not typically needed in a summary CSV
    standard_patient_headers = [
        'id', 'mrn', 'mrn_agg', 'nom', 'prenom', 'naissance_date', 'sexe', 
        'birth_weight_g', 'birth_height_cm', 'birth_head_circumference_cm', 'birth_notes',
        'mere_nom', 'pere_nom', 'pediatre_initiales', 'domicile', 'telephone', 
        'third_party_payer', 'hopital', 'diag1', 'diag2', 'obstetrical_history',
        'monotest1', 'monotest2', 'monotest3', 'rougeole_seule_date',
        'dtcp1_date', 'dtcp2_date', 'dtcp3_date', 'dtcp_rappel1_date', 'dtcp_rappel2_date', 
        'dtcp_rappel3_date', 'dtcp_rappel4_date', 'hep_b1_date', 'hep_b2_date', 'hep_b3_date',
        'hib1_date', 'hib2_date', 'hib3_date', 'hib_rappel_date', 'ror_date'
        # 'raw_dossier_text', 'raw_autres_vaccins_text' # Often too large for a summary CSV
    ]
    
    custom_field_headers = [cf['field_label'] for cf in active_custom_fields_metadata] # Use label for header
    custom_field_internal_names = [cf['field_name'] for cf in active_custom_fields_metadata]

    patients_csv_writer = csv.writer(patients_output)
    patients_csv_writer.writerow(standard_patient_headers + custom_field_headers)

    for p_dict in patients_data:
        row = [p_dict.get(header) for header in standard_patient_headers]
        
        # Add custom field values
        # The 'custom_fields' in p_dict is a list of dicts: [{'field_name': ..., 'value': ...}]
        # We need to map these to the order of custom_field_internal_names
        
        # Create a quick lookup for the current patient's custom field values
        current_patient_custom_values = {cf_data['field_name']: cf_data['value'] 
                                         for cf_data in p_dict.get('custom_fields', [])}
                                         
        for internal_name in custom_field_internal_names:
            row.append(current_patient_custom_values.get(internal_name)) # Appends None if not found
            
        patients_csv_writer.writerow(row)
    
    csv_files['patients.csv'] = patients_output.getvalue()
    patients_output.close()

    # --- Generate visits.csv ---
    visits_output = io.StringIO()
    # Define visit headers (ensure patient_id or mrn is first for linking)
    visit_headers = ['patient_id', 'patient_mrn', 'id', 'visit_date', 'weight_g', 'height_cm', 'head_circumference_cm', 'notes', 'raw_visit_entry']
    visits_csv_writer = csv.writer(visits_output)
    visits_csv_writer.writerow(visit_headers)

    for p_dict in patients_data:
        patient_id = p_dict.get('id')
        patient_mrn = p_dict.get('mrn')
        for visit in p_dict.get('visits', []):
            row = [
                patient_id,
                patient_mrn,
                visit.get('id'),
                visit.get('visit_date'),
                visit.get('weight_g'),
                visit.get('height_cm'),
                visit.get('head_circumference_cm'),
                visit.get('notes'),
                visit.get('raw_visit_entry')
            ]
            visits_csv_writer.writerow(row)
    
    csv_files['visits.csv'] = visits_output.getvalue()
    visits_output.close()

    # --- Generate immunizations.csv ---
    immunizations_output = io.StringIO()
    # Define immunization headers (ensure patient_id or mrn is first)
    immunization_headers = ['patient_id', 'patient_mrn', 'id', 'immunization', 'administered_date', 'brand_name', 'dose_number', 'notes', 'source', 'created_at']
    immunizations_csv_writer = csv.writer(immunizations_output)
    immunizations_csv_writer.writerow(immunization_headers)

    for p_dict in patients_data:
        patient_id = p_dict.get('id')
        patient_mrn = p_dict.get('mrn')
        for immunization in p_dict.get('immunizations', []):
            row = [
                patient_id,
                patient_mrn,
                immunization.get('id'),
                immunization.get('immunization'),
                immunization.get('administered_date'),
                immunization.get('brand_name'),
                immunization.get('dose_number'),
                immunization.get('notes'),
                immunization.get('source'),
                immunization.get('created_at')
            ]
            immunizations_csv_writer.writerow(row)

    csv_files['immunizations.csv'] = immunizations_output.getvalue()
    immunizations_output.close()

    return csv_files

if __name__ == '__main__':
    # Example usage (for testing - requires dummy data similar to what database.py produces)
    print("CSV Exporter module. Not meant to be run directly for full functionality.")
    # dummy_custom_fields_meta = [
    #     {'field_label': 'Nationality', 'field_name': 'custom_nationality'},
    #     {'field_label': 'Blood Type', 'field_name': 'custom_blood_type'},
    # ]
    # dummy_patients_data = [
    #     {
    #         'id': 1, 'mrn': 'MRN001', 'nom': 'Doe', 'prenom': 'John', 
    #         'custom_fields': [
    #             {'field_name': 'custom_nationality', 'value': 'US'},
    #             {'field_name': 'custom_blood_type', 'value': 'O+'}
    #         ],
    #         'visits': [{'id': 101, 'patient_id': 1, 'visit_date': '2023-01-01', 'weight_g': 5000}],
    #         'non_standard_vaccines': [{'id': 201, 'patient_id': 1, 'vaccine_name': 'FluX', 'vaccine_date': '2023-01-01'}]
    #     },
    #     {
    #         'id': 2, 'mrn': 'MRN002', 'nom': 'Smith', 'prenom': 'Jane',
    #         'custom_fields': [{'field_name': 'custom_nationality', 'value': 'CA'}], # No blood type
    #         'visits': [],
    #         'non_standard_vaccines': []
    #     }
    # ]
    # generated_csvs = generate_patient_csvs(dummy_patients_data, dummy_custom_fields_meta)
    # for filename, content in generated_csvs.items():
    #     print(f"--- {filename} ---")
    #     print(content)
    #     print("\n") 