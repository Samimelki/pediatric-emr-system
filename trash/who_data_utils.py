import pandas as pd
import os
import sys # Added for PyInstaller path detection

# Function to determine the correct base path for data files
def get_data_base_path():
    """ Get base path for data files, works for dev and PyInstaller """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running in a PyInstaller bundle
        # In the .spec file, ('data/who_standards', 'data/who_standards') means
        # the 'who_standards' folder from project_root/data/who_standards 
        # is copied to app_bundle_root/data/who_standards.
        # The original WHO_DATA_BASE_PATH was os.path.join("static", "data", "who_growth_standards")
        # We need to adjust this to match the .spec datas and the location of this util file.
        # The spec file now copies 'data/who_standards' to 'data/who_standards' in the bundle.
        # So, the path inside the bundle will be 'data/who_standards' relative to _MEIPASS.
        return os.path.join(sys._MEIPASS, 'data', 'who_standards')
    else:
        # Running in a normal Python environment (development)
        # Assuming this script (who_data_utils.py) is at the project root.
        # If it's in a utils/ subdir, adjust accordingly, but based on previous paths, 
        # it seems CSVs are in project_root/data/who_standards/
        # The original path was os.path.join("static", "data", "who_growth_standards")
        # This implies the CSVs are in project_root/static/data/who_growth_standards
        # Let's ensure this matches where the files actually are during development.
        # Based on the app.spec: ('data/who_standards', 'data/who_standards')
        # it implies source is 'data/who_standards'.
        # And the old WHO_DATA_BASE_PATH was os.path.join("static", "data", "who_growth_standards")
        # This is a discrepancy. Let's assume the .spec file is the source of truth for location.
        # So in dev, it should be 'data/who_standards' from project root.
        dev_path = os.path.join(os.path.abspath("."), "data", "who_standards")
        return dev_path

WHO_DATA_BASE_PATH = get_data_base_path()
EXPECTED_PERCENTILES_P_NOTATION = ["P3", "P15", "P50", "P85", "P97"] # Renamed for clarity
EXPECTED_PERCENTILES_ORDINAL = ["3rd", "15th", "50th", "85th", "97th"]

def load_who_percentile_data(data_type: str, sex: str):
    """
    Loads WHO growth percentile data from a CSV file.

    Args:
        data_type (str): The type of data to load (e.g., "wfa", "lhfa", "hcfa", "hfa_5_19").
        sex (str): The sex for the data ("boys" or "girls").

    Returns:
        dict: A dictionary where keys are percentile strings (e.g., "P3" or "3rd")
              and values are lists of the corresponding measurement values.
              Returns an empty dictionary if the file is not found or data is invalid.
              The month data is returned under the key "Month".
    """
    if sex.lower() not in ["boys", "girls"]:
        print(f"Error loading WHO data: Invalid sex '{sex}'. Must be 'boys' or 'girls'.")
        return {}
    data_type_lower = data_type.lower() # Moved up
    if data_type_lower not in ["wfa", "lhfa", "hcfa", "hfa_5_19"]:
        print(f"Error loading WHO data: Invalid data_type '{data_type}'. Must be 'wfa', 'lhfa', 'hcfa', or 'hfa_5_19'.")
        return {}

    # Determine which set of percentile keys to use
    if data_type_lower == "hfa_5_19":
        percentile_keys_to_use = EXPECTED_PERCENTILES_ORDINAL
    else:
        percentile_keys_to_use = EXPECTED_PERCENTILES_P_NOTATION

    sex_lower = sex.lower()
    if data_type_lower == "hfa_5_19":
        filename = f"hfa_{sex_lower}_p_5_19.csv"
    elif data_type_lower == "lhfa":
        filename = f"lhfa_{sex_lower}_0_5_percentiles.csv"
    else:
        filename = f"{data_type_lower}_{sex_lower}_0_5_percentiles.csv"

    file_path = os.path.join(WHO_DATA_BASE_PATH, filename)

    # Initialize with "Month" and the chosen percentile keys
    percentile_data = {"Month": []}
    for p_col in percentile_keys_to_use:
        percentile_data[p_col] = []

    try:
        df = pd.read_csv(file_path)

        if data_type.lower() == "hcfa": # Specific debug prints for HCFA
            print(f"[DEBUG HCFA] Successfully read {filename}. Shape: {df.shape}. Dtypes: {df.dtypes}")
            if "Month" in df.columns:
                print(f"[DEBUG HCFA] {filename} - Month column head: {df['Month'].head().tolist()}")
            else:
                print(f"[DEBUG HCFA] {filename} - Month column IS MISSING.")

        if "Month" not in df.columns:
            error_msg = f"Error loading WHO data: 'Month' column not found in {filename}"
            if data_type_lower == "hfa_5_19":
                error_msg += ". This is critical for the HFA 5-19 years chart."
            print(error_msg)
            return {key: list(val) for key, val in percentile_data.items()} 
        
        # Ensure all expected percentile columns (for this data_type) are present
        for p_col in percentile_keys_to_use:
            if p_col not in df.columns:
                print(f"Error loading WHO data: Percentile column '{p_col}' not found in {filename}")
                return {key: [] for key in percentile_data} # Return empty dict matching init structure

        # Convert to float, coercing errors to NaN, then fill NaN with None (for JSON compatibility)
        percentile_data["Month"] = df["Month"].astype(int).tolist()
        for p_col in percentile_keys_to_use: # Use the determined keys
            percentile_data[p_col] = pd.to_numeric(df[p_col], errors='coerce').where(pd.notnull(df[p_col]), None).tolist()
            
        return percentile_data

    except FileNotFoundError:
        print(f"Error: WHO data file not found: {file_path}")
        return {key: [] for key in percentile_data} # Return empty lists if file not found
    except Exception as e:
        print(f"Error loading or processing WHO data file {filename}: {type(e).__name__} - {e}") # More verbose error
        if data_type.lower() == "hcfa":
            import traceback
            print(f"[DEBUG HCFA] Traceback for {filename}:\n{traceback.format_exc()}")
        return {key: [] for key in percentile_data} # Return empty lists on other errors

if __name__ == '__main__':
    # Example usage:
    print("--- Testing WHO Data Loader ---")
    
    boys_wfa = load_who_percentile_data("wfa", "boys")
    if boys_wfa.get("Month"):
        print(f"Boys WFA (0-5y) - Months: {boys_wfa['Month'][:5]}...") # First 5
        print(f"Boys WFA (0-5y) - P50: {boys_wfa['P50'][:5]}...")    # First 5
    else:
        print("Could not load Boys WFA data.")

    girls_lhfa = load_who_percentile_data("lhfa", "girls")
    if girls_lhfa.get("Month"):
        print(f"Girls LHFA (0-5y) - Months: {girls_lhfa['Month'][:5]}...")
        print(f"Girls LHFA (0-5y) - P97: {girls_lhfa['P97'][:5]}...")
    else:
        print("Could not load Girls LHFA data.")

    # Test the new HFA 5-19 loader
    boys_hfa_5_19 = load_who_percentile_data("hfa_5_19", "boys")
    if boys_hfa_5_19.get("Month"):
        print(f"Boys HFA (5-19y) - Months: {boys_hfa_5_19['Month'][:5]}...")
        print(f"Boys HFA (5-19y) - 50th: {boys_hfa_5_19.get('50th', [])[:5]}...") # Use .get for safety in test
    else:
        print("Could not load Boys HFA (5-19y) data.")

    girls_hfa_5_19 = load_who_percentile_data("hfa_5_19", "girls")
    if girls_hfa_5_19.get("Month"):
        print(f"Girls HFA (5-19y) - Months: {girls_hfa_5_19['Month'][:5]}...")
        print(f"Girls HFA (5-19y) - 97th: {girls_hfa_5_19.get('97th', [])[:5]}...") # Use .get for safety in test
    else:
        print("Could not load Girls HFA (5-19y) data.")

    invalid_data = load_who_percentile_data("xyz", "boys") # Test invalid type
    if not invalid_data.get("Month"):
        print("Test for invalid data type behaved as expected.")

    # Test case for a potentially missing file (example)
    # non_existent_data = load_who_percentile_data("wfa", "aliens")
    # if not non_existent_data.get("Month"):
    #     print("Test for non-existent file (aliens) behaved as expected.") 