from app import app
import logging

# Enable debug mode
app.config['DEBUG'] = True
app.config['TESTING'] = True

# Set up logging
logging.basicConfig(level=logging.DEBUG)

with app.test_client() as client:
    try:
        response = client.get('/patient/new')
        print(f'Status: {response.status_code}')
        if response.status_code == 500:
            print('Response data:')
            print(response.get_data(as_text=True))
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc() 