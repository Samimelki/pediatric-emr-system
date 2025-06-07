from app import app
from emr_config import emr_config
from database import get_active_custom_demographic_fields
from flask import render_template

with app.app_context():
    try:
        emr_mode = emr_config.get_emr_mode()
        emr_features = emr_config.get_enabled_features()
        custom_fields = get_active_custom_demographic_fields()
        
        print('EMR Mode:', emr_mode)
        print('EMR Features:', emr_features)
        print('Custom Fields:', custom_fields)
        
        # Try to render the template
        html = render_template('unified_add_patient.html', 
                             title='Add New Patient',
                             emr_mode=emr_mode,
                             emr_features=emr_features,
                             custom_fields=custom_fields)
        print('✅ Template rendered successfully!')
        print('HTML length:', len(html))
        
    except Exception as e:
        print('❌ Template rendering failed:', e)
        import traceback
        traceback.print_exc() 