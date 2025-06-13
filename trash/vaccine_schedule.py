# vaccine_schedule.py - Default Vaccine Schedule Configuration
# This defines the recommended ages for each vaccine dose

# Default Lebanon/WHO-based pediatric vaccine schedule (ages in months)
DEFAULT_VACCINE_SCHEDULE = {
    # Mandatory Vaccines
    "DTaP - IPV": {
        "category": "mandatory",
        "doses": {
            "d1": {"age_months": 2, "label": "Dose 1"},
            "d2": {"age_months": 4, "label": "Dose 2"}, 
            "d3": {"age_months": 6, "label": "Dose 3"},
            "r1": {"age_months": 18, "label": "Booster 1"},
            "r2": {"age_months": 60, "label": "Booster 2"}  # 5 years
        }
    },
    "Hepatitis B": {
        "category": "mandatory",
        "doses": {
            "d1": {"age_months": 0, "label": "Birth"},  # At birth
            "d2": {"age_months": 2, "label": "Dose 2"},
            "d3": {"age_months": 6, "label": "Dose 3"}
        }
    },
    "Hib (Haemophilus influenzae b)": {
        "category": "mandatory", 
        "doses": {
            "d1": {"age_months": 2, "label": "Dose 1"},
            "d2": {"age_months": 4, "label": "Dose 2"},
            "d3": {"age_months": 6, "label": "Dose 3"},
            "r1": {"age_months": 15, "label": "Booster"}
        }
    },
    "MMR (Measles, Mumps, Rubella)": {
        "category": "mandatory",
        "doses": {
            "d1": {"age_months": 12, "label": "Dose 1"},
            "d2": {"age_months": 18, "label": "Dose 2"}
        }
    },
    "PCV": {  # Pneumococcal Conjugate Vaccine
        "category": "mandatory",
        "doses": {
            "d1": {"age_months": 2, "label": "Dose 1"},
            "d2": {"age_months": 4, "label": "Dose 2"},
            "d3": {"age_months": 6, "label": "Dose 3"},
            "r1": {"age_months": 15, "label": "Booster"}
        }
    },
    "Rotavirus": {
        "category": "mandatory",
        "doses": {
            "d1": {"age_months": 2, "label": "Dose 1"},
            "d2": {"age_months": 4, "label": "Dose 2"},
            "d3": {"age_months": 6, "label": "Dose 3"}
        }
    },
    
    # Recommended Vaccines
    "Meningococcal ACWY": {
        "category": "recommended",
        "doses": {
            "d1": {"age_months": 12, "label": "Dose 1"},
            "r1": {"age_months": 132, "label": "Booster"}  # 11 years
        }
    },
    "Varicella": {
        "category": "recommended",
        "doses": {
            "d1": {"age_months": 12, "label": "Dose 1"},
            "d2": {"age_months": 18, "label": "Dose 2"}
        }
    },
    "Hepatitis A": {
        "category": "recommended", 
        "doses": {
            "d1": {"age_months": 12, "label": "Dose 1"},
            "d2": {"age_months": 18, "label": "Dose 2"}
        }
    },
    "HPV": {
        "category": "recommended",
        "doses": {
            "d1": {"age_months": 132, "label": "Dose 1"},  # 11 years
            "d2": {"age_months": 134, "label": "Dose 2"}   # 11 years + 2 months
        }
    },
    "Influenza": {
        "category": "recommended",
        "doses": {
            "d1": {"age_months": 6, "label": "Annual"}  # Starting at 6 months, then yearly
        }
    }
}

def get_vaccine_schedule():
    """Get the default vaccine schedule"""
    return DEFAULT_VACCINE_SCHEDULE

def get_mandatory_vaccines():
    """Get list of mandatory vaccine names"""
    return [name for name, info in DEFAULT_VACCINE_SCHEDULE.items() 
            if info["category"] == "mandatory"]

def get_recommended_vaccines():
    """Get list of recommended vaccine names"""
    return [name for name, info in DEFAULT_VACCINE_SCHEDULE.items() 
            if info["category"] == "recommended"]

def get_vaccine_doses(vaccine_name):
    """Get dose schedule for a specific vaccine"""
    return DEFAULT_VACCINE_SCHEDULE.get(vaccine_name, {}).get("doses", {}) 