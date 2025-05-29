import pdfplumber
import csv
import os

def extract_hfa_percentiles_from_pdf(pdf_path, output_csv_path):
    """
    Extracts Height-for-Age percentile data from a WHO PDF file and saves it to a CSV.
    Uses page-dependent logic for column offsets based on observations from raw CSV output.
    Pages 1 & 2 (0-indexed i=0,1) have a different layout for 'Month' and percentile data
    compared to Page 3 onwards (i>=2).
    """
    target_data_headers = ["Month", "3rd", "15th", "50th", "85th", "97th"]
    # Define how target headers might appear in the PDF
    pdf_header_candidates = {
        "Month": "Month", "3rd": "3rd", "15th": "15th",
        "50th": "50th", "85th": "85th", "97th": "97th"
    }
    pdf_header_candidates_alt = {
        "Month": "Month", "P3": "3rd", "P15": "15th",
        "P50": "50th", "P85": "85th", "P97": "97th"
    }

    all_extracted_rows = []
    target_headers_found_for_pdf = False  # Has a valid header set been found for this PDF?
    last_known_col_indices = {}       # Stores the last successfully mapped header_name:pdf_column_index

    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Processing PDF: {pdf_path}, Pages: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages): # i is the 0-indexed page number
                print(f"  Extracting tables from page {i + 1}...")
                tables = page.extract_tables(table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    # "snap_tolerance": 3,
                    # "join_tolerance": 3,
                })

                if not tables:
                    print(f"    Page {i+1}: No tables found.")
                    continue

                for table_idx, table_data in enumerate(tables):
                    if not table_data:
                        print(f"    Page {i+1}, Table {table_idx+1} is empty.")
                        continue

                    found_header_row_index = -1 # Index of the header row within the current table_data
                    current_col_indices = {}    # Tentative column indices for this table

                    # Attempt to find headers in the current table if we haven't found them for the PDF yet,
                    # or if this table looks like it might re-state headers.
                    if not target_headers_found_for_pdf or len(table_data) > 2: # Heuristic for tables that might contain headers
                        for row_num, pdf_row_list in enumerate(table_data[:3]): # Check first 3 rows for headers
                            if not pdf_row_list: continue
                            current_row_normalized = [str(cell).strip() if cell is not None else '' for cell in pdf_row_list]
                            matches = 0
                            temp_indices = {}

                            # Try primary header candidates
                            for pdf_h_key, target_h_val in pdf_header_candidates.items():
                                try:
                                    idx = -1
                                    if pdf_h_key == "Month": # Require exact match for "Month"
                                        for cell_idx, cell_val_raw in enumerate(current_row_normalized):
                                            if cell_val_raw.strip() == "Month":
                                                idx = cell_idx; break
                                    else: # Allow substring match for other percentile headers
                                        for cell_idx, cell_val_raw in enumerate(current_row_normalized):
                                            if pdf_h_key and pdf_h_key in cell_val_raw:
                                                idx = cell_idx; break
                                    if idx == -1: raise ValueError("Header not found")
                                    temp_indices[target_h_val] = idx
                                    matches += 1
                                except ValueError:
                                    pass

                            if matches < 3: # If primary set fails, try alternative (e.g., "P3" instead of "3rd")
                                matches = 0
                                temp_indices = {}
                                for pdf_h_key, target_h_val in pdf_header_candidates_alt.items():
                                    try:
                                        idx = -1
                                        # For simplicity, allow substring for all in alt set for now
                                        for cell_idx, cell_val_raw in enumerate(current_row_normalized):
                                            if pdf_h_key and pdf_h_key in cell_val_raw:
                                                idx = cell_idx; break
                                        if idx == -1: raise ValueError("Alt Header not found")
                                        temp_indices[target_h_val] = idx
                                        matches += 1
                                    except ValueError:
                                        pass
                            
                            # If we have a "Month" and at least 3 other headers, consider it a valid header row
                            if temp_indices.get("Month") is not None and matches >= 4:
                                current_col_indices = temp_indices
                                found_header_row_index = row_num
                                actual_header_names_debug = sorted(current_col_indices.keys(), key=lambda k: current_col_indices[k])
                                print(f"    Page {i+1}, Table {table_idx+1}: Found plausible header at table row {row_num + 1}. Headers: {actual_header_names_debug}")
                                print(f"    Mapped PDF column indices: {current_col_indices}")
                                target_headers_found_for_pdf = True
                                last_known_col_indices = current_col_indices # Update last known good header map
                                break # Found headers in this table

                    # Determine which data rows to iterate and which column map to use
                    data_to_iterate = []
                    effective_col_indices = {}
                    start_row_for_data_in_table = 0

                    if found_header_row_index != -1: # Headers were found in *this* table
                        effective_col_indices = current_col_indices
                        start_row_for_data_in_table = found_header_row_index + 1
                        if start_row_for_data_in_table >= len(table_data):
                            # print(f"    DEBUG: Headers found on last row of table P{i+1},T{table_idx+1}, no data rows after.")
                            continue # No data rows after header
                        data_to_iterate = table_data[start_row_for_data_in_table:]
                    elif target_headers_found_for_pdf: # No headers in this table, but found in a previous one for this PDF
                        effective_col_indices = last_known_col_indices # Use the last good map
                        data_to_iterate = table_data # Assume all rows are data
                        # print(f"    DEBUG: P{i+1},T{table_idx+1} is continuation table. Using last_known_col_indices.")
                    else:
                        # Headers not found in this table AND not found previously in PDF.
                        # This table cannot be processed reliably.
                        if table_data and table_data[0]: print(f"    Skipping table on Page {i+1}, Table {table_idx+1}: Headers not yet identified for PDF. First row of table: {[str(c).strip() for c in table_data[0][:5]]}...")
                        continue

                    if not effective_col_indices: # Should not happen if logic above is correct
                        print(f"    ERROR: P{i+1},T{table_idx+1} - effective_col_indices is empty. Skipping.")
                        continue

                    # Page-dependent offset for PERCENTILE data columns
                    # Pages 1 and 2 (i=0,1) have percentile data directly at mapped header indices.
                    # Pages 3+ (i>=2) have percentile data shifted by +1 from mapped header indices.
                    data_column_offset_for_percentiles = 1 if i >= 2 else 0
                    # print(f"    DEBUG (Page {i+1}, Table {table_idx+1}): Using data_column_offset_for_percentiles = {data_column_offset_for_percentiles}")

                    for r_idx, data_row_list in enumerate(data_to_iterate):
                        if not data_row_list or not any(s is not None and str(s).strip() != '' for s in data_row_list):
                            # print(f"        Skipping empty or all-None/empty-string row at P{i+1},T{table_idx+1}, data_row_idx {r_idx}")
                            continue
                        
                        normalized_data_row = [str(cell).strip() if cell is not None else '' for cell in data_row_list]
                        extracted_data_point = {}
                        valid_point = True
                        missing_reason = ""

                        for target_h_name in target_data_headers:
                            # This is the column index where the header (e.g., "Month", "3rd") was FOUND in the header row
                            pdf_col_idx_where_header_was_found = effective_col_indices.get(target_h_name)

                            if pdf_col_idx_where_header_was_found is None:
                                missing_reason = f"Header '{target_h_name}' was not in effective_col_indices map: {effective_col_indices}."
                                valid_point = False; break
                            
                            actual_data_access_idx = -1 # This will be the index into normalized_data_row
                            value_str = ""

                            if target_h_name == "Month":
                                # For "Month", the logic is specific to which column the *actual total month* is in,
                                # relative to where the "Month" *header* was found.
                                if i <= 1: # Pages 1 & 2 (0-indexed i=0,1)
                                    # On these pages, total month data is in the *same column* as the "Month" header.
                                    actual_data_access_idx = pdf_col_idx_where_header_was_found
                                else: # Pages 3+ (i>=2)
                                    # On these pages, total month data is in the column *after* the "Month" header's column.
                                    actual_data_access_idx = pdf_col_idx_where_header_was_found + 1
                            else: # For percentile headers ("3rd", "15th", etc.)
                                actual_data_access_idx = pdf_col_idx_where_header_was_found + data_column_offset_for_percentiles
                            
                            # Boundary check for the calculated access index
                            if not (0 <= actual_data_access_idx < len(normalized_data_row)):
                                missing_reason = f"Calculated index {actual_data_access_idx} for '{target_h_name}' (header at {pdf_col_idx_where_header_was_found}, page_offset_for_perc {data_column_offset_for_percentiles if target_h_name != 'Month' else 'N/A for Month'}) is out of bounds for data row of length {len(normalized_data_row)}. Row sample: {normalized_data_row[:7]}..."
                                valid_point = False; break
                            
                            value_str = normalized_data_row[actual_data_access_idx]

                            if not value_str: # If the cell is empty after stripping
                                extracted_data_point[target_h_name] = None # Store None, will be checked later
                                continue

                            try:
                                if target_h_name == "Month":
                                    month_val_str = value_str.split('(')[0].strip() # Remove any bracketed text like (continued)
                                    if not month_val_str: 
                                        missing_reason = f"Month value '{value_str}' became empty after processing."
                                        valid_point = False; break
                                    int(month_val_str) # Validate it's an integer
                                    extracted_data_point[target_h_name] = month_val_str
                                elif target_h_name == "50th" and ' ' in value_str: # Handle merged "25th 50th" case
                                    parts = value_str.split()
                                    numeric_val_str = parts[1] if len(parts) > 1 else value_str # Default to whole if split fails unexpectedly
                                    float(numeric_val_str) # Validate
                                    extracted_data_point[target_h_name] = numeric_val_str
                                else:
                                    float(value_str) # Validate
                                    extracted_data_point[target_h_name] = value_str
                            except ValueError:
                                missing_reason = f"Value '{value_str}' for target '{target_h_name}' is not a valid number."
                                valid_point = False; break
                        
                        if not valid_point:
                            # print(f"        INVALID ROW (Page {i+1}, Table {table_idx+1}, DataRowInTable {r_idx+1}, OrigPDFRow~ {start_row_for_data_in_table + r_idx + 1}): {missing_reason}")
                            # print(f"          Problematic Row Content (first 7 cells): {normalized_data_row[:7]}")
                            continue

                        # Check if all required headers got a value (even if None, they must be processed)
                        all_required_present_and_valid = all(h in extracted_data_point for h in target_data_headers)
                        if all_required_present_and_valid and extracted_data_point.get("Month") is not None:
                            # print(f"        SUCCESS: Adding data. Month: {extracted_data_point.get('Month')}, 3rd: {extracted_data_point.get('3rd')}")
                            all_extracted_rows.append(extracted_data_point)
                        # else:
                            # reason = "Missing required value(s)" if not all_required_present_and_valid else "Month value is None"
                            # print(f"        INCOMPLETE ROW (Page {i+1}, Table {table_idx+1}, DataRowInTable {r_idx+1}): {reason}. Data: {extracted_data_point}")

        if not all_extracted_rows:
            print(f"No data rows fully extracted from {pdf_path}. CSV will not be created.")
            return

        # Sort by month before writing
        all_extracted_rows.sort(key=lambda x: int(x["Month"])) 

        with open(output_csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=target_data_headers)
            writer.writeheader()
            writer.writerows(all_extracted_rows)
        print(f"Successfully extracted {len(all_extracted_rows)} rows to {output_csv_path}")

    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Assume the script is in a subdirectory like 'statistics_engine'
    # Get the project root directory (one level up from where the script is)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'who_standards')

    pdf_files_to_process = {
        'boys': {
            'pdf': os.path.join(DATA_DIR, 'hfa-boys-5-19years-per.pdf'),
            'csv': os.path.join(DATA_DIR, 'hfa_boys_p_5_19.csv')
        },
        'girls': {
            'pdf': os.path.join(DATA_DIR, 'hfa-girls-5-19years-per.pdf'),
            'csv': os.path.join(DATA_DIR, 'hfa_girls_p_5_19.csv')
        }
    }

    for sex, paths in pdf_files_to_process.items():
        print(f"--- Processing {sex.capitalize()} HFA 5-19 years ---")
        if os.path.exists(paths['pdf']):
            extract_hfa_percentiles_from_pdf(paths['pdf'], paths['csv'])
        else:
            print(f"PDF file not found: {paths['pdf']}")
        print("\n")

    print("PDF processing finished.")