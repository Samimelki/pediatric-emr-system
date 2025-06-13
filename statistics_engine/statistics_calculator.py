import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
from flask import g
from collections import defaultdict
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Tuple, Optional, Any
import emr_config

def convert_weight_to_kg(weight_raw):
    """
    Convert weight value to kg according to the storage format rules:
    - 2 digits (10-99): Already in kg, display as-is
    - 500-9999: In grams, divide by 1000 to display as kg
    - 10000+: Would be stored as kg value (e.g., 10 for 10kg), display as-is
    """
    if weight_raw is None:
        return None
    
    try:
        weight_val = float(weight_raw)
        
        # 2 digits (10-99): already in kg
        if 10 <= weight_val <= 99:
            return weight_val
        
        # 500-9999: stored in grams, convert to kg
        elif 500 <= weight_val <= 9999:
            return weight_val / 1000.0
        
        # 10000+: this shouldn't happen as per user, but if it does, treat as kg
        elif weight_val >= 10000:
            return weight_val / 1000.0
        
        # Less than 10: assume kg (edge case)
        else:
            return weight_val
            
    except (ValueError, TypeError):
        return None

def get_db_standalone(db_path=None):
    """
    Get database connection for standalone use (outside Flask context)
    """
    if db_path is None:
        # Use the configured database path
        config = emr_config.EMRConfig()
        db_path = config.get_database_path()
    
    if hasattr(g, '_database') and g._database is not None:
        return g._database
    
    db = g._database = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db

def close_db_standalone(exception=None):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
        g._database = None # Ensure it's removed from g

def calculate_average_vaccines_per_child(db_path=None):
    """Calculate average number of vaccines per child"""
    if db_path is None:
        config = emr_config.EMRConfig()
        db_path = config.get_database_path()
    
    # You might want to make the database path configurable
    conn = get_db_standalone(db_path=db_path)

    cursor = conn.cursor()

    try:
        # Get all patient IDs
        cursor.execute("SELECT id FROM Patients")
        patients = cursor.fetchall()

        if not patients:
            return 0  # No patients, so average is 0

        total_vaccines_all_patients = 0
        num_patients = len(patients)

        # Standard vaccine columns in the Patients table
        # Excluding monotest as they are tests, not vaccines based on previous context
        standard_vaccine_columns = [
            'rougeole_seule_date',
            'dtcp1_date', 'dtcp2_date', 'dtcp3_date',
            'dtcp_rappel1_date', 'dtcp_rappel2_date', 'dtcp_rappel3_date', 'dtcp_rappel4_date',
            'hep_b1_date', 'hep_b2_date', 'hep_b3_date',
            'hib1_date', 'hib2_date', 'hib3_date', 'hib_rappel_date',
            'ror_date'
        ]

        for patient in patients:
            patient_id = patient['id']
            patient_vaccine_count = 0

            # Count standard vaccines
            # Construct the query safely to select specific columns for the current patient
            columns_to_select = ", ".join(standard_vaccine_columns)
            cursor.execute(f"SELECT {columns_to_select} FROM Patients WHERE id = ?", (patient_id,))
            patient_std_vaccines = cursor.fetchone()

            if patient_std_vaccines:
                for col in standard_vaccine_columns:
                    if patient_std_vaccines[col] is not None and str(patient_std_vaccines[col]).strip() != "":
                        patient_vaccine_count += 1
            
            # Count non-standard vaccines
            cursor.execute("SELECT COUNT(*) FROM NonStandardVaccines WHERE patient_id = ? AND vaccine_date IS NOT NULL AND vaccine_date != ''", (patient_id,))
            non_standard_vaccine_count = cursor.fetchone()[0]
            patient_vaccine_count += non_standard_vaccine_count

            total_vaccines_all_patients += patient_vaccine_count

        average_vaccines = total_vaccines_all_patients / num_patients if num_patients > 0 else 0
        return average_vaccines

    finally:
        # Only close if we established a new connection directly through db_path
        # If using Flask's g, it should be managed by app teardown context.
        if db_path: # or if we know this function solely uses its own connection cycle
            close_db_standalone() 
        # If get_db_standalone used current_app.config['DATABASE'], the connection is on g
        # and should be closed by the Flask app's teardown_appcontext handler.
        # For simplicity in a mixed-use module, if db_path was not given,
        # assume it might be using 'g' and let Flask manage it.

EXPECTED_PERCENTILES_STATS = [3, 15, 50, 85, 97]
EXPECTED_PERCENTILES_KEYS_STATS = ["P3", "P15", "P50", "P85", "P97"]

def moving_average(data, window_size):
    """Calculates the moving average of a list of numbers."""
    if not data or window_size <= 0:
        return data
    # Pad with None for elements where full window is not available at the start
    # or return a shorter list. For plotting, it's often better to have same length.
    # Simple approach: use original value if window cannot be formed.
    smoothed = []
    for i in range(len(data)):
        start_index = max(0, i - window_size // 2)
        end_index = min(len(data), i + window_size // 2 + 1)
        window = [x for x in data[start_index:end_index] if x is not None] # Ensure only valid numbers in window
        if window:
            smoothed.append(round(sum(window) / len(window), 2))
        elif data[i] is not None: # If window is empty but original data exists (e.g. isolated point)
             smoothed.append(data[i])
        else:
            smoothed.append(None) # If original data is also None
    return smoothed

def calculate_percentiles(db_path=None, target_percentiles=None, smoothing_window=0, max_age_months=228,
                          outlier_filter_sd_threshold=5.0, min_points_for_outlier_filtering=10):
    """
    Calculates local percentiles for weight, height, and head circumference
    based on all patient data in the EMR.

    Args:
        db_path (str, optional): Path to the SQLite database file.
        target_percentiles (list, optional): A list of integers for which percentiles to calculate.
        smoothing_window (int, optional): Size of the moving average window for smoothing. 
                                          0 or 1 means no smoothing.
        max_age_months (int, optional): Maximum age in months to calculate percentiles for.
                                      Defaults to 228 (19 years).
        outlier_filter_sd_threshold (float, optional): SD threshold to filter outliers before percentile calculation.
                                                   Measurements beyond this many SDs from the mean of their specific
                                                   age/sex/type group will be excluded. Defaults to 5.0.
                                                   Set to 0 or None to disable outlier filtering.
        min_points_for_outlier_filtering (int, optional): Minimum number of data points in an age/sex/type group
                                                        required to attempt outlier removal. Defaults to 10.

    Returns:
        dict: A dictionary containing the calculated percentiles, structured like:
              {
                  'wfa': {
                      'boys': {'Month': [...], 'P3': [...], ...},
                      'girls': {'Month': [...], 'P3': [...], ...}
                  },
                  'lhfa': { ... },
                  'hcfa': { ... }
              }
              Returns an empty dict if no data or error.
    """
    if target_percentiles is None:
        target_percentiles = EXPECTED_PERCENTILES_STATS
    
    percentile_keys = [f"P{p}" for p in target_percentiles]

    if db_path is None:
        try:
            conn = get_db_standalone()
        except RuntimeError:
            conn = get_db_standalone(db_path='emr_database.db')
    else:
        conn = get_db_standalone(db_path=db_path)

    cursor = conn.cursor()
    all_measurements = {
        'boys': {
            'wfa': defaultdict(list), # Key: age_in_months, Value: list of weights
            'lhfa': defaultdict(list), # Key: age_in_months, Value: list of heights
            'hcfa': defaultdict(list)  # Key: age_in_months, Value: list of head circumferences
        },
        'girls': {
            'wfa': defaultdict(list),
            'lhfa': defaultdict(list),
            'hcfa': defaultdict(list)
        }
    }

    try:
        # Fetch all patients with birth date and sex
        cursor.execute("SELECT id, naissance_date, sexe FROM Patients WHERE naissance_date IS NOT NULL AND sexe IS NOT NULL")
        patients = cursor.fetchall()

        if not patients:
            print("No patients with birth date and sex found to calculate percentiles.")
            return {}

        for patient_row in patients:
            patient_id = patient_row['id']
            patient_birth_date_iso = patient_row['naissance_date']
            patient_sex_db = patient_row['sexe']

            who_sex = None
            if patient_sex_db:
                sex_lower = patient_sex_db.lower()
                if sex_lower in ['m', 'male', 'garçon', 'boy', 'boys', 'masculin']:
                    who_sex = "boys"
                elif sex_lower in ['f', 'female', 'fille', 'girl', 'girls', 'féminin', 'feminin']:
                    who_sex = "girls"
            
            if not who_sex or not patient_birth_date_iso:
                continue # Skip if sex or DOB is unknown

            try:
                birth_dt = datetime.fromisoformat(patient_birth_date_iso.split('T')[0])
            except ValueError:
                # print(f"Invalid birth date format for patient {patient_id}: {patient_birth_date_iso}. Skipping patient.")
                continue

            # Fetch all visits for this patient
            cursor.execute("SELECT visit_date, weight_g, height_cm, head_circumference_cm FROM Visits WHERE patient_id = ? AND visit_date IS NOT NULL ORDER BY visit_date ASC", (patient_id,))
            visits = cursor.fetchall()

            for visit_row in visits:
                visit_date_iso = visit_row['visit_date']
                weight_g = visit_row['weight_g']
                height_cm = visit_row['height_cm']
                hc_cm = visit_row['head_circumference_cm']

                try:
                    visit_dt = datetime.fromisoformat(visit_date_iso.split('T')[0])
                    age_delta = relativedelta(visit_dt, birth_dt)
                    # Round age to nearest whole month for grouping
                    age_in_total_months = age_delta.years * 12 + age_delta.months
                    if age_delta.days > 15 and age_in_total_months < (max_age_months -1) : # round up if more than half a month, avoid exceeding max age
                        age_in_total_months +=1
                        
                    if 0 <= age_in_total_months <= max_age_months:
                        if weight_g is not None and weight_g > 0:
                            all_measurements[who_sex]['wfa'][age_in_total_months].append(convert_weight_to_kg(weight_g))
                        if height_cm is not None and height_cm > 0:
                            all_measurements[who_sex]['lhfa'][age_in_total_months].append(height_cm)
                        if hc_cm is not None and hc_cm > 0:
                            # Head circumference typically tracked up to 5 years (60 months) for standard charts
                            if age_in_total_months <= 60: 
                                all_measurements[who_sex]['hcfa'][age_in_total_months].append(hc_cm)
                except ValueError:
                    # print(f"Invalid visit date format for patient {patient_id}, visit date {visit_date_iso}. Skipping visit.")
                    continue
        
        # Calculate percentiles
        output_percentiles = {
            'wfa': {'boys': defaultdict(list), 'girls': defaultdict(list)},
            'lhfa': {'boys': defaultdict(list), 'girls': defaultdict(list)},
            'hcfa': {'boys': defaultdict(list), 'girls': defaultdict(list)}
        }

        # Step 1: Outlier Filtering - Create a new structure for filtered measurements
        filtered_measurements = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for sex_key in all_measurements:
            for m_type_key in all_measurements[sex_key]:
                for age_month_key, measurements_at_age in all_measurements[sex_key][m_type_key].items():
                    if outlier_filter_sd_threshold and outlier_filter_sd_threshold > 0 and \
                       len(measurements_at_age) >= min_points_for_outlier_filtering:
                        
                        mean_val = np.mean(measurements_at_age)
                        std_dev_val = np.std(measurements_at_age)

                        if std_dev_val > 0: # Only filter if there is variance
                            current_filtered_list = []
                            for val in measurements_at_age:
                                if abs(val - mean_val) / std_dev_val <= outlier_filter_sd_threshold:
                                    current_filtered_list.append(val)
                            if not current_filtered_list: # Safeguard: if all points were filtered, use original (rare)
                                 filtered_measurements[sex_key][m_type_key][age_month_key] = list(measurements_at_age)
                            else:
                                filtered_measurements[sex_key][m_type_key][age_month_key] = current_filtered_list
                        else: # No variance, copy all
                            filtered_measurements[sex_key][m_type_key][age_month_key] = list(measurements_at_age)
                    else: # Not enough points to filter or filtering disabled, copy all
                        filtered_measurements[sex_key][m_type_key][age_month_key] = list(measurements_at_age)

        # Step 3: Percentile Calculation (using filtered_measurements)
        for sex in ['boys', 'girls']:
            for measurement_type in ['wfa', 'lhfa', 'hcfa']:
                # Sort ages to ensure 'Month' column is ordered, based on original keys collected if filtered list is sparse
                # but it's better to use keys from filtered_measurements if it now defines the available ages with data.
                # However, all_measurements has all age keys where data was initially found.
                # We need to ensure that Month array corresponds to percentile arrays.
                
                # Get all unique age months available across original and filtered data for this sex/type
                # This ensures 'Month' array covers all points that *could* have data.
                # Using keys from `all_measurements` ensures we iterate through all months that originally had data.
                original_age_keys = sorted(all_measurements[sex][measurement_type].keys())
                output_percentiles[measurement_type][sex]['Month'] = list(original_age_keys)
                
                for p_key in percentile_keys:
                    output_percentiles[measurement_type][sex][p_key] = [] # Initialize percentile lists

                for age_month in original_age_keys:
                    # Use measurements from the filtered set for this age_month
                    data_for_percentile_calc = filtered_measurements[sex][measurement_type].get(age_month, [])
                    
                    if data_for_percentile_calc: # If list is not empty after filtering
                        calculated_p_values = np.percentile(data_for_percentile_calc, target_percentiles)
                        for i, p_key in enumerate(percentile_keys):
                            output_percentiles[measurement_type][sex][p_key].append(round(calculated_p_values[i], 2) if calculated_p_values[i] is not None else None)
                    else:
                        # No data for this age_month after filtering (or initially), append None for all percentiles
                        for p_key in percentile_keys:
                            output_percentiles[measurement_type][sex][p_key].append(None)
                
                # Apply smoothing if window_size > 1
                if smoothing_window > 1:
                    for p_key in percentile_keys:
                        raw_series = output_percentiles[measurement_type][sex][p_key]
                        output_percentiles[measurement_type][sex][p_key] = moving_average(raw_series, smoothing_window)

        return output_percentiles

    except sqlite3.Error as e:
        print(f"Database error during percentile calculation: {e}")
        return {}
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred during percentile calculation: {e}")
        print(traceback.format_exc())
        return {}
    finally:
        if db_path: # or if we know this function solely uses its own connection cycle
            close_db_standalone()

def find_measurement_outliers(db_path=None, std_dev_threshold=4.0, age_limit_months=60):
    """
    Finds measurement outliers based on standard deviations from the mean 
    for age and sex groups.

    Args:
        db_path (str, optional): Path to the SQLite database.
        std_dev_threshold (float, optional): Number of standard deviations to consider an outlier.
        age_limit_months (int, optional): Maximum age in months to consider for this outlier detection pass.
                                        (e.g., 60 for up to 5 years, 228 for up to 19 years)

    Returns:
        list: A list of dictionaries, where each dictionary represents an outlier.
              e.g., {
                  'patient_mrn': 'MRN123',
                  'patient_id': 1,
                  'measurement_type': 'Weight (kg)',
                  'age_months': 12,
                  'value': 15.5,
                  'mean': 9.6,
                  'std_dev': 1.2,
                  'num_std_devs': 4.92
              }
    """
    if db_path is None:
        config = emr_config.EMRConfig()
        db_path = config.get_database_path()
    
    conn = get_db_standalone(db_path=db_path)
    
    cursor = conn.cursor()
    outliers_list = []

    # 1. Aggregate all measurements by type, sex, and age_month
    # Similar to calculate_percentiles, but we also need to store patient_id/mrn with each measurement
    all_measurements_for_stats = {
        'boys': {
            'wfa': defaultdict(list), # {age_month: [(value, patient_id, patient_mrn), ...]}
            'lhfa': defaultdict(list),
            'hcfa': defaultdict(list)
        },
        'girls': {
            'wfa': defaultdict(list),
            'lhfa': defaultdict(list),
            'hcfa': defaultdict(list)
        }
    }

    try:
        cursor.execute("SELECT id, mrn, naissance_date, sexe FROM Patients WHERE naissance_date IS NOT NULL AND sexe IS NOT NULL")
        patients = cursor.fetchall()

        if not patients: return []

        for patient_row in patients:
            patient_id = patient_row['id']
            patient_mrn = patient_row['mrn']
            patient_birth_date_iso = patient_row['naissance_date']
            patient_sex_db = patient_row['sexe']

            who_sex = None
            if patient_sex_db:
                sex_lower = patient_sex_db.lower()
                if sex_lower in ['m', 'male', 'garçon', 'boy', 'boys', 'masculin']:
                    who_sex = "boys"
                elif sex_lower in ['f', 'female', 'fille', 'girl', 'girls', 'féminin', 'feminin']:
                    who_sex = "girls"
            
            if not who_sex or not patient_birth_date_iso: continue

            try:
                birth_dt = datetime.fromisoformat(patient_birth_date_iso.split('T')[0])
            except ValueError: continue

            cursor.execute("SELECT visit_date, weight_g, height_cm, head_circumference_cm FROM Visits WHERE patient_id = ? AND visit_date IS NOT NULL", (patient_id,))
            visits = cursor.fetchall()

            for visit_row in visits:
                visit_date_iso = visit_row['visit_date']
                try:
                    visit_dt = datetime.fromisoformat(visit_date_iso.split('T')[0])
                    age_delta = relativedelta(visit_dt, birth_dt)
                    age_in_total_months = age_delta.years * 12 + age_delta.months
                    if age_delta.days > 15 and age_in_total_months < (age_limit_months -1) : # Round up, ensure not to exceed limit
                        age_in_total_months +=1
                    
                    if 0 <= age_in_total_months <= age_limit_months:
                        data_point = (patient_id, patient_mrn)
                        if visit_row['weight_g'] is not None and visit_row['weight_g'] > 0:
                            all_measurements_for_stats[who_sex]['wfa'][age_in_total_months].append(
                                (convert_weight_to_kg(visit_row['weight_g']), patient_id, patient_mrn)
                            )
                        if visit_row['height_cm'] is not None and visit_row['height_cm'] > 0:
                            all_measurements_for_stats[who_sex]['lhfa'][age_in_total_months].append(
                                (visit_row['height_cm'], patient_id, patient_mrn)
                            )
                        if visit_row['head_circumference_cm'] is not None and visit_row['head_circumference_cm'] > 0:
                             # Only consider HC for younger children, e.g., up to 60 months for typical outlier checks
                            if age_in_total_months <= 60: 
                                all_measurements_for_stats[who_sex]['hcfa'][age_in_total_months].append(
                                    (visit_row['head_circumference_cm'], patient_id, patient_mrn)
                                )
                except ValueError: continue

        # 2. Calculate mean & std dev for each group and find outliers
        measurement_type_map = {
            'wfa': 'Weight (kg)',
            'lhfa': 'Height (cm)',
            'hcfa': 'Head Circ. (cm)'
        }

        for sex in ['boys', 'girls']:
            for m_type_key, m_type_label in measurement_type_map.items():
                for age_month, measurements_with_ids in all_measurements_for_stats[sex][m_type_key].items():
                    values_only = [m[0] for m in measurements_with_ids]
                    if len(values_only) < 2: # Need at least 2 data points to calculate std dev meaningfully
                        continue
                    
                    mean_val = np.mean(values_only)
                    std_dev_val = np.std(values_only)

                    if std_dev_val == 0: # Avoid division by zero if all values in group are identical
                        continue 

                    for value, p_id, p_mrn in measurements_with_ids:
                        if value is None: continue
                        num_std_devs = abs(value - mean_val) / std_dev_val
                        if num_std_devs > std_dev_threshold:
                            outliers_list.append({
                                'patient_mrn': p_mrn,
                                'patient_id': p_id,
                                'measurement_type': m_type_label,
                                'sex': sex.capitalize(),
                                'age_months': age_month,
                                'value': round(value, 2),
                                'mean': round(mean_val, 2),
                                'std_dev': round(std_dev_val, 2),
                                'num_std_devs': round(num_std_devs, 2)
                            })
        
        # Sort outliers for consistent display, e.g., by how extreme they are
        outliers_list.sort(key=lambda x: x['num_std_devs'], reverse=True)
        return outliers_list

    except sqlite3.Error as e:
        print(f"Database error during outlier detection: {e}")
        return []
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred during outlier detection: {e}")
        print(traceback.format_exc())
        return []
    finally:
        if db_path:
            close_db_standalone()

if __name__ == '__main__':
    # Get the configured database path
    config = emr_config.EMRConfig()
    db_path = config.get_database_path()
    
    # You'll need to ensure the database exists or provide the correct path.
    print("Calculating average vaccines per child...")
    # avg_vaccines = calculate_average_vaccines_per_child(db_path='../unified_emr.db') # Adjusted path for being inside statistics_engine
    avg_vaccines = calculate_average_vaccines_per_child(db_path=db_path)
    print(f"Average vaccines per child: {avg_vaccines}")
    
    print("\nCalculating percentiles...")
    # Smoothing window of 3 means we'll average over 3-month windows
    # local_percentiles = calculate_percentiles(db_path='../unified_emr.db')
    local_percentiles = calculate_percentiles(db_path=db_path, smoothing_window=3)
    
    print("\nWeight percentiles (sample):")
    for age_months in [6, 12, 24, 36]:
        if age_months in local_percentiles['weight']:
            percentiles = local_percentiles['weight'][age_months]
            print(f"  {age_months} months: P10={percentiles['p10']:.1f}kg, P50={percentiles['p50']:.1f}kg, P90={percentiles['p90']:.1f}kg")
    
    print("\nHeight percentiles (sample):")
    for age_months in [6, 12, 24, 36]:
        if age_months in local_percentiles['height']:
            percentiles = local_percentiles['height'][age_months]
            print(f"  {age_months} months: P10={percentiles['p10']:.1f}cm, P50={percentiles['p50']:.1f}cm, P90={percentiles['p90']:.1f}cm")
    
    print("\nFinding outliers...")
    outliers = find_measurement_outliers(db_path=db_path, std_dev_threshold=4.0, age_limit_months=60)
    if outliers:
        print(f"Found {len(outliers)} outliers:")
        for i, outlier in enumerate(outliers[:5]): # Print top 5 outliers
            print(f"  {i+1}. Patient MRN: {outlier['patient_mrn']}, Type: {outlier['measurement_type']}, Age: {outlier['age_months']}m, Sex: {outlier['sex']}, Value: {outlier['value']}, Group Mean: {outlier['mean']}, Group SD: {outlier['std_dev']}, Num SDs: {outlier['num_std_devs']}")
        if len(outliers) > 5:
            print(f"  ... and {len(outliers) - 5} more.")
    else:
        print("No significant outliers found with the current criteria.") 