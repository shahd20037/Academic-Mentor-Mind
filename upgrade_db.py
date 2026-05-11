from sqlalchemy import inspect
from config import Config
from models import Base, make_db

if __name__ == "__main__":
    engine, _ = make_db(Config.DB_URL)
    inspector = inspect(engine)

    existing_tables = set(inspector.get_table_names())
    defined_tables = set(Base.metadata.tables.keys())

    missing_tables = defined_tables - existing_tables

    if missing_tables:
        Base.metadata.create_all(engine)
        print("Upgrade done. Created tables:", ", ".join(missing_tables))
    else:
        print("No upgrade needed. Database is up to date.")
