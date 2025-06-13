from emr_config import emr_config
import os
import sqlite3

def rename_documents():
    """Rename all Word documents to use the new naming convention."""
    
    # Get paths from emr_config
    word_docs_folder = emr_config.get_word_docs_folder()
    database_path = emr_config.get_database_path()
    
    if not os.path.exists(word_docs_folder):
        print(f"Word documents folder does not exist: {word_docs_folder}")
        return
    
    if not os.path.exists(database_path):
        print(f"Database does not exist: {database_path}")
        return
    
    # Connect to database
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get all patients
        cursor.execute("SELECT id, prenom, nom FROM Patients")
        patients = cursor.fetchall()
        
        renamed_count = 0
        
        for patient in patients:
            patient_id = patient['id']
            prenom = patient['prenom'] or 'Unknown'
            nom = patient['nom'] or 'Unknown'
            
            # Old filename pattern
            old_filename = f"patient_{patient_id}.docx"
            old_path = os.path.join(word_docs_folder, old_filename)
            
            # New filename pattern
            new_filename = f"{prenom}_{nom}_{patient_id}.docx"
            new_path = os.path.join(word_docs_folder, new_filename)
            
            # Check if old file exists and new file doesn't
            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    os.rename(old_path, new_path)
                    print(f"Renamed: {old_filename} -> {new_filename}")
                    renamed_count += 1
                except OSError as e:
                    print(f"Error renaming {old_filename}: {e}")
            elif os.path.exists(new_path):
                print(f"New filename already exists: {new_filename}")
            else:
                print(f"Old file not found: {old_filename}")
        
        print(f"\nRenamed {renamed_count} documents successfully.")
        
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    rename_documents() 