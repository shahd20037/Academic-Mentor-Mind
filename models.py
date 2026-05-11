from __future__ import annotations
from datetime import datetime
from extensions import db
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Student(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    code = db.Column(db.String(50), unique=True)

    name = db.Column(db.String(100))
    email = db.Column(db.String(100))

    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))

    attendance = db.Column(db.Integer, default=0)
    assignments = db.Column(db.Integer, default=0)
    midterm = db.Column(db.Integer, default=0)
    final = db.Column(db.Integer, default=0)

    study_hours = db.Column(db.Integer, default=0)

    GPA = db.Column(db.Float, default=0)

    image = db.Column(db.String(200))
# ===== Base =====
Base = declarative_base()

# ===== TutorInteraction =====
class TutorInteraction(Base):
    __tablename__ = "tutor_interaction"

    id = Column(Integer, primary_key=True)
    student_code = Column(String(50), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

# ===== Doctor =====
class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # hashed password
    created_at = Column(DateTime, default=datetime.utcnow)

# ===== Task =====
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    kind = Column(String(20), nullable=False, index=True)  # task | quiz | material
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    deadline = Column(String(50), nullable=True)
    attachment_path = Column(String(400), nullable=True)
    created_by = Column(String(80), nullable=False, index=True)  # doctor username
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    assignments = relationship(
        "TaskAssignment",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

# ===== TaskAssignment =====
class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    student_code = Column(String(50), nullable=False, index=True)
    submitted_path = Column(String(400), nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="assignments")

    __table_args__ = (
        Index("ix_assignment_task_student", "task_id", "student_code", unique=True),
    )

# ===== Message =====
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    student_code = Column(String(50), nullable=False, index=True)
    doctor_username = Column(String(80), nullable=False, index=True)
    text = Column(Text, nullable=True)
    attachment_path = Column(String(400), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

# ===== ActivityLog =====
class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    doctor_username = Column(String(80), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)  # SEND_TASK / SUBMISSION / etc
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

# ===== AttendanceSession (QR Code) =====
class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True)
    doctor_username = Column(String(80), nullable=False, index=True)
    session_name = Column(String(200), nullable=False)
    qr_code_token = Column(String(100), unique=True, nullable=False)
    is_active = Column(Integer, default=1) # 1 for active, 0 for closed
    created_at = Column(DateTime, default=datetime.utcnow)

# ===== AttendanceRecord =====
class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    student_code = Column(String(50), nullable=False, index=True)
    marked_at = Column(DateTime, default=datetime.utcnow)

    # ===== Integrity Report Fields =====
    ip_address   = Column(String(50),  nullable=True)   # IP of the device used
    latitude     = Column(String(30),  nullable=True)   # GPS latitude (if provided)
    longitude    = Column(String(30),  nullable=True)   # GPS longitude (if provided)
    attempt_count = Column(Integer, default=1)          # how many times student tried to submit
    is_suspicious = Column(Integer, default=0)          # 1 = flagged, 0 = clean
    suspicious_reason = Column(String(200), nullable=True)  # e.g. "Multiple attempts", "Duplicate IP"

    __table_args__ = (
        Index("ix_attendance_session_student", "session_id", "student_code", unique=True),
    )

# ===== ProctoringLog =====
class ProctoringLog(Base):
    __tablename__ = "proctoring_logs"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    student_code = Column(String(50), nullable=False, index=True)
    violation_type = Column(String(100), nullable=False) # TAB_SWITCH, FACE_NOT_FOUND, MULTIPLE_FACES, LOOKING_AWAY, NOISE_DETECTED
    details = Column(Text, nullable=True)
    screenshot_path = Column(String(400), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ===== Exam Session =====
class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True)
    doctor_username = Column(String(100), nullable=False)
    subject_name = Column(String(200), nullable=False)
    is_active = Column(Integer, default=1)
    camera_enabled = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

# ===== Exam Participation =====
class ExamParticipation(Base):
    __tablename__ = "exam_participations"

    id = Column(Integer, primary_key=True)
    exam_id = Column(Integer, ForeignKey("exam_sessions.id", ondelete="CASCADE"), nullable=False)
    student_code = Column(String(50), nullable=False, index=True)
    status = Column(String(20), default="entered") # entered, finished, locked, not_entered
    score = Column(Integer, nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_exam_participation_student", "exam_id", "student_code", unique=True),
    )

# ===== Notification =====
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    student_code = Column(String(50), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Integer, default=0) # 0 for unread, 1 for read
    created_at = Column(DateTime, default=datetime.utcnow)

# ===== QuickPoll =====
class QuickPoll(Base):
    __tablename__ = "quick_polls"

    id = Column(Integer, primary_key=True)
    doctor_username = Column(String(80), nullable=False, index=True)
    question = Column(Text, nullable=False)
    is_active = Column(Integer, default=1) # 1 for active, 0 for closed
    created_at = Column(DateTime, default=datetime.utcnow)

# ===== PollAnswer =====
class PollAnswer(Base):
    __tablename__ = "poll_answers"

    id = Column(Integer, primary_key=True)
    poll_id = Column(Integer, ForeignKey("quick_polls.id", ondelete="CASCADE"), nullable=False)
    student_code = Column(String(50), nullable=False, index=True)
    answer = Column(String(10), nullable=False) # 'yes' or 'no'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_poll_answer_student", "poll_id", "student_code", unique=True),
    )

# ===== PollResponse =====
class PollResponse(Base):
    __tablename__ = "poll_responses"

    id = Column(Integer, primary_key=True)
    student_code = Column(String(50), nullable=False, index=True)
    rating = Column(Integer, nullable=False) # e.g., 1-5
    feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

# ===== StudentProject =====
class StudentProject(Base):
    __tablename__ = "student_projects"

    id = Column(Integer, primary_key=True)
    student_code = Column(String(50), nullable=False, index=True)
    student_name = Column(String(100), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    code_path = Column(String(400), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    interactions = relationship("ProjectInteraction", back_populates="project", cascade="all, delete-orphan")

# ===== ProjectInteraction =====
class ProjectInteraction(Base):
    __tablename__ = "project_interactions"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("student_projects.id", ondelete="CASCADE"), nullable=False)
    student_code = Column(String(50), nullable=False, index=True)
    type = Column(String(20), nullable=False) # 'love' or 'save'
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("StudentProject", back_populates="interactions")

    __table_args__ = (
        Index("ix_project_interaction_user", "project_id", "student_code", "type", unique=True),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)

    sender = Column(String)
    receiver = Column(String)

    message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

# ===== make_db function =====
def make_db(db_url: str):
    engine = create_engine(db_url, future=True)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True
    )
    return engine, SessionLocal