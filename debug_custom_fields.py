from app import app
from database import get_active_custom_demographic_fields

with app.app_context():
    try:
        fields = get_active_custom_demographic_fields()
        print('✅ Custom fields loaded:', fields)
    except Exception as e:
        print('❌ Custom fields error:', e)
        import traceback
        traceback.print_exc() 