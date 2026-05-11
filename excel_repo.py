from __future__ import annotations

from datetime import datetime
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

Base = declarative_base()


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)

    # store hashed password (werkzeug.security)
    password_hash = Column(String(255), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)

    # task | quiz | material
    kind = Column(String(20), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # optional for task/quiz
    deadline = Column(String(50), nullable=True)

    # optional attachment uploaded by doctor (relative path inside uploads/)
    attachment_path = Column(String(400), nullable=True)

    # who created it
    created_by = Column(String(80), nullable=False, index=True)  # doctor username

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    assignments = relationship(
        "TaskAssignment",
        back_populates="task",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True)

    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)

    # student code/id from excel
    student_code = Column(String(50), nullable=False, index=True)

    # uploaded submission (relative path inside uploads/)
    submitted_path = Column(String(400), nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    task = relationship("Task", back_populates="assignments")

    __table_args__ = (
        # useful to prevent duplicates for same task+student (optional but recommended)
        Index("ix_assignment_task_student", "task_id", "student_code", unique=True),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)

    student_code = Column(String(50), nullable=False, index=True)

    doctor_username = Column(String(80), nullable=False, index=True)

    text = Column(Text, nullable=True)
    attachment_path = Column(String(400), nullable=True)  # relative path inside uploads/

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)

    doctor_username = Column(String(80), nullable=False, index=True)

    # SEND_TASK / SEND_QUIZ / SEND_MATERIAL / SEND_MESSAGE / SUBMISSION
    action = Column(String(50), nullable=False, index=True)

    details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)


def make_db(db_url: str):
    engine = create_engine(db_url, future=True)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        future=True
    )
    return engine, SessionLocal