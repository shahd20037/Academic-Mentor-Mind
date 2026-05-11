from sqlalchemy import create_engine
from models import Base
from config import Config

# نعمل engine باستخدام DB_URL من config
engine = create_engine(Config.DB_URL, future=True)

# ننشئ كل الجداول اللي معرفينها في models.py
Base.metadata.create_all(engine)

print("✅ All tables created successfully!")