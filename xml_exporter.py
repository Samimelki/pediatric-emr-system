import xml.etree.ElementTree as ET
# from xml.dom import minidom # Removed for performance

def _get_text(value):
    """Converts a value to a string, handling None by returning an empty string."""
    if value is None:
        return ""
    return str(value)

def generate_patient_xml(patients_data):
    """
    Generates an XML string from a list of patient data dictionaries.
    patients_data: List of dictionaries, where each dict contains full patient info.
    """
    root_element = ET.Element("PediatricEMRData")
    root_element.set("version", "1.0")

    for patient_dict in patients_data:
        patient_element = ET.SubElement(root_element, "Patient")
        
        # Add standard patient fields as sub-elements
        standard_fields = {k: v for k, v in patient_dict.items() if k not in ['custom_fields', 'visits', 'non_standard_vaccines']}
        for key, value in standard_fields.items():
            field_element = ET.SubElement(patient_element, key.replace("_", "-")) # Use hyphens for XML tags
            field_element.text = _get_text(value)

        # Add custom fields
        if patient_dict.get('custom_fields'):
            custom_fields_element = ET.SubElement(patient_element, "CustomFields")
            for cf_data in patient_dict['custom_fields']:
                custom_field_el = ET.SubElement(custom_fields_element, "CustomField")
                custom_field_el.set("fieldName", cf_data['field_name'])
                custom_field_el.set("fieldLabel", cf_data['field_label'])
                custom_field_el.set("fieldType", cf_data['type'])
                custom_field_el.text = _get_text(cf_data['value'])

        # Add visits
        if patient_dict.get('visits'):
            visits_element = ET.SubElement(patient_element, "Visits")
            for visit_data in patient_dict['visits']:
                visit_el = ET.SubElement(visits_element, "Visit")
                for key, value in visit_data.items():
                    field_element = ET.SubElement(visit_el, key.replace("_", "-"))
                    field_element.text = _get_text(value)
        
        # Add non-standard vaccines
        if patient_dict.get('non_standard_vaccines'):
            non_std_vaccines_element = ET.SubElement(patient_element, "NonStandardVaccines")
            for vaccine_data in patient_dict['non_standard_vaccines']:
                vaccine_el = ET.SubElement(non_std_vaccines_element, "Vaccine")
                for key, value in vaccine_data.items():
                    field_element = ET.SubElement(vaccine_el, key.replace("_", "-"))
                    field_element.text = _get_text(value)

    # Convert ElementTree to a string
    # rough_string = ET.tostring(root_element, 'utf-8') # Original before minidom
    # reparsed = minidom.parseString(rough_string)
    # return reparsed.toprettyxml(indent="  ", encoding="UTF-8").decode('utf-8') # This is slow
    
    # Return non-pretty printed XML for performance
    return ET.tostring(root_element, encoding="UTF-8", xml_declaration=True).decode('utf-8')

if __name__ == '__main__':
    # Example Usage (requires being run in an environment where database.py can be imported and Flask app context is available)
    # This is just for standalone testing of this module, not part of the main app flow.
    print("This module is intended to be used by the main application.")
    print("To test, you would need to simulate patient_data or integrate with the app context.")
    
    # Basic test with dummy data:
    # dummy_patients = [
    #     {
    #         'id': 1, 'mrn': 'P001', 'nom': 'Doe', 'prenom': 'John', 'naissance_date': '2020-01-01',
    #         'custom_fields': [
    #             {'field_name': 'custom_nationality', 'field_label': 'Nationality', 'value': 'US', 'type': 'TEXT'}
    #         ],
    #         'visits': [
    #             {'id': 101, 'patient_id': 1, 'visit_date': '2020-02-01', 'weight_g': 3500}
    #         ],
    #         'non_standard_vaccines': [
    #             {'id': 201, 'patient_id': 1, 'vaccine_name': 'Flu Shot', 'vaccine_date': '2020-09-15'}
    #         ]
    #     }
    # ]
    # xml_output = generate_patient_xml(dummy_patients)
    # print("\nGenerated XML (dummy data):\n", xml_output) 