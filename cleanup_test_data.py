from app import app
from database import get_db

with app.app_context():
    db = get_db()
    db.execute('DELETE FROM Patients WHERE mrn LIKE "TEST%"')
    db.commit()
    print('Test data cleaned') 