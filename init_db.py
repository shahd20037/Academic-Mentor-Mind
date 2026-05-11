from config import Config
from models import Base, make_db

if __name__ == "__main__":
    engine, _ = make_db(Config.DB_URL)

    Base.metadata.create_all(engine)

    print("Database initialized / updated successfully.")
    print("Using DB:", Config.DB_URL)
