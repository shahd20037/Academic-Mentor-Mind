import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Project base dir (absolute)
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # Optional bootstrap admin (first run)
    DOCTOR_USERNAME = os.getenv("DOCTOR_USERNAME")
    DOCTOR_PASSWORD = os.getenv("DOCTOR_PASSWORD")
    MANAGER_PASSWORD = os.getenv("MANAGER_PASSWORD", "admin123")

    # Paths (absolute)
    EXCEL_PATH = os.path.join(
        BASE_DIR,
        "data",
        "Student_performance_dataset.xlsx"
     )
    DB_URL = os.getenv(
        "DB_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
    )

    UPLOAD_BASE_DIR = os.getenv(
        "UPLOAD_BASE_DIR",
        os.path.join(BASE_DIR, "uploads")
    )

    UPLOAD_SOLUTIONS_DIR = os.path.join(UPLOAD_BASE_DIR, "solutions")
    UPLOAD_DOCTOR_DIR = os.path.join(UPLOAD_BASE_DIR, "doctor_uploads")
    UPLOAD_MESSAGES_DIR = os.path.join(UPLOAD_BASE_DIR, "messages")

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))  # 25 MB