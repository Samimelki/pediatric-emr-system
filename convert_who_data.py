'''
Script to convert WHO growth standard Excel files to CSV format.

Instructions:
1. Ensure you have pandas and openpyxl installed:
   pip install pandas openpyxl
2. Before running, you MUST inspect each Excel file listed in the FILE_CONFIG
   and update the 'sheet_name', 'header_row', and 'column_map' for each entry.
   - 'sheet_name': The name of the Excel sheet containing the data.
   - 'header_row': The 0-indexed row number where the column headers (like 'Month', 'P3') are located.
   - 'column_map': A dictionary mapping the exact column name in the Excel
                   sheet to the desired CSV column name.
                   Required CSV columns are: "Month", "P3", "P15", "P50", "P85", "P97".
                   Example: {"Age in completed months": "Month", "3rd": "P3", ...}
   - 'age_unit': Specify if the age column in Excel is in 'months' or 'days' (for birth-13 weeks tables if used).
                 Currently, the script primarily expects 'months' for 0-5yr data.
   - 'measurement_unit': For potential future use if unit conversion within script is needed (e.g. 'kg', 'cm').
                        Assume for now that percentiles are already in desired units (kg, cm).
'''
import pandas as pd
import os

# --- USER CONFIGURATION REQUIRED ---
# User MUST update this section by inspecting each Excel file.
FILE_CONFIG = [
    {
        "input_excel": "tab_wfa_boys_p_0_5.xlsx",
        "output_csv": "wfa_boys_0_5_percentiles.csv",
        "sheet_name": "tab_wfa_boys_p_0_5",  # Updated from Sheet1
        "header_row": 0,        # Confirmed
        "column_map": {
            "Month": "Month", # Confirmed
            "P3": "P3",       # Updated from "3rd"
            "P15": "P15",     # Updated from "15th"
            "P50": "P50",     # Updated from "50th"
            "P85": "P85",     # Updated from "85th"
            "P97": "P97"      # Updated from "97th"
        },
        "data_type": "wfa", # weight-for-age
        "age_unit": "months",
        "measurement_unit": "kg"
    },
    {
        "input_excel": "tab_wfa_girls_p_0_5.xlsx",
        "output_csv": "wfa_girls_0_5_percentiles.csv",
        "sheet_name": "tab_wfa_girls_p_0_5", # Updated from Sheet1
        "header_row": 0, # Confirmed
        "column_map": {
            "Month": "Month", "P3": "P3", "P15": "P15", # Confirmed/Updated
            "P50": "P50", "P85": "P85", "P97": "P97"  # Confirmed/Updated
        },
        "data_type": "wfa",
        "age_unit": "months",
        "measurement_unit": "kg"
    },
    # --- Length/Height for Age (requires combining 0-2 and 2-5 year files) ---
    {
        "input_excel_0_2": "tab_lhfa_boys_p_0_2.xlsx", # Length
        "input_excel_2_5": "tab_lhfa_boys_p_2_5.xlsx", # Height
        "output_csv": "lhfa_boys_0_5_percentiles.csv",
        "sheet_name_0_2": "tab_lhfa_boys_p_0_2", # Updated
        "header_row_0_2": 0, # Confirmed
        "column_map_0_2": {
            "Month": "Month", "P3": "P3", "P15": "P15", # Confirmed/Updated
            "P50": "P50", "P85": "P85", "P97": "P97"  # Confirmed/Updated
        },
        "sheet_name_2_5": "tab_lhfa_boys_p_2_5", # Updated
        "header_row_2_5": 0, # Confirmed
        "column_map_2_5": { # May have different month/age col name, e.g. for "height"
            "Month": "Month", "P3": "P3", "P15": "P15", # Confirmed/Updated
            "P50": "P50", "P85": "P85", "P97": "P97"  # Confirmed/Updated
        },
        "data_type": "lhfa", # length/height-for-age
        "age_unit": "months",
        "measurement_unit": "cm"
    },
    {
        "input_excel_0_2": "tab_lhfa_girls_p_0_2.xlsx",
        "input_excel_2_5": "tab_lhfa_girls_p_2_5.xlsx",
        "output_csv": "lhfa_girls_0_5_percentiles.csv",
        "sheet_name_0_2": "tab_lhfa_girls_p_0_2", # Updated
        "header_row_0_2": 0, # Confirmed
        "column_map_0_2": {
            "Month": "Month", "P3": "P3", "P15": "P15", # Confirmed/Updated
            "P50": "P50", "P85": "P85", "P97": "P97"  # Confirmed/Updated
        },
        "sheet_name_2_5": "tab_lhfa_girls_p_2_5", # Updated
        "header_row_2_5": 0, # Confirmed
        "column_map_2_5": {
            "Month": "Month", "P3": "P3", "P15": "P15", # Confirmed/Updated
            "P50": "P50", "P85": "P85", "P97": "P97"  # Confirmed/Updated
        },
        "data_type": "lhfa",
        "age_unit": "months",
        "measurement_unit": "cm"
    },
    # --- Head Circumference for Age ---
    {
        "input_excel": "tab_hcfa_boys_p_0_5.xlsx",
        "output_csv": "hcfa_boys_0_5_percentiles.csv",
        "sheet_name": "tab_hcfa_boys_p_0_5", # Updated
        "header_row": 0, # Confirmed
        "column_map": {
            "Month": "Month", "P3": "P3", "P15": "P15", # Confirmed/Updated
            "P50": "P50", "P85": "P85", "P97": "P97"  # Confirmed/Updated
        },
        "data_type": "hcfa", # headcircumference-for-age
        "age_unit": "months",
        "measurement_unit": "cm"
    },
    {
        "input_excel": "tab_hcfa_girls_p_0_5.xlsx",
        "output_csv": "hcfa_girls_0_5_percentiles.csv",
        "sheet_name": "tab_hcfa_girls_p_0_5", # Updated
        "header_row": 0, # Confirmed
        "column_map": {
            "Month": "Month", "P3": "P3", "P15": "P15", # Confirmed/Updated
            "P50": "P50", "P85": "P85", "P97": "P97"  # Confirmed/Updated
        },
        "data_type": "hcfa",
        "age_unit": "months",
        "measurement_unit": "cm"
    },
]
# --- END USER CONFIGURATION ---

BASE_PATH = os.path.join("static", "data", "who_growth_standards")
DESIRED_CSV_COLUMNS = ["Month", "P3", "P15", "P50", "P85", "P97"]

def _process_dataframe(df, config_name, column_map, age_unit, month_filter_le=60, month_filter_gt=None):
    """Helper function to process a DataFrame: rename, clean, filter months, and select columns."""
    current_column_map = {k: v for k, v in column_map.items() if k in df.columns}
    if not all(csv_col in current_column_map.values() for csv_col in DESIRED_CSV_COLUMNS):
        print(f"  WARNING: Not all desired columns could be mapped for {config_name}.")
        print(f"  Mapped columns found: {list(current_column_map.values())}")
        # Check which are missing
        missing_desired = [d for d in DESIRED_CSV_COLUMNS if d not in current_column_map.values()]
        print(f"  Desired CSV columns missing in map: {missing_desired}")
        # Attempt to proceed with what we have, but highlight the issue.

    df_selected = df[list(current_column_map.keys())].copy()
    df_selected.rename(columns=current_column_map, inplace=True)

    if "Month" not in df_selected.columns:
        print(f"  ERROR: 'Month' column not found after mapping for {config_name}. Check column_map.")
        return None # Indicate error

    df_selected["Month"] = pd.to_numeric(df_selected["Month"], errors='coerce').fillna(-1).astype(int)
    df_selected = df_selected[df_selected["Month"] != -1]

    if age_unit == "months":
        if month_filter_le is not None:
            df_selected = df_selected[df_selected["Month"] <= month_filter_le]
        if month_filter_gt is not None:
            df_selected = df_selected[df_selected["Month"] > month_filter_gt]
            
    final_columns_present = [col for col in DESIRED_CSV_COLUMNS if col in df_selected.columns]
    return df_selected[final_columns_present]

def process_single_file(config):
    '''Processes a single Excel file configuration.'''
    excel_path = os.path.join(BASE_PATH, config["input_excel"])
    csv_path = os.path.join(BASE_PATH, config["output_csv"])

    print(f"Processing {config['input_excel']} -> {config['output_csv']}...")
    try:
        df = pd.read_excel(
            excel_path,
            sheet_name=config["sheet_name"],
            header=config["header_row"]
        )
        
        df_final = _process_dataframe(
            df, 
            config["input_excel"], 
            config["column_map"], 
            config["age_unit"]
        )

        if df_final is None: # Error occurred in helper
            return
        
        df_final.to_csv(csv_path, index=False)
        print(f"  Successfully created {csv_path}")

    except FileNotFoundError:
        print(f"  ERROR: Excel file not found: {excel_path}")
    except KeyError as e:
        print(f"  ERROR: A specified column in column_map not found in {config['input_excel']}: {e}")
        print(f"  Available columns: {list(df.columns if 'df' in locals() else [])}")
    except Exception as e:
        print(f"  ERROR processing {config['input_excel']}: {e}")

def process_combined_lh_file(config):
    '''Processes and combines 0-2yr and 2-5yr length/height Excel files.'''
    excel_path_0_2 = os.path.join(BASE_PATH, config["input_excel_0_2"])
    excel_path_2_5 = os.path.join(BASE_PATH, config["input_excel_2_5"])
    csv_path = os.path.join(BASE_PATH, config["output_csv"])

    print(f"Processing {config['input_excel_0_2']} & {config['input_excel_2_5']} -> {config['output_csv']}...")
    
    try:
        # Process 0-2 years data (Length)
        df_0_2_raw = pd.read_excel(
            excel_path_0_2,
            sheet_name=config["sheet_name_0_2"],
            header=config["header_row_0_2"]
        )
        df_0_2_final = _process_dataframe(
            df_0_2_raw, 
            config["input_excel_0_2"], 
            config["column_map_0_2"], 
            config["age_unit"], 
            month_filter_le=24
        )
        if df_0_2_final is None: return

        # Process 2-5 years data (Height)
        df_2_5_raw = pd.read_excel(
            excel_path_2_5,
            sheet_name=config["sheet_name_2_5"],
            header=config["header_row_2_5"]
        )
        df_2_5_final = _process_dataframe(
            df_2_5_raw, 
            config["input_excel_2_5"], 
            config["column_map_2_5"], 
            config["age_unit"], 
            month_filter_le=60, 
            month_filter_gt=24
        )
        if df_2_5_final is None: return
        
        # Combine the two dataframes
        df_combined = pd.concat([df_0_2_final, df_2_5_final], ignore_index=True)
        df_combined.drop_duplicates(subset=["Month"], keep="first", inplace=True) # Handle overlap, e.g. month 24
        df_combined.sort_values(by="Month", inplace=True)
        
        df_combined.to_csv(csv_path, index=False)
        print(f"  Successfully created {csv_path}")

    except FileNotFoundError as e:
        print(f"  ERROR: Excel file not found: {e}")
    except KeyError as e:
        print(f"  ERROR: A specified column in column_map not found: {e}")
    except Exception as e:
        print(f"  ERROR processing combined LH file: {e}")


if __name__ == "__main__":
    if not os.path.exists(BASE_PATH):
        os.makedirs(BASE_PATH)
        print(f"Created directory: {BASE_PATH}")

    for config_item in FILE_CONFIG:
        if config_item["data_type"] == "lhfa":
            process_combined_lh_file(config_item)
        else: # wfa, hcfa
            process_single_file(config_item)
    
    print("\nConversion process finished.")
    print("Please check the CSV files in:", BASE_PATH)
    print("If there were errors or warnings, you may need to adjust the FILE_CONFIG in this script and re-run.") 