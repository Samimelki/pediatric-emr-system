import sqlite3
import json
from xml_parser import parse_excel_xml, parse_date_to_iso, parse_memo_text
from unified_database import save_patient_unified, get_db
# from emr_config import EMRMode  # No longer needed with profile-based system
import datetime
from word_document_manager import WordDocumentManager
from emr_config import emr_config

# Header mapping for XML to unified database fields
HEADER_TO_DB_MAP = {
    '/fichier/n/#agg': {'db_col': 'mrn_agg', 'type': 'text'},
    '/fichier/nom': {'db_col': 'nom', 'type': 'text'},
    '/fichier/prenom': {'db_col': 'prenom', 'type': 'text'},
    '/fichier/naissance': {'db_col': 'naissance_date', 'type': 'datetime_to_date'},
    '/fichier/sexe': {'db_col': 'sexe', 'type': 'text'},
    '/fichier/mere': {'db_col': 'mere_nom', 'type': 'text'},
    '/fichier/pere': {'db_col': 'pere_nom', 'type': 'text'},
    '/fichier/ped': {'db_col': 'pediatre_initiales', 'type': 'text'},
    '/fichier/dom': {'db_col': 'domicile', 'type': 'text'},
    '/fichier/tel': {'db_col': 'telephone', 'type': 'text'},
    '/fichier/cat': {'db_col': 'third_party_payer', 'type': 'text'},
    '/fichier/hopital': {'db_col': 'hopital', 'type': 'text'},
    '/fichier/diag1': {'db_col': 'diag1', 'type': 'text'},
    '/fichier/diag2': {'db_col': 'diag2', 'type': 'text'},
    '/fichier/obst': {'db_col': 'obstetrical_history', 'type': 'text'},
    '/fichier/monotest1': {'db_col': 'monotest1', 'type': 'datetime_to_date'},
    '/fichier/monotest2': {'db_col': 'monotest2', 'type': 'datetime_to_date'},
    '/fichier/monotest3': {'db_col': 'monotest3', 'type': 'datetime_to_date'},
    '/fichier/r': {'db_col': 'rougeole_seule_date', 'type': 'date'},
    
    # Vaccine dates
    '/fichier/dtcp1': {'db_col': 'dtcp1_date', 'type': 'date'},
    '/fichier/dtcp2': {'db_col': 'dtcp2_date', 'type': 'date'},
    '/fichier/dtcp3': {'db_col': 'dtcp3_date', 'type': 'date'},
    '/fichier/rdtcp1': {'db_col': 'dtcp_rappel1_date', 'type': 'date'},
    '/fichier/rdtcp2': {'db_col': 'dtcp_rappel2_date', 'type': 'date'},
    '/fichier/rdtp3': {'db_col': 'dtcp_rappel3_date', 'type': 'date'},
    '/fichier/rdtp4': {'db_col': 'dtcp_rappel4_date', 'type': 'date'},
    
    '/fichier/hep_b1': {'db_col': 'hep_b1_date', 'type': 'date'},
    '/fichier/hep_b2': {'db_col': 'hep_b2_date', 'type': 'date'},
    '/fichier/hep_b3': {'db_col': 'hep_b3_date', 'type': 'date'},
    
    '/fichier/hib1': {'db_col': 'hib1_date', 'type': 'date'},
    '/fichier/hib2': {'db_col': 'hib2_date', 'type': 'date'},
    '/fichier/hib3': {'db_col': 'hib3_date', 'type': 'date'},
    '/fichier/rhib': {'db_col': 'hib_rappel_date', 'type': 'date'},
    
    '/fichier/ror': {'db_col': 'ror_date', 'type': 'date'},
}

def get_patient_unified_data(patient_xml_data, header_map, current_sequential_mrn):
    """Convert XML patient data to unified database format."""
    record = {}
    record['mrn'] = str(current_sequential_mrn).zfill(5)  # 5-digit MRN
    record['emr_mode'] = 'pediatric'  # Mark as imported from pediatric system
    record['created_date'] = datetime.datetime.now().isoformat()
    record['modified_date'] = datetime.datetime.now().isoformat()

    for xml_key, map_info in header_map.items():
        db_key = map_info['db_col']
        val_type = map_info['type']
        raw_val = patient_xml_data.get(xml_key)

        if raw_val is None or raw_val == "":
            record[db_key] = None
        elif val_type == 'text':
            record[db_key] = raw_val
        elif val_type == 'date':
            parsed_date = None
            if raw_val and 'T' in raw_val:
                parsed_date = raw_val.split('T')[0]
                try:
                    datetime.datetime.strptime(parsed_date, '%Y-%m-%d')
                except ValueError:
                    parsed_date = None
            if not parsed_date and raw_val:
                parsed_date = parse_date_to_iso(raw_val, input_format='%d-%m-%y')
            record[db_key] = parsed_date
        elif val_type == 'datetime_to_date':
            parsed_dt_date = None
            if raw_val and 'T' in raw_val:
                parsed_dt_date = raw_val.split('T')[0]
                try:
                    datetime.datetime.strptime(parsed_dt_date, '%Y-%m-%d')
                except ValueError:
                    parsed_dt_date = None
            else:
                parsed_dt_date = parse_date_to_iso(raw_val, input_format='%d-%m-%y')
            record[db_key] = parsed_dt_date
        else:
            record[db_key] = raw_val

    # Add raw text fields
    record['raw_dossier_text'] = patient_xml_data.get('/fichier/dossier')
    record['raw_autres_vaccins_text'] = patient_xml_data.get('/fichier/autres_vac')
    
    # Add birth measurements if parsed
    parsed_dossier = patient_xml_data.get('parsed_dossier_content', {})
    birth_measurements = parsed_dossier.get('birth_measurements', {})
    record['birth_weight_g'] = birth_measurements.get('weight_g')
    record['birth_height_cm'] = birth_measurements.get('height_cm')
    record['birth_head_circumference_cm'] = birth_measurements.get('hc_cm')
    record['birth_notes'] = birth_measurements.get('notes')
    
    return record

def _insert_patient_visits_unified(patient_id, parsed_visits):
    """Insert visits using unified database system."""
    visits_added_count = 0
    db = get_db()
    
    for visit in parsed_visits:
        if visit.get('visit_date'):
            visit_data = {
                'patient_id': patient_id,
                'visit_date': visit['visit_date'],
                'weight_g': visit.get('weight_g'),
                'height_cm': visit.get('height_cm'),
                'head_circumference_cm': visit.get('head_circumference_cm'),
                'notes': visit.get('notes'),
                'raw_visit_entry': visit.get('raw_visit_entry'),
                'visit_type': 'pediatric',
                'created_date': datetime.datetime.now().isoformat()
            }
            
            # Insert visit directly into unified database
            columns = ', '.join(visit_data.keys())
            placeholders = ', '.join(['?' for _ in visit_data.keys()])
            query = f"INSERT INTO Visits ({columns}) VALUES ({placeholders})"
            
            cursor = db.execute(query, list(visit_data.values()))
            visits_added_count += 1
    
    return visits_added_count

def _insert_non_standard_vaccines_unified(patient_id, parsed_vaccines):
    """Insert non-standard vaccines using unified database system."""
    vaccines_added_count = 0
    db = get_db()
    
    for vac in parsed_vaccines:
        if vac.get('vaccine_date') and vac.get('vaccine_name'):
            vaccine_data = {
                'patient_id': patient_id,
                'vaccine_name': vac['vaccine_name'],
                'vaccine_date': vac['vaccine_date'],
                'raw_entry': vac.get('raw_entry'),
                'created_date': datetime.datetime.now().isoformat()
            }
            
            columns = ', '.join(vaccine_data.keys())
            placeholders = ', '.join(['?' for _ in vaccine_data.keys()])
            query = f"INSERT INTO NonStandardVaccines ({columns}) VALUES ({placeholders})"
            
            cursor = db.execute(query, list(vaccine_data.values()))
            vaccines_added_count += 1
    
    return vaccines_added_count

def populate_database_from_parsed_data(all_xml_patients, target_mode='pediatric', document_format='md'):
    """Populate unified database from parsed XML data."""
    
    if not all_xml_patients:
        print("No patient data to populate. Aborting.")
        return 0, 0, 0

    print(f"Starting unified database population with {len(all_xml_patients)} patient records...")

    db = get_db()
    patients_added = 0
    visits_added = 0
    non_std_vaccines_added = 0
    
    # Initialize word document manager for failsafe document creation
    word_manager = WordDocumentManager(
        db_path=emr_config.get_database_path(), 
        documents_folder=emr_config.get_word_docs_folder()
    )
    
    # Get the highest existing MRN to continue sequence
    cursor = db.execute("SELECT MAX(CAST(mrn AS INTEGER)) FROM Patients WHERE mrn GLOB '[0-9]*'")
    max_mrn_result = cursor.fetchone()
    sequential_mrn_counter = 1 if max_mrn_result[0] is None else int(max_mrn_result[0]) + 1

    for i, patient_xml in enumerate(all_xml_patients):
        # Check for essential data
        raw_nom = patient_xml.get('/fichier/nom', '').strip()
        raw_prenom = patient_xml.get('/fichier/prenom', '').strip()

        if not raw_nom and not raw_prenom:
            print(f"Skipping record {i+1} due to missing name data.")
            continue

        try:
            # Convert to unified format
            unified_patient_data = get_patient_unified_data(
                patient_xml, HEADER_TO_DB_MAP, sequential_mrn_counter
            )
            
            # Use unified database save function
            patient_id = save_patient_unified(unified_patient_data, target_mode)
            patients_added += 1
            sequential_mrn_counter += 1

            # Insert visits
            parsed_dossier = patient_xml.get('parsed_dossier_content', {})
            parsed_visits = parsed_dossier.get('parsed_visits', [])
            visits_added += _insert_patient_visits_unified(patient_id, parsed_visits)
            
            # Insert non-standard vaccines
            parsed_autres_vaccins = patient_xml.get('parsed_autres_vaccins', [])
            non_std_vaccines_added += _insert_non_standard_vaccines_unified(
                patient_id, parsed_autres_vaccins
            )

            # Create/update document for this patient (failsafe feature)
            try:
                word_manager.create_or_update_document(patient_id, document_format)
                format_name = "Word document" if document_format == 'docx' else "Markdown document"
                print(f"Created {format_name} for patient ID {patient_id} (MRN: {unified_patient_data.get('mrn', 'N/A')})")
            except Exception as e:
                print(f"Warning: Failed to create Word document for patient ID {patient_id}: {e}")

        except Exception as e:
            print(f"Error processing patient {i+1}: {e}")
            import traceback
            traceback.print_exc()

        if (i + 1) % 50 == 0:
            print(f"Processed {i+1}/{len(all_xml_patients)} patients...")
            db.commit()

    db.commit()
    print("\nUnified database population completed.")
    print(f"Total patients added: {patients_added}")
    print(f"Total visits added: {visits_added}")
    print(f"Total non-standard vaccines added: {non_std_vaccines_added}")
    
    return patients_added, visits_added, non_std_vaccines_added

def populate_database(xml_file, target_mode='pediatric'):
    """Main entry point for XML database population."""
    print(f"Parsing XML data from: {xml_file}")
    all_xml_patients = parse_excel_xml(xml_file)
    
    return populate_database_from_parsed_data(all_xml_patients, target_mode) 