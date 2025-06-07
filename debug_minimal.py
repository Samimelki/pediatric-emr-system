from flask import Flask, render_template
from emr_config import emr_config
from database import get_active_custom_demographic_fields, init_db_schema

# Create minimal Flask app
app = Flask(__name__)
app.config['DEBUG'] = True
app.config['DATABASE'] = emr_config.get_database_path()

# Initialize database
with app.app_context():
    init_db_schema()

@app.route('/')
def index():
    return "Home Page"

@app.route('/test')
def test_route():
    try:
        emr_mode = emr_config.get_emr_mode()
        emr_features = emr_config.get_enabled_features()
        custom_fields = get_active_custom_demographic_fields()
        
        return render_template('unified_add_patient.html', 
                             title='Add New Patient',
                             emr_mode=emr_mode,
                             emr_features=emr_features,
                             custom_fields=custom_fields)
    except Exception as e:
        import traceback
        return f"<pre>Error: {e}\n\nTraceback:\n{traceback.format_exc()}</pre>"

if __name__ == '__main__':
    with app.test_client() as client:
        response = client.get('/test')
        print(f'Status: {response.status_code}')
        print(f'Content: {response.get_data(as_text=True)[:1000]}...') 