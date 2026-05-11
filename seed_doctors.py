from werkzeug.security import generate_password_hash
from config import Config
from models import Doctor, make_db

DEFAULT_DOCTORS = {
    "dr_osama": "Osama@123",
    "dr_sara": "Sara@123",
}

engine, SessionLocal = make_db(Config.DB_URL)
db = SessionLocal()

for username, pwd in DEFAULT_DOCTORS.items():
    d = db.query(Doctor).filter_by(username=username).first()
    if not d:
        db.add(Doctor(username=username, password_hash=generate_password_hash(pwd)))

db.commit()
db.close()

print("Done. Doctors seeded ✅")
