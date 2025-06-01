import os
from config_manager import load_config, WORD_DOCS_FOLDER
from database_operations import DatabaseOperations

def main():
    # Load configuration
    config = load_config()
    
    # Initialize database operations with Word document management
    db_ops = DatabaseOperations(
        db_path=config['database_path'],
        documents_folder=config['word_docs_folder']
    )
    
    # Rename existing documents
    print("Renaming existing documents...")
    renamed_files = db_ops.rename_all_documents()
    
    if renamed_files:
        print("\nRenamed files:")
        for old_name, new_name in renamed_files:
            print(f"  {old_name} -> {new_name}")
    else:
        print("No files were renamed.")
    
    # Create Word documents for all patients
    print("\nCreating/updating Word documents for all patients...")
    conn = db_ops._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM Patients")
        patient_ids = [row['id'] for row in cursor.fetchall()]
        
        for patient_id in patient_ids:
            try:
                doc_path = db_ops.word_manager.create_or_update_patient_document(patient_id)
                print(f"Created/updated document for patient {patient_id}: {os.path.basename(doc_path)}")
            except Exception as e:
                print(f"Error creating document for patient {patient_id}: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    main() 