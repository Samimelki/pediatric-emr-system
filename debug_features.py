from app import app
from emr_config import emr_config

with app.app_context():
    features = emr_config.get_enabled_features()
    print('Features type:', type(features))
    print('vaccines_enabled:', getattr(features, 'vaccines_enabled', 'MISSING'))
    print('All features:', features)
    print('Dir features:', dir(features)) 