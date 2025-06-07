from flask import Flask
from routes.patient_routes import patient_bp
from routes.pdf_export_routes import pdf_export_bp
from emr_config import emr_config
from database import close_connection
from utils import format_datetime
import datetime

app = Flask(__name__)
app.secret_key = 'test'
app.config['DATABASE'] = '/Users/samimelki/Documents/UnifiedEMR/unified_emr.db'
app.jinja_env.filters['format_datetime'] = format_datetime
app.teardown_appcontext(close_connection)

@app.context_processor
def inject_emr_config():
    return {
        'emr_config': emr_config,
        'emr_mode': emr_config.get_emr_mode(),
        'emr_features': emr_config.get_enabled_features()
    }

app.register_blueprint(patient_bp)
app.register_blueprint(pdf_export_bp)

if __name__ == '__main__':
    print('Starting Flask app on port 5001...')
    app.run(debug=True, host='localhost', port=5001) 