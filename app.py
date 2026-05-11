import os
import sys
import logging
import io
import re
import PyPDF2
import os
import qrcode
from datetime import datetime
import pandas as pd
import config
from config import Config
from flask import (
     Flask, render_template, render_template_string, request, redirect, url_for,
    session, flash, jsonify, send_from_directory, abort, send_file
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy.orm import scoped_session, sessionmaker

from models import Base, make_db, Doctor, Task, TaskAssignment, Message, ActivityLog, ExamSession, ExamParticipation, Notification, PollResponse, TutorInteraction, StudentProject, ProjectInteraction, AttendanceSession, AttendanceRecord, ChatMessage, QuickPoll, PollAnswer
from ai_advisor import generate_ai_student_advice as generate_student_advice, process_pdf_and_answer
from models import TutorInteraction
from models import db, Student
from sqlalchemy import create_engine

DATABASE_URL = "sqlite:///test.db"

engine = create_engine(DATABASE_URL)
# ===============================
# Logging setup
# ===============================
logging.basicConfig(
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("mentor_mind")

# ===============================
# Flask setup
# ===============================
app = Flask(__name__)

def get_student_by_code(code):
    try:
        # قراءة ملف الإكسيل الجديد
        df = pd.read_excel("Student_performance_dataset.xlsx") 
        
        # البحث عن الطالب (مع تحويل الكود لنص لضمان المطابقة)
        student_row = df[df['code'].astype(str) == str(code)]
        
        if not student_row.empty:
            # تحويل الصف لقاموس (هنا يتحول لـ dict)
            return student_row.iloc[0].to_dict()
        return None
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return None

def calculate_gpa(student):
    try:
        # الوصول للبيانات باستخدام .get() لتجنب خطأ AttributeError
        # وإضافة "or 0" لضمان عدم وجود قيم فارغة (None)
        attendance  = float(student.get('attendance', 0) or 0)
        assignments = float(student.get('assignments', 0) or 0)
        midterm     = float(student.get('midterm', 0) or 0)
        final       = float(student.get('final', 0) or 0)

        # حساب المجموع الكلي (مثال: 10% حضور، 20% تكليفات، 30% ميدترم، 40% نهائي)
        total_score = (attendance * 0.1) + (assignments * 0.2) + (midterm * 0.3) + (final * 0.4)

        # تحويل المجموع (من 100) إلى نظام الـ 4.0
        # المعادلة: (المجموع / 100) * 4
        gpa_value = (total_score / 100) * 4
        
        # تقريب النتيجة لرقمان عشريان
        return round(gpa_value, 2)
    except Exception as e:
        print(f"Error in GPA calculation: {e}")
        return 0.0
    
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)
with app.app_context():
    db.create_all()
    # Also ensure the engine-based tables are created
    Base.metadata.create_all(engine)
app.secret_key = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
app.config.update(
    SESSION_COOKIE_NAME="mentor_mind_session",
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
)

# Ensure upload dirs exist
os.makedirs(Config.UPLOAD_BASE_DIR, exist_ok=True)
os.makedirs(Config.UPLOAD_SOLUTIONS_DIR, exist_ok=True)
os.makedirs(Config.UPLOAD_DOCTOR_DIR, exist_ok=True)
os.makedirs(Config.UPLOAD_MESSAGES_DIR, exist_ok=True)
os.makedirs(os.path.join(Config.UPLOAD_BASE_DIR, "projects"), exist_ok=True)

UPLOAD_DIR = Config.UPLOAD_BASE_DIR
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "mp4", "mov", "avi", "zip", "rar", "txt", "py", "js", "html", "css"}

# ===============================
# DB setup
# ===============================
engine, _ = make_db(Config.DB_URL)
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
)
Base.metadata.create_all(engine)

@app.teardown_appcontext
def remove_db_session(exception=None):
    SessionLocal.remove()

def get_db():
    return SessionLocal()


def read_pdf(path):
    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text



def search_answer(text, question):
    question = question.lower()
    lines = text.split("\n")

    best_paragraph = ""

    for i in range(len(lines)):
        line = lines[i].strip().lower()

        # 🚫 تجاهل الفهرس والكلام الفاضي
        if any(x in line for x in ["contents", "chapter", "page", "...."]):
            continue

        if any(word in line for word in question.split()):
            
            # 👇 خد 5 سطور بعده (مش سطر واحد)
            paragraph = " ".join(lines[i:i+5])

            if len(paragraph) > len(best_paragraph):
                best_paragraph = paragraph

    return best_paragraph if best_paragraph else "No answer found"


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

BOOKS = {
    "machine": os.path.join(BASE_DIR, "books", "content", "Machine book.pdf"),
    "ai": os.path.join(BASE_DIR, "books", "content", "AI book.pdf"),
    "CG": os.path.join(BASE_DIR, "books", "content", "Computer Graphic Book.pdf"),
    "pattern": os.path.join(BASE_DIR, "books", "content", "Pattern_Recognition.pdf"),
    "java": os.path.join(BASE_DIR, "books", "content", "Java book.pdf")
}



def search_in_books(question):
    folder = "books/content"

    best_match = ""
    best_score = 0

    question_words = question.lower().split()

    for file in os.listdir(folder):
        if file.endswith(".pdf"):
            path = os.path.join(folder, file)
            text = read_pdf(path)

            paragraphs = text.split("\n")

            for p in paragraphs:
                p_clean = p.strip().lower()

                if len(p_clean) < 50:
                    continue

                # نحسب score
                score = sum(1 for w in question_words if w in p_clean)

                if score > best_score:
                    best_score = score
                    best_match = p

    if best_match:
        return best_match[:500]

    return "مش لاقي إجابة مناسبة في الكتاب"




# ===============================
# Helpers
# ===============================
def normalize_col(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")

def load_students() -> pd.DataFrame:
    if not os.path.exists(Config.EXCEL_PATH):
        # Create a default Excel file if it doesn't exist
        df = pd.DataFrame(columns=["student_code", "name", "email", "attendance", "assignments", "midterm", "final", "gpa"])
        df.to_excel(Config.EXCEL_PATH, index=False)
        return df
    try:
        df = pd.read_excel(Config.EXCEL_PATH)
        df.columns = [normalize_col(c) for c in df.columns]
        return df
    except Exception as e:
        logger.error(f"Error reading Excel: {e}")
        return pd.DataFrame(columns=["student_code", "name", "email"])

def detect_student_code_column(df: pd.DataFrame) -> str | None:
    candidates = ["studentid", "student_id", "student_code", "studentcode", "code", "id"]
    for c in candidates:
        if c in df.columns: return c
    return None

def get_student_by_code(code: str) -> dict | None:
    try:
        df = load_students()
        col = detect_student_code_column(df)
        if not col: return None
        code = str(code).strip()
        # Convert column to string and clean it for comparison
        df[col] = df[col].astype(str).str.strip()
        row = df[df[col] == code]
        if row.empty: return None
        record = row.iloc[0].to_dict()
        if "name" not in record or str(record.get("name")).strip().lower() in ("", "nan"):
            record["name"] = code
        return record
    except Exception as e:
        logger.error(f"Error in get_student_by_code: {e}")
        return None

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def safe_join_uploads(rel_path: str) -> str | None:
    rel_path = (rel_path or "").strip().lstrip("/\\")
    full = os.path.abspath(os.path.join(UPLOAD_DIR, rel_path))
    root = os.path.abspath(UPLOAD_DIR)
    return full if full.startswith(root) else None

def require_student(): return session.get("student_code")
def require_doctor(): return session.get("doctor")
def require_manager(): return session.get("manager")

def log_activity(db, doctor_username: str, action: str, details: str = ""):
    try:
        db.add(ActivityLog(doctor_username=doctor_username, action=action, details=details))
        db.commit()
    except Exception as e:
        db.rollback()

def ensure_bootstrap_doctors():
    defaults = {"dr_osama": "Osama@123", "dr_sara": "Sara@123"}
    db = get_db()
    for username, pwd in defaults.items():
        if not db.query(Doctor).filter_by(username=username).first():
            db.add(Doctor(username=username, password_hash=generate_password_hash(pwd)))
    db.commit()

def create_notification(db, student_code, title, message):
    notif = Notification(
        student_code=str(student_code),
        title=title,
        message=message
    )
    db.add(notif)    

ensure_bootstrap_doctors()

# ===============================
# Routes
# ===============================
@app.route("/")
def root(): return redirect(url_for("home_page"))

@app.route("/home")
def home_page():
    return render_template("Home_page.html")

@app.route("/go-home")
def go_home():
    if require_manager(): return redirect(url_for("manager_dashboard"))
    if require_doctor(): return redirect(url_for("doctor_dashboard"))
    if require_student(): return redirect(url_for("student_dashboard"))
    return redirect(url_for("home_page"))

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    db = get_db()
    doctor_names = [d.username for d in db.query(Doctor).order_by(Doctor.username).all()]
    if request.method == "POST":
        role = (request.form.get("role") or "").strip().lower()
        if role=="student":
            code = (request.form.get("student_code") or "").strip()
            student = get_student_by_code(code)
            if student:
                session.clear()
                session["student_code"] = code
                return redirect(url_for("student_dashboard"))
            error = "Student code not found. Please sign up first."
        elif role=="doctor":
            username = (request.form.get("doctor_username_select") or "").strip()
            password = (request.form.get("doctor_password") or "").strip()
            doctor = db.query(Doctor).filter_by(username=username).first()
            if doctor and check_password_hash(doctor.password_hash,password):
                session.clear()
                session["doctor"] = doctor.username
                return redirect(url_for("doctor_dashboard"))
            error = "Invalid doctor credentials"
        elif role=="manager":
            password = (request.form.get("manager_password") or "").strip()
            if password == Config.MANAGER_PASSWORD:
                session.clear()
                session["manager"] = True
                return redirect(url_for("manager_dashboard"))
            error = "Invalid manager password"
    return render_template("login.html", error=error, doctor_names=doctor_names)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home_page"))

# ===============================
# Quick Polls Routes
# ===============================
@app.route("/doctor/create_poll", methods=["POST"])
def create_poll():
    doctor = require_doctor()
    if not doctor: return jsonify({"error": "Unauthorized"}), 401
    
    question = request.form.get("question")
    if not question: return jsonify({"error": "Question is required"}), 400
    
    db = get_db()
    # Deactivate previous polls by this doctor
    db.query(QuickPoll).filter_by(doctor_username=doctor, is_active=1).update({"is_active": 0})
    
    new_poll = QuickPoll(doctor_username=doctor, question=question)
    db.add(new_poll)
    db.commit()
    
    return jsonify({"success": True, "poll_id": new_poll.id})

@app.route("/doctor/poll_stats/<int:poll_id>")
def poll_stats(poll_id):
    doctor = require_doctor()
    if not doctor: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    poll = db.query(QuickPoll).filter_by(id=poll_id, doctor_username=doctor).first()
    if not poll: return jsonify({"error": "Poll not found"}), 404
    
    yes_count = db.query(PollAnswer).filter_by(poll_id=poll_id, answer='yes').count()
    no_count = db.query(PollAnswer).filter_by(poll_id=poll_id, answer='no').count()
    
    return jsonify({
        "question": poll.question,
        "yes": yes_count,
        "no": no_count,
        "is_active": poll.is_active
    })

@app.route("/doctor/close_poll/<int:poll_id>", methods=["POST"])
def close_poll(poll_id):
    doctor = require_doctor()
    if not doctor: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    poll = db.query(QuickPoll).filter_by(id=poll_id, doctor_username=doctor).first()
    if not poll: return jsonify({"error": "Poll not found"}), 404
    
    poll.is_active = 0
    db.commit()
    return jsonify({"success": True})

@app.route("/student/active_polls")
def student_active_polls():
    student_code = require_student()
    if not student_code: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    active_polls = db.query(QuickPoll).filter_by(is_active=1).all()
    
    result = []
    for poll in active_polls:
        # Check if student already answered
        answered = db.query(PollAnswer).filter_by(poll_id=poll.id, student_code=student_code).first()
        result.append({
            "id": poll.id,
            "question": poll.question,
            "doctor": poll.doctor_username,
            "answered": True if answered else False
        })
    
    return jsonify(result)

@app.route("/student/submit_poll", methods=["POST"])
def submit_poll():
    student_code = require_student()
    if not student_code: return jsonify({"error": "Unauthorized"}), 401
    
    poll_id = request.form.get("poll_id")
    answer = request.form.get("answer") # 'yes' or 'no'
    
    if not poll_id or answer not in ['yes', 'no']:
        return jsonify({"error": "Invalid data"}), 400
    
    db = get_db()
    # Check if poll is active
    poll = db.query(QuickPoll).filter_by(id=poll_id, is_active=1).first()
    if not poll: return jsonify({"error": "Poll is not active"}), 404
    
    # Check if already answered
    existing = db.query(PollAnswer).filter_by(poll_id=poll_id, student_code=student_code).first()
    if existing: return jsonify({"error": "Already answered"}), 400
    
    new_answer = PollAnswer(poll_id=poll_id, student_code=student_code, answer=answer)
    db.add(new_answer)
    db.commit()
    
    return jsonify({"success": True})

# ===============================
# Projects Routes
# ===============================

@app.route("/projects")
def projects_dashboard():
    db = get_db()
    projects_list = db.query(StudentProject).order_by(StudentProject.created_at.desc()).all()
    
    # Get interaction counts and user status
    student_code = session.get("student_code")
    projects_data = []
    for p in projects_list:
        loves = db.query(ProjectInteraction).filter_by(project_id=p.id, type='love').count()
        saves = db.query(ProjectInteraction).filter_by(project_id=p.id, type='save').count()
        
        user_loved = False
        user_saved = False
        if student_code:
            user_loved = db.query(ProjectInteraction).filter_by(project_id=p.id, student_code=student_code, type='love').first() is not None
            user_saved = db.query(ProjectInteraction).filter_by(project_id=p.id, student_code=student_code, type='save').first() is not None
            
        projects_data.append({
            'project': p,
            'loves': loves,
            'saves': saves,
            'user_loved': user_loved,
            'user_saved': user_saved
        })
        
    return render_template("projects_dashboard.html", projects=projects_data)

@app.route("/projects/upload_page")
def upload_page():
    if not session.get("student_code"):
        flash("You must be logged in as a student to upload projects.")
        return redirect(url_for("login"))
    return render_template("upload_project.html")

@app.route("/projects/upload", methods=["POST"])
def upload_project():
    if not session.get("student_code"):
        flash("You must be logged in as a student to upload projects.")
        return redirect(url_for("login"))
    
    student_code = session.get("student_code")
    title = request.form.get("title")
    description = request.form.get("description")
    file = request.files.get("code_file")
    
    if not title or not file:
        flash("Title and file are required.")
        return redirect(url_for("projects"))
    
    filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    save_path = os.path.join(Config.UPLOAD_BASE_DIR, "projects", filename)
    file.save(save_path)
    
    student = get_student_by_code(student_code)
    student_name = student.get("name") if student else student_code
    

    db = get_db()
    new_project = StudentProject(
        student_code=student_code,
        student_name=student_name,
        title=title,
        description=description,
        code_path=f"projects/{filename}"
    )
    db.add(new_project)
    db.commit()

    doctors = db.query(Doctor).all()

    for d in doctors:
      create_notification(
        db,
        "DOCTOR_MSG",
        "New Project 📁",
        f"{student_name} uploaded a project"
    )
    
    flash("Project uploaded successfully!")
    return redirect(url_for("projects_dashboard"))

@app.route("/projects/interact/<int:project_id>/<string:itype>", methods=["POST"])
def interact_project(project_id, itype):
    if not session.get("student_code"):
        return jsonify({"error": "Unauthorized"}), 401
    
    if itype not in ['love', 'save']:
        return jsonify({"error": "Invalid interaction"}), 400
        
    student_code = session.get("student_code")
    db = get_db()
    
    existing = db.query(ProjectInteraction).filter_by(
        project_id=project_id, 
        student_code=student_code, 
        type=itype
    ).first()
    
    if existing:
        db.delete(existing)
        action = "removed"
    else:
        new_interaction = ProjectInteraction(
            project_id=project_id,
            student_code=student_code,
            type=itype
        )
        db.add(new_interaction)
        action = "added"
        
    db.commit()
    
    count = db.query(ProjectInteraction).filter_by(project_id=project_id, type=itype).count()
    return jsonify({"status": "success", "action": action, "count": count})
# ===============================
# Student Dashboard
# ===============================
@app.route("/student/dashboard")
def student_dashboard():
    code = require_student()
    if not code:
        return redirect(url_for("login"))

    student = get_student_by_code(code)
    if not student:
        return redirect(url_for("login"))

    # --- التعديل هنا لتوحيد الـ GPA ---
    # نقوم بحساب الـ GPA باستخدام الدالة الموحدة بدلاً من الاعتماد على القيمة المخزنة فقط
    calculated_gpa = calculate_gpa(student) 
    # --------------------------------

    db = get_db()
    assignments = db.query(TaskAssignment).filter_by(student_code=str(code)).all()

    total = len(assignments)
    submitted = len([a for a in assignments if a.submitted_at])
    pending = total - submitted

    # 🔥 Smart Insights
    insights = []

    if total == 0:
        insights.append("No tasks yet, stay tuned 👀")
    else:
        if pending > 0:
            insights.append(f"You have {pending} pending tasks ⚠️")
        else:
            insights.append("All tasks submitted! Great job 🎉")

        if submitted > 0:
            insights.append("Your performance is improving 📈")

        if pending > submitted:
            insights.append("Try to focus more on your pending tasks 🎯")

    # 🤖 AI Insight
    advice_data = generate_student_advice(student)
    ai_message = advice_data.get("advice", "Keep pushing forward 🚀")

    insights.append(ai_message)
    
    messages = db.query(Message).filter_by(student_code=str(code)).order_by(Message.created_at.desc()).all()

    return render_template(
        "student_dashboard.html",
        student=student,
        calculated_gpa=calculated_gpa, # نمرر القيمة المحسوبة هنا
        insights=insights,
        total=total,
        submitted=submitted,
        pending=pending,
        messages=messages
    )
@app.route("/student/exam_proctoring")
def exam_proctoring():
    code = require_student()
    if not code: return redirect(url_for("login"))
    student = get_student_by_code(code)
    return render_template("exam_proctoring.html", student_name=student.get("name", "Student"))

# Alias for compatibility with Home_page.html
@app.route("/student/exam_proctoring_alias")
def student_exam_proctoring():
    return exam_proctoring()

@app.route("/student/qrcode")
def student_qrcode():
    code = require_student()
    if not code:
        return redirect(url_for("login"))

    qr_data = f"ATTENDANCE:{code}"

    img = qrcode.make(qr_data)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    import base64
    qr_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return render_template(
        "attendance_qr.html",
        qr_code=qr_base64,
        student_code=code
    )
    
    db = get_db()
    # البحث عن آخر امتحان نشط للمادة
    active_exam = db.query(ExamSession).filter_by(is_active=1).order_by(ExamSession.created_at.desc()).first()
    
    if active_exam:
        qr_data = f"Exam: {active_exam.subject_name} | Doctor: {active_exam.doctor_username} | Student: {code}"
    else:
        qr_data = f"Student Verification: {code}"
        
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route("/doctor/start_exam", methods=["POST"])
def start_exam():
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))
    
    subject = request.form.get("subject_name", "General Exam").strip()
    db = get_db()
    
    # إغلاق أي امتحانات سابقة لنفس الدكتور
    db.query(ExamSession).filter_by(doctor_username=doctor, is_active=1).update({"is_active": 0})
    
    new_exam = ExamSession(doctor_username=doctor, subject_name=subject, is_active=1, camera_enabled=0)
    db.add(new_exam)
    db.commit()
    flash(f"Exam for {subject} started successfully!")
    return redirect(url_for("doctor_dashboard"))

@app.route("/doctor/toggle_camera/<int:exam_id>", methods=["POST"])
def toggle_camera(exam_id):
    doctor = require_doctor()
    if not doctor: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    exam = db.query(ExamSession).filter_by(id=exam_id, doctor_username=doctor).first()
    if exam:
        exam.camera_enabled = 1 if exam.camera_enabled == 0 else 0
        db.commit()
        return jsonify({"status": "success", "camera_enabled": exam.camera_enabled})
    return jsonify({"error": "Exam not found"}), 404

@app.route("/doctor/delete_exam/<int:exam_id>", methods=["POST"])
def delete_exam(exam_id):
    doctor = require_doctor()
    if not doctor:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    exam = db.query(ExamSession).filter_by(id=exam_id, doctor_username=doctor).first()
    if not exam:
        return jsonify({"error": "Exam not found or not yours"}), 404

    # Mark as inactive (soft delete — keeps participation records intact)
    exam.is_active = 0
    db.commit()

    log_activity(db, doctor, "END_EXAM", f"Ended exam session: {exam.subject_name} (id={exam_id})")
    return jsonify({"status": "success", "message": "Exam ended successfully"})

@app.route("/api/exam_status")
def exam_status():
    db = get_db()
    active_exam = db.query(ExamSession).filter_by(is_active=1).order_by(ExamSession.created_at.desc()).first()
    if active_exam:
        # Check if student already joined
        student_code = session.get("student_code")
        has_joined = False
        if student_code:
            participation = db.query(ExamParticipation).filter_by(exam_id=active_exam.id, student_code=str(student_code)).first()
            if participation:
                has_joined = True

        return jsonify({
            "active": True,
            "exam_id": active_exam.id,
            "subject": active_exam.subject_name,
            "camera_enabled": bool(active_exam.camera_enabled),
            "has_joined": has_joined
        })
    return jsonify({"active": False})

@app.route("/api/exam/join", methods=["POST"])
def join_exam():
    student_code = require_student()
    if not student_code: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    active_exam = db.query(ExamSession).filter_by(is_active=1).order_by(ExamSession.created_at.desc()).first()
    if not active_exam: return jsonify({"error": "No active exam"}), 404
    
    participation = db.query(ExamParticipation).filter_by(exam_id=active_exam.id, student_code=str(student_code)).first()
    if not participation:
        participation = ExamParticipation(exam_id=active_exam.id, student_code=str(student_code), status="entered")
        db.add(participation)
        db.commit()
    
    return jsonify({"status": "success", "message": "Joined exam successfully"})

@app.route("/api/exam/finish", methods=["POST"])
def finish_exam():
    student_code = require_student()
    if not student_code: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    active_exam = db.query(ExamSession).filter_by(is_active=1).order_by(ExamSession.created_at.desc()).first()
    if not active_exam: return jsonify({"error": "No active exam"}), 404
    
    participation = db.query(ExamParticipation).filter_by(exam_id=active_exam.id, student_code=str(student_code)).first()
    if participation:
        participation.status = "finished"
        # Simulate a score for demonstration
        import random
        participation.score = random.randint(50, 100)
        db.commit()
    
    return jsonify({"status": "success", "message": "Exam finished"})

@app.route("/api/doctor/exam_stats")
def doctor_exam_stats():
    doctor = require_doctor()
    if not doctor: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    active_exam = db.query(ExamSession).filter_by(doctor_username=doctor, is_active=1).first()
    if not active_exam: return jsonify({"active": False})
    
    participations = db.query(ExamParticipation).filter_by(exam_id=active_exam.id).all()
    
    # Get all students to find who didn't enter
    all_students_df = load_students()
    student_col = detect_student_code_column(all_students_df)
    all_student_codes = all_students_df[student_col].astype(str).tolist() if student_col else []
    
    entered_codes = [p.student_code for p in participations]
    
    stats = {
        "active": True,
        "exam_id": active_exam.id,
        "subject": active_exam.subject_name,
        "camera_enabled": bool(active_exam.camera_enabled),
        "students": []
    }
    
    # Process entered students
    for p in participations:
        student_info = get_student_by_code(p.student_code)
        stats["students"].append({
            "code": p.student_code,
            "name": student_info.get("name") if student_info else p.student_code,
            "status": p.status,
            "score": p.score,
            "joined_at": p.joined_at.strftime("%H:%M:%S")
        })
        
    # Add not entered students
    for code in all_student_codes:
        if code not in entered_codes:
            student_info = get_student_by_code(code)
            stats["students"].append({
                "code": code,
                "name": student_info.get("name") if student_info else code,
                "status": "not_entered",
                "score": None,
                "joined_at": None
            })
            
    return jsonify(stats)

@app.route("/doctor/publish_exam")
def publish_exam_page():
    if not require_doctor(): return redirect(url_for("login"))
    return render_template("publish_exam.html")

@app.route("/doctor/upload_grade", methods=["POST"])
def upload_grade():
    doctor = require_doctor()
    if not doctor: return jsonify({"error": "Unauthorized"}), 401
    
    student_code = request.form.get("student_code")
    exam_id = request.form.get("exam_id")
    score = request.form.get("score")
    
    if not student_code or not score:
        return jsonify({"error": "Missing data"}), 400
        
    db = get_db()
    participation = db.query(ExamParticipation).filter_by(exam_id=exam_id, student_code=str(student_code)).first()
    
    if not participation:
        participation = ExamParticipation(exam_id=exam_id, student_code=str(student_code), status="finished")
        db.add(participation)
    
    participation.score = int(score)
    participation.status = "finished"
    db.commit()
    
    return jsonify({"status": "success", "message": "Grade uploaded successfully"})

@app.route("/api/notifications/read/<int:notif_id>", methods=["POST"])
def mark_notification_read(notif_id):
    code = require_student()
    if not code: return jsonify({"status": "error"}), 401
    db = get_db()
    notif = db.query(Notification).filter_by(id=notif_id, student_code=str(code)).first()
    if notif:
        notif.is_read = 1
        db.commit()
    return jsonify({"status": "success"})

@app.route("/api/poll", methods=["POST"])
def submit_poll_api():
    code = require_student()
    if not code: return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    data = request.json
    rating = data.get("rating")
    feedback = data.get("feedback", "").strip()
    
    # Allow feedback without rating, or rating without feedback
    if not rating and not feedback:
        return jsonify({"status": "error", "message": "Please provide either a rating or feedback"}), 400
        
    db = get_db()
    try:
        poll = PollResponse(
            student_code=str(code),
            rating=int(rating) if rating else 0,
            feedback=feedback if feedback else None
        )
        db.add(poll)
        db.commit()
        return jsonify({"status": "success", "message": "Thank you for your feedback!"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/get_advice", methods=["GET"])
def get_advice():
    code = require_student()
    if not code: return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    student = get_student_by_code(code)
    if not student:
        return jsonify({"status": "error", "message": "Student not found"}), 404
    
    advice_data = generate_student_advice(student)
    return jsonify({
        "status": "success",
        "advice": advice_data.get("advice", "Keep working hard!"),
        "risk_level": advice_data.get("risk_level", "N/A"),
        "gpa": advice_data.get("gpa")
    })
@app.route("/student/advice_page")
def advice_page():
    code = require_student()
    if not code:
        return redirect(url_for("login"))

    student = get_student_by_code(code)

    advice_data = generate_student_advice(student)

    return render_template("ai_advice.html", data=advice_data)

@app.route("/student/manager_messages", endpoint="student_manager_messages")
def manager_messages():
    code = require_student()
    if not code:
        return redirect(url_for("login"))

    db = get_db()

    messages = db.query(Message)\
        .filter(
            Message.student_code == str(code),
            Message.doctor_username == "Manager"
        )\
        .order_by(Message.created_at.desc())\
        .all()

    return render_template("manager_messages.html", messages=messages)

@app.route("/api/delete_message/<int:message_id>", methods=["POST"])
def api_delete_message(message_id):

    msg = db.session.query(Message).filter_by(id=message_id).first()

    if msg:
        db.session.delete(msg)
        db.session.commit()

    return jsonify({
        "status": "success"
    })

@app.route("/api/study_plan")
def study_plan():
    code = require_student()
    if not code:
        return jsonify({"status": "error"}), 401

    student = get_student_by_code(code)
    if not student:
        return jsonify({"status": "error", "message": "not found"}), 404

    gpa = float(student.get("GPA", 0))
    attendance = float(student.get("attendance", 0))

    plan = []

    # 🔴 GPA logic
    if gpa < 2.5:
        plan.append({
            "title": "Low GPA Alert",
            "subject": "General",
            "priority": "High",
            "action": "Focus more on studying core subjects and attend office hours"
        })
    elif gpa < 3:
        plan.append({
            "title": "Moderate GPA",
            "subject": "General",
            "priority": "Medium",
            "action": "Improve assignments and revise weak topics"
        })
    else:
        plan.append({
            "title": "Good Performance",
            "subject": "General",
            "priority": "Low",
            "action": "Maintain consistency and solve advanced problems"
        })

    # 🟡 Attendance logic
    if attendance < 75:
        plan.append({
            "title": "Low Attendance",
            "subject": "Attendance",
            "priority": "High",
            "action": "Increase attendance immediately to avoid academic risk"
        })
    elif attendance < 90:
        plan.append({
            "title": "Attendance Warning",
            "subject": "Attendance",
            "priority": "Medium",
            "action": "Try to attend more lectures regularly"
        })
    else:
        plan.append({
            "title": "Excellent Attendance",
            "subject": "Attendance",
            "priority": "Low",
            "action": "Keep it up"
        })

    return jsonify({
        "status": "success",
        "plan": plan,
        "gpa": gpa,
        "attendance": attendance
    })
@app.route("/student/study-plan")
def study_plan_page():
    return render_template("study_plan.html")

@app.route("/student/tasks")
def student_tasks():
    code = require_student()
    if not code: return redirect(url_for("login"))
    db = get_db()
    assignments = db.query(TaskAssignment).filter_by(student_code=str(code)).all()
    
    tasks = [a for a in assignments if a.task.kind == 'task']
    quizzes = [a for a in assignments if a.task.kind == 'quiz']
    
    return render_template("student_tasks.html", tasks=tasks, quizzes=quizzes)
@app.route("/api/weak_points")
def weak_points():
    code = require_student()
    if not code:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    student = get_student_by_code(code)
    if not student:
        return jsonify({"status": "error", "message": "Student not found"}), 404

    gpa = float(student.get("gpa", student.get("GPA", 0)))
    attendance = float(student.get("attendance", 0))

    weak_points = []

    # تحليل GPA
    if gpa < 2.5:
        weak_points.append("📉 Weak academic performance (low GPA)")
        weak_points.append("📚 Needs revision of basic concepts")
    elif gpa < 3:
        weak_points.append("⚠️ Average performance - needs improvement in exams")
    
    # تحليل الحضور
    if attendance < 75:
        weak_points.append("❌ Low attendance rate")
        weak_points.append("🕒 Missing lectures affecting understanding")

    # لو كويسين
    if not weak_points:
        weak_points.append("✅ No major weak points detected, keep maintaining your level")

    return jsonify({
        "status": "success",
        "weak_points": weak_points,
        "gpa": gpa,
        "attendance": attendance
    })

@app.route("/student/weakpoints")
def student_weakpoints():
    code = require_student()
    if not code:
        return redirect(url_for("login"))

    # 👇 هنا البيانات اللي بتتبعت للصفحة
    weakpoints = [
        {
            "subject": "Database",
            "level": "High",
            "suggestion": "Focus on SQL joins and normalization + solve practice tasks"
        },
        {
            "subject": "Data Structures",
            "level": "Medium",
            "suggestion": "Revise trees and graphs + implement linked lists"
        }
    ]

    return render_template("student_weakpoints.html", weakpoints=weakpoints)

@app.route("/student/opinion")
def opinion_page():
    code = require_student()
    if not code:
        return redirect(url_for("login"))
    return render_template("opinion.html")

@app.route("/student/proctoring/<int:assignment_id>")
def student_proctoring(assignment_id):
    code = require_student()
    if not code: return redirect(url_for("login"))
    
    db = get_db()
    assignment = db.query(TaskAssignment).filter_by(id=assignment_id, student_code=str(code)).first()
    if not assignment: abort(404)
    
    student = get_student_by_code(code)
    return render_template("attendance_qr.html", assignment=assignment, student_name=student.get("name", "Student"))

@app.route("/student/submit/<int:assignment_id>", methods=["POST"])
def student_submit(assignment_id):
    code = require_student()
    if not code: return redirect(url_for("login"))
    
    db = get_db()
    assignment = db.query(TaskAssignment).filter_by(id=assignment_id, student_code=str(code)).first()
    if not assignment: abort(404)
    
    file = request.files.get("file")
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        save_path = os.path.join(Config.UPLOAD_SOLUTIONS_DIR, filename)
        file.save(save_path)
        
        assignment.submitted_path = os.path.join("solutions", filename)
        assignment.submitted_at = datetime.utcnow()
        db.commit()
        flash("Task submitted successfully!")
    else:
        flash("Invalid file type.")
        
    return redirect(url_for("student_tasks"))

@app.route("/student/scores")
def student_scores():
    student_code = require_student()
    if not student_code: return redirect(url_for("login"))
    
    raw = get_student_by_code(student_code)

    # Normalize keys — Excel may store as lowercase 'gpa', 'attendance', etc.
    student_data = {
        "attendance":  int(raw.get("attendance",  raw.get("Attendance",  0)) or 0) if raw else 0,
        "assignments": int(raw.get("assignments", raw.get("Assignments", 0)) or 0) if raw else 0,
        "midterm":     int(raw.get("midterm",     raw.get("Midterm",     0)) or 0) if raw else 0,
        "final":       int(raw.get("final",       raw.get("Final",       0)) or 0) if raw else 0,
        "GPA":       float(raw.get("GPA",         raw.get("gpa",         0)) or 0) if raw else 0,
    }

    # Override final with latest exam score if available
    db = get_db()
    latest_participation = db.query(ExamParticipation).filter_by(student_code=str(student_code)).order_by(ExamParticipation.updated_at.desc()).first()

    if latest_participation and latest_participation.score is not None:
        student_data["final"] = latest_participation.score
        student_data["GPA"]   = calculate_gpa(student_data)

    return render_template("student_scores.html", student=student_data)


@app.route('/api/student_lookup')
def student_lookup():
    """Doctor-facing API: look up a student by code and return their current grades."""
    if not require_doctor():
        return jsonify({"found": False, "error": "Unauthorized"}), 401
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({"found": False})
    student = get_student_by_code(code)
    if not student:
        return jsonify({"found": False})
    return jsonify({
        "found": True,
        "name":        student.get("name", ""),
        "attendance":  student.get("attendance", 0),
        "assignments": student.get("assignments", 0),
        "midterm":     student.get("midterm", 0),
        "final":       student.get("final", 0),
        "GPA":         student.get("GPA", 0),
    })


@app.route('/doctor/update_grades', methods=['POST'])
def update_grades():
    """Doctor uploads/updates grades for a student (attendance, assignments, midterm, final)."""
    doctor = require_doctor()
    if not doctor:
        return jsonify({"error": "Unauthorized"}), 401

    student_code = request.form.get('student_code', '').strip()
    if not student_code:
        return jsonify({"error": "Student code is required"}), 400

    student = get_student_by_code(student_code)
    if not student:
        return jsonify({"error": f"No student found with code: {student_code}"}), 404

    # Build only the fields the doctor actually submitted
    updates = {}
    for field in ('attendance', 'assignments', 'midterm', 'final'):
        val = request.form.get(field)
        if val is not None and val != '':
            try:
                updates[field] = int(val)
            except ValueError:
                return jsonify({"error": f"Invalid value for {field}"}), 400

    if not updates:
        return jsonify({"error": "No grade values provided"}), 400

    # Persist to the Student table (Flask-SQLAlchemy model)
    from models import Student as StudentModel
    db_session = get_db()   # SQLAlchemy session used elsewhere in app
    # Student model lives in Flask-SQLAlchemy db, so use db.session
    from extensions import db as flask_db
    s = flask_db.session.query(StudentModel).filter_by(code=student_code).first()
    if not s:
        return jsonify({"error": "Student record not found in DB"}), 404

    for field, val in updates.items():
        setattr(s, field, val)

    # Recalculate GPA
    att  = s.attendance  if s.attendance  is not None else 0
    asn  = s.assignments if s.assignments is not None else 0
    mid  = s.midterm     if s.midterm     is not None else 0
    fin  = s.final       if s.final       is not None else 0
    total = (att * 0.1) + (asn * 0.2) + (mid * 0.3) + (fin * 0.4)
    s.GPA = round((total / 100) * 4, 2)

    flask_db.session.commit()

    log_activity(db_session, doctor, "UPLOAD_GRADE",
                 f"Updated grades for student {student_code}: {updates}")

    return jsonify({"status": "success", "message": "Grades updated successfully", "GPA": s.GPA})



@app.route('/student/notifications')
def student_notifications():
    return render_template('student_notifications.html')



@app.route('/student/calendar')
def student_calendar():
    return render_template('student_calendar.html')

    return render_template('student_profile.html')


@app.route('/upload_student_image', methods=['POST'])
def upload_student_image():

    if 'student_code' not in session:
        return redirect(url_for('login'))

    file = request.files.get('image')

    if file:

        filename = secure_filename(file.filename)

        upload_path = os.path.join('static/uploads', filename)

        file.save(upload_path)

        db = SessionLocal()

        student = db.query(Student).filter_by(
            code=session['student_code']
        ).first()

        if student:
            student.image = f"uploads/{filename}"
            db.commit()

        db.close()

    return redirect(url_for('student_profile'))

# ===============================
# Student ai_tutor (fixed)
# ===============================
@app.route("/student/ai_tutor", methods=["GET","POST"])
def ai_tutor():
    code = require_student()
    if not code: 
        return redirect(url_for("login"))

    response_text = ""
    question_text = ""
    
    if request.method == "POST":
        student = get_student_by_code(code)
        question_text = request.form.get("query", "").strip()
        file_path = None

        
        if question_text:
                selected_book = request.form.get("book")

                if selected_book in BOOKS:
                    text = read_pdf(BOOKS[selected_book])
                    response_text = search_answer(text, question_text)
                else:
                    response_text = "Please select a book"
                
            # إذا لم يتم رفع ملف، نحاول الإجابة بشكل عام أو نطلب ملفاً

        # تخزين السؤال والرد في DB
        db = get_db()
        interaction = TutorInteraction(
            student_code=code,
            question=question_text if question_text else "(file uploaded)",
            answer=response_text
        )
        db.add(interaction)
        db.commit()

    return render_template("ai_tutor.html", response=response_text)

@app.route("/chat/delete/<int:msg_id>", methods=["POST"])
def delete_chat(msg_id):
    db = get_db()

    student_code = require_student()
    doctor_username = require_doctor()

    msg = db.query(ChatMessage).filter_by(id=msg_id).first()

    # ✅ FIX 2a: redirect to the right page based on who is logged in
    def back_redirect():
        if doctor_username:
            return redirect(url_for("doctor_dashboard"))
        return redirect(url_for("doctor_chat"))

    if not msg:
        return back_redirect()

    # ✅ FIX 2b: check actual username for doctor, not the string "doctor"
    can_delete = (
        (student_code and msg.sender == student_code) or
        (doctor_username and msg.sender == doctor_username)
    )

    if not can_delete:
        return back_redirect()

    db.delete(msg)
    db.commit()
    return back_redirect()


@app.route("/student/profile")
def student_profile():
    code = require_student()
    if not code:
        return redirect(url_for("login"))

    student = get_student_by_code(code)
    if not student:
        return redirect(url_for("login"))

    # حساب الـ GPA الموحد هنا
    calculated_gpa = calculate_gpa(student)

    return render_template(
        "student_profile.html",
        student=student,
        calculated_gpa=calculated_gpa # نمرر المتغير الجديد للملف
    )

@app.route('/update_student_profile', methods=['POST'])
def update_student_profile():
    student_code = session.get("student_code")
    if not student_code:
        return redirect(url_for("login"))

    # جلب البيانات من الفورم في الـ HTML
    file_path = "Student_performance_dataset.xlsx"
    df = pd.read_excel(file_path)

    # تحديث البيانات في الإكسيل
    mask = df['code'].astype(str) == str(student_code)
    if any(mask):
        df.loc[mask, 'attendance'] = request.form.get('attendance', type=float)
        df.loc[mask, 'assignments'] = request.form.get('assignments', type=float)
        df.loc[mask, 'midterm'] = request.form.get('midterm', type=float)
        df.loc[mask, 'final'] = request.form.get('final', type=float)
        
        df.to_excel(file_path, index=False)
        flash("تم تحديث الدرجات وإعادة حساب المعدل!")

    return redirect(url_for("student_profile"))   
# ===============================
# Doctor Chat Send (to student)
# ===============================
@app.route("/api/doctor/chat/send", methods=["POST"])
def doctor_chat_send():
    doctor = require_doctor()
    if not doctor:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json or {}
    student_code = str(data.get("student_code", "")).strip()
    message_text = str(data.get("message", "")).strip()

    if not student_code or not message_text:
        return jsonify({"status": "error", "message": "Student code and message are required"}), 400

    student = get_student_by_code(student_code)
    if not student:
        return jsonify({"status": "error", "message": f"No student found with code: {student_code}"}), 404

    db = get_db()
    new_msg = ChatMessage(
        sender=doctor,
        receiver=student_code,
        message=message_text
    )
    db.add(new_msg)

    # Also create a notification so the student sees it
    create_notification(db, student_code, "New Message from Doctor 💬", message_text[:80])

    db.commit()
    log_activity(db, doctor, "SEND_CHAT", f"Sent chat message to student {student_code}")
    return jsonify({"status": "success", "message": "Message sent!", "student_name": student.get("name", student_code)})


@app.route("/api/doctor/chat/history")
def doctor_chat_history():
    """Return chat history between doctor and a student."""
    doctor = require_doctor()
    if not doctor:
        return jsonify({"status": "error"}), 401

    student_code = request.args.get("student_code", "").strip()
    if not student_code:
        return jsonify({"messages": []})

    db = get_db()
    msgs = db.query(ChatMessage).filter(
        ((ChatMessage.sender == doctor) & (ChatMessage.receiver == student_code)) |
        ((ChatMessage.sender == student_code) & (ChatMessage.receiver == doctor))
    ).order_by(ChatMessage.created_at.asc()).all()

    return jsonify({"messages": [
        {
            "id":         m.id,
            "sender":     m.sender,
            "text":       m.message,
            "time":       m.created_at.strftime("%H:%M") if m.created_at else "",
            "is_doctor":  m.sender == doctor
        }
        for m in msgs
    ]})


# ===============================
# Doctor Dashboard
# ===============================
@app.route("/doctor/dashboard")
def doctor_dashboard():
    if not require_doctor(): return redirect(url_for("login"))
    
    search_code = request.args.get("search_code", "").strip()
    student_result = None
    error_msg = None
    
    if search_code:
        student_result = get_student_by_code(search_code)
        if not student_result:
            error_msg = f"No student found with code: {search_code}"
        
    db = get_db()
    doctors = db.query(Doctor).all()
    interactions = db.query(TutorInteraction).order_by(TutorInteraction.timestamp.desc()).all()
    
    active_exam = db.query(ExamSession)\
        .filter_by(doctor_username=session["doctor"], is_active=1)\
        .first()
        
    messages = db.query(Message).filter_by(doctor_username=session["doctor"]).order_by(Message.created_at.desc()).all()

    # Calculate stats for the new dashboard
    total_students = 0
    try:
        df = load_students()
        total_students = len(df)
    except:
        pass

    # Mock or calculate attendance (if data exists)
    avg_attendance = "84%" 
    at_risk_count = 0
    if total_students > 0:
        # Simple logic: students with GPA < 2.0 are at risk
        try:
            gpa_col = "gpa" if "gpa" in df.columns else "GPA"
            at_risk_count = len(df[df[gpa_col] < 2.0])
        except:
            at_risk_count = 12 # fallback mock

    return render_template(
        "doctor_dashboard.html",
        student_result=student_result,
        search_code=search_code,
        error_msg=error_msg,
        doctors=doctors,
        doctor=session["doctor"],
        interactions=interactions,
        active_exam=active_exam,
        messages=messages,
        total_students=total_students,
        avg_attendance=avg_attendance,
        at_risk_count=at_risk_count
    )

@app.route("/doctor-chat", methods=["GET", "POST"])
def doctor_chat():
    # ✅ FIX 1: use require_student() helper consistently
    student_code = require_student()
    if not student_code:
        return redirect(url_for("login"))

    db = get_db()
    doctors = db.query(Doctor).all()
    selected_doctor = request.form.get("doctor_username") or request.args.get("doctor")

    # SEND MESSAGE
    if request.method == "POST":
        msg = request.form.get("message", "").strip()
        if msg and selected_doctor:
            new_msg = ChatMessage(
                sender=student_code,
                receiver=selected_doctor,
                message=msg
            )
            db.add(new_msg)
            # ✅ FIX: notify the doctor, not just save silently
            create_notification(db, selected_doctor, "New Message from Student 💬", msg[:80])
            db.commit()

    # GET CHAT history between this student and the selected doctor
    messages = []
    if selected_doctor:
        messages = db.query(ChatMessage).filter(
            ((ChatMessage.sender == student_code) & (ChatMessage.receiver == selected_doctor)) |
            ((ChatMessage.sender == selected_doctor) & (ChatMessage.receiver == student_code))
        ).order_by(ChatMessage.created_at.asc()).all()

    return render_template(
        "doctor_chat.html",
        messages=messages,
        doctors=doctors,
        selected_doctor=selected_doctor,
        student_code=student_code
    )
# ===============================
# Doctor task center
# ===============================

@app.route("/doctor/task_center", methods=["GET", "POST"])
def doctor_task_center():
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))
    
    if request.method == "POST":
        db = get_db()
        try:
            # Get form data
            level = request.form.get("level", "").strip()
            department = request.form.get("department", "").strip()
            kind = request.form.get("kind", "task").strip().lower()
            deadline = request.form.get("deadline", "").strip()
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            range_from = request.form.get("range_from", "").strip()
            range_to = request.form.get("range_to", "").strip()
            
            # Validate required fields
            if not title or not kind:
                flash("Title and Content Type are required")
                return redirect(url_for("doctor_task_center"))
            
            # Handle file attachment
            attachment_path = None
            file = request.files.get("attachment")
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                save_path = os.path.join(Config.UPLOAD_BASE_DIR, "tasks", filename)
                file.save(save_path)
                attachment_path = os.path.join("tasks", filename)
            
            # Create task
            new_task = Task(
                kind=kind,
                title=title,
                description=description,
                deadline=deadline,
                attachment_path=attachment_path,
                created_by=doctor
            )
            db.add(new_task)
            db.flush()  # Get the task ID
            
            # Get students to assign task to
            df = load_students()
            col = detect_student_code_column(df)
            
            if col:
                student_codes = df[col].astype(str).unique()
                
                # Filter by level if provided
                if level:
                    level_col = None
                    for c in df.columns:
                        if 'level' in c.lower():
                            level_col = c
                            break
                    if level_col:
                        df = df[df[level_col].astype(str) == level]
                        student_codes = df[col].astype(str).unique()
                
                # Filter by range if provided
                if range_from and range_to:
                    try:
                        range_from_int = int(range_from)
                        range_to_int = int(range_to)
                        student_codes = [s for s in student_codes if range_from_int <= int(s.split()[-1] if s else 0) <= range_to_int]
                    except:
                        pass
                
                # Create assignments for each student
                for code in student_codes:
                    assignment = TaskAssignment(task_id=new_task.id, student_code=str(code))
                    db.add(assignment)

                    create_notification(
                        db,
                        code,
                        f"New {kind} 📚",
                        f"You got a new task: {title}"
                     )

                    # Create notification
                    notification = Notification(
                        student_code=str(code),
                        title=f"New {kind}: {title}",
                        message=f"A new {kind} has been assigned to you: {title}"
                    )
                    db.add(notification)
            
            db.commit()
            log_activity(db, doctor, "create_task", f"Created {kind} '{title}' for {len(student_codes) if col else 0} students")
            flash(f"Task '{title}' created and assigned successfully!")
            return redirect(url_for("doctor_task_center"))
            
        except Exception as e:
            db.rollback()
            flash(f"Error creating task: {str(e)}")
            return redirect(url_for("doctor_task_center"))
    
    return render_template("doctor_task_center.html")

# ===============================
# Doctor activity
# ===============================

@app.route("/doctor/activity")
def doctor_activity():
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))
    
    db = get_db()
    activity = db.query(ActivityLog).filter_by(doctor_username=doctor).order_by(ActivityLog.created_at.desc()).all()
    
    return render_template("doctor_activity.html", doctor=doctor, activity=activity)

# ===============================
# Doctor clear activity
# ===============================
@app.route("/doctor/clear_activity", methods=["POST"])
def clear_my_activity():
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))
    
    db = get_db()
    try:
        db.query(ActivityLog).filter_by(doctor_username=doctor).delete()
        db.commit()
        flash("Activity logs cleared successfully!")
    except Exception as e:
        db.rollback()
        flash(f"Error clearing logs: {str(e)}")
    
    return redirect(url_for("doctor_activity"))

# ===============================
# Delete AI Tutor Interaction
# ===============================
@app.route("/doctor/delete_interaction/<int:interaction_id>", methods=["POST"])
def delete_interaction(interaction_id):
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))
    
    db = get_db()
    interaction = db.query(TutorInteraction).filter_by(id=interaction_id).first()
    
    if interaction:
        try:
            db.delete(interaction)
            db.commit()
            flash(f"Interaction deleted successfully!", "success")
            log_activity(db, doctor, "delete_interaction", f"Deleted interaction {interaction_id} for student {interaction.student_code}")
        except Exception as e:
            db.rollback()
            flash(f"Error deleting interaction: {str(e)}", "error")
    else:
        flash("Interaction not found", "error")
    
    return redirect(url_for("doctor_dashboard"))

@app.route("/doctor/delete/<int:doctor_id>", methods=["POST"])
def delete_doctor(doctor_id):
    # هنا تحطي الكود اللي هيحذف الدكتور من قاعدة البيانات
    # مثلاً:
    # doctor = Doctor.query.get(doctor_id)
    # db.session.delete(doctor)
    # db.session.commit()
    return redirect(url_for("doctor_dashboard"))

@app.route("/doctor/attendance/toggle", methods=["POST"])
def toggle_attendance():
    doctor_username = require_doctor()
    if not doctor_username: return jsonify({"error": "Unauthorized"}), 401
    
    db_session = get_db()
    active_session = db_session.query(AttendanceSession).filter_by(
        doctor_username=doctor_username, 
        is_active=1
    ).first()
    
    if active_session:
        active_session.is_active = 0
        db_session.commit()
        return jsonify({"status": "closed", "message": "Attendance closed"})
    else:
        import uuid
        token = str(uuid.uuid4())
        new_session = AttendanceSession(
            doctor_username=doctor_username,
            session_name=f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            qr_code_token=token,
            is_active=1
        )
        db_session.add(new_session)
        db_session.commit()
        return jsonify({
            "status": "active", 
            "message": "Attendance opened", 
            "token": token,
            "session_id": new_session.id
        })

@app.route("/doctor/attendance/status")
def doctor_attendance_status():
    doctor_username = require_doctor()
    if not doctor_username: return jsonify({"error": "Unauthorized"}), 401
    
    db_session = get_db()
    active_session = db_session.query(AttendanceSession).filter_by(
        doctor_username=doctor_username, 
        is_active=1
    ).first()
    
    if active_session:
        count = db_session.query(AttendanceRecord).filter_by(session_id=active_session.id).count()
        return jsonify({
            "is_active": True,
            "count": count,
            "token": active_session.qr_code_token,
            "session_id": active_session.id
        })
    return jsonify({"is_active": False, "count": 0})

@app.route("/student/attendance/mark", methods=["POST"])
def student_mark_attendance():
    student_code = require_student()
    if not student_code: return jsonify({"error": "Unauthorized"}), 401

    token = request.json.get("token")
    if not token: return jsonify({"error": "Invalid token"}), 400

    # ✅ Capture device/network info for Integrity Report
    ip_address = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    latitude   = str(request.json.get("latitude",  "")).strip() or None
    longitude  = str(request.json.get("longitude", "")).strip() or None

    db_session = get_db()
    session_obj = db_session.query(AttendanceSession).filter_by(qr_code_token=token, is_active=1).first()
    if not session_obj:
        return jsonify({"error": "Attendance session is closed or invalid"}), 400

    exists = db_session.query(AttendanceRecord).filter_by(
        session_id=session_obj.id,
        student_code=student_code
    ).first()

    if exists:
        # ✅ FIX: count the re-attempt and flag as suspicious if already marked
        exists.attempt_count = (exists.attempt_count or 1) + 1
        if exists.attempt_count >= 2:
            exists.is_suspicious = 1
            exists.suspicious_reason = f"Multiple submit attempts ({exists.attempt_count})"
        db_session.commit()
        return jsonify({"message": "Already marked"})

    # ✅ Check for duplicate IP in same session (another student using same device)
    ip_duplicate = db_session.query(AttendanceRecord).filter_by(
        session_id=session_obj.id,
        ip_address=ip_address
    ).first() if ip_address else None

    is_suspicious    = 1 if ip_duplicate else 0
    suspicious_reason = f"Duplicate IP ({ip_address}) — possible shared device" if ip_duplicate else None

    record = AttendanceRecord(
        session_id=session_obj.id,
        student_code=student_code,
        ip_address=ip_address,
        latitude=latitude,
        longitude=longitude,
        attempt_count=1,
        is_suspicious=is_suspicious,
        suspicious_reason=suspicious_reason
    )
    db_session.add(record)
    db_session.commit()

    return jsonify({"message": "Attendance marked successfully"})

@app.route("/student/attendance")
def student_attendance():
    student_code = require_student()
    if not student_code: return redirect(url_for("login"))
    
    db_session = get_db()
    active_session = db_session.query(AttendanceSession).filter_by(is_active=1).first()
    
    qr_code = None
    if active_session:
        # Link for the student to "scan" or visit to mark attendance
        # In this implementation, we can just show a QR that contains the token
        import qrcode
        import base64
        from io import BytesIO
        
        img = qrcode.make(active_session.qr_code_token)
        buffer = BytesIO()
        img.save(buffer)
        buffer.seek(0)
        qr_code = base64.b64encode(buffer.read()).decode("utf-8")

    return render_template(
        "student_attendance.html",
        qr_code=qr_code,
        student_code=student_code,
        active_session=active_session
    )
# ===============================
# Doctor view student
# ============================
@app.route("/student/send_message", methods=["POST"])
def send_student_message():
    student_code = require_student()
    if not student_code: return redirect(url_for("login"))
    
    db = get_db()
    msg_text = request.form.get("message", "").strip()
    doctor_username = request.form.get("doctor_username", "").strip()
    
    if not msg_text:
        flash("Message cannot be empty")
        return redirect(url_for("student_dashboard"))
        
    if not doctor_username:
        # Default to first doctor if none selected, or handle error
        first_doc = db.query(Doctor).first()
        if first_doc:
            doctor_username = first_doc.username
        else:
            flash("No doctors available to message")
            return redirect(url_for("student_dashboard"))

    try:
        new_msg = Message(
            student_code=str(student_code),
            doctor_username=doctor_username,
            text=f"[STUDENT] {msg_text}"
        )
        db.add(new_msg)
        create_notification(
            db,
            doctor_username,
            "New Message 💬",
            msg_text[:80]
        )
        db.commit()
        flash("Message sent to doctor!")
    except Exception as e:
        db.rollback()
        flash(f"Error sending message: {str(e)}")
        
    return redirect(url_for("student_dashboard"))

@app.route("/doctor/send_message", methods=["POST"])
def send_doctor_message():
    doctor_username = require_doctor()
    if not doctor_username: return redirect(url_for("login"))
    
    recipient_type = request.form.get("recipient_type") # 'all' or 'specific'
    student_code = request.form.get("student_code", "").strip()
    msg_text = request.form.get("message", "").strip()
    
    if not msg_text:
        flash("Message cannot be empty")
        return redirect(url_for("doctor_dashboard"))
        
    db = get_db()
    try:
        if recipient_type == "all":
            df = load_students()
            col = detect_student_code_column(df)
            if col:
                student_codes = df[col].astype(str).unique()
                for code in student_codes:
                    msg = Message(
                        student_code=str(code),
                        doctor_username=doctor_username,
                        text=f"[DOCTOR] {msg_text}"
                    )
                    db.add(msg)
                    # ✅ FIX 3: was `student_code` (from form, empty for broadcast) — now correctly `code` from the loop
                    create_notification(
                        db,
                        code,
                        "New Message 💬",
                        msg_text[:80]
                    )
            flash("Broadcast message sent to all students!")
        else:
            if not student_code:
                flash("Please provide a student code")
                return redirect(url_for("doctor_dashboard"))
            
            # Verify student exists
            student = get_student_by_code(student_code)
            if not student:
                flash(f"Student with code {student_code} not found")
                return redirect(url_for("doctor_dashboard"))
                
            msg = Message(
                student_code=str(student_code),
                doctor_username=doctor_username,
                text=f"[DOCTOR] {msg_text}"
            )
            db.add(msg)
            flash(f"Message sent to student {student_code}!")
            
        db.commit()
    except Exception as e:
        db.rollback()
        flash(f"Error sending message: {str(e)}")
        
    return redirect(url_for("doctor_dashboard"))

@app.route("/doctor/view_student/<string:student_code>", methods=["GET", "POST"])
def doctor_view_student(student_code):
    doctor_username = require_doctor()
    if not doctor_username: return redirect(url_for("login"))
    
    db = get_db()
    student = get_student_by_code(student_code)
    if not student: abort(404)
    
    if request.method == "POST":
        msg_text = request.form.get("message", "").strip()
        file = request.files.get("attachment")
        
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            save_path = os.path.join(Config.UPLOAD_MESSAGES_DIR, filename)
            file.save(save_path)
            filename = os.path.join("messages", filename)
            
        if msg_text or filename:
            new_msg = Message(
                student_code=str(student_code),
                doctor_username=doctor_username,
                text=msg_text,
                attachment_path=filename
            )
            db.add(new_msg)   # ✅ FIX 4a: was commented out accidentally
            create_notification(db, str(student_code), "New Message from Doctor 💬", (msg_text or "")[:80])
            db.commit()       # ✅ FIX 4b: was commented out — message never saved
            flash("Message sent successfully!")
            log_activity(db, doctor_username, "send_message", f"Sent message to student {student_code}")
            
    messages = db.query(Message).filter_by(student_code=str(student_code), doctor_username=doctor_username).order_by(Message.created_at.desc()).all()
    return render_template("doctor_view_student.html", student=student, messages=messages)

@app.route("/doctor/student_ai_questions/<string:student_code>")
def doctor_student_ai_questions(student_code):
    doctor_username = require_doctor()
    if not doctor_username: return redirect(url_for("login"))

    db = get_db()
    student = get_student_by_code(student_code)
    if not student: abort(404)

    # Try matching with and without whitespace / int conversion
    code_str = str(student_code).strip()
    interactions = db.query(TutorInteraction)\
        .filter(TutorInteraction.student_code.in_([code_str, code_str.lstrip("0")]))\
        .order_by(TutorInteraction.timestamp.desc()).all()

    return render_template("doctor_student_ai_questions.html",
                           student=student,
                           interactions=interactions,
                           doctor=doctor_username)


@app.route("/manager/dashboard")
def manager_dashboard():
    if not require_manager(): return redirect(url_for("login"))
    
    search_code = request.args.get("search_code", "").strip()
    student_data = None
    error_msg = None
    
    if search_code:
        student_data = get_student_by_code(search_code)
        if not student_data:
            error_msg = f"No student found with code: {search_code}"
    
    # Get all student opinions
    db = get_db()
    all_opinions = db.query(PollResponse).order_by(PollResponse.created_at.desc()).all()
            
    return render_template("manager_dashboard.html", 
                           search_code=search_code, 
                           student_data=student_data, 
                           error_msg=error_msg,
                           all_fields=True,
                           all_opinions=all_opinions)

@app.route("/manager/send_message", methods=["POST"])
def send_manager_message():
    if not require_manager(): return redirect(url_for("login"))
    
    # The template uses 'message_type', but the code was looking for 'recipient_type'
    recipient_type = request.form.get("message_type") or request.form.get("recipient_type")
    message_text = request.form.get("message", "").strip()
    
    if not message_text:
        flash("Message cannot be empty")
        return redirect(url_for("manager_dashboard"))
        
    db = get_db()
    try:
        if recipient_type == "students" or recipient_type == "all":
            # Send to all students in Excel
            df = load_students()
            col = detect_student_code_column(df)
            if col:
                student_codes = df[col].astype(str).unique()
                for code in student_codes:
                    msg = Message(
                        student_code=str(code),
                        doctor_username="Manager",
                        text=f"[MANAGER] {message_text}"
                    )
                    db.add(msg)
            
        if recipient_type == "doctors" or recipient_type == "all":
            # Send to all doctors in DB
            doctors = db.query(Doctor).all()
            for doc in doctors:
                msg = Message(
                    student_code="DOCTOR_MSG", # Special code for doctor-targeted messages
                    doctor_username=doc.username,
                    text=f"[MANAGER] {message_text}"
                )
                db.add(msg)
            
        db.commit()
        flash("Broadcast message sent successfully!")
    except Exception as e:
        db.rollback()
        flash(f"Error sending message: {str(e)}")
        
    return redirect(url_for("manager_dashboard"))

@app.route("/manager/delete_opinion/<int:opinion_id>", methods=["POST"])
def delete_opinion(opinion_id):
    if not require_manager():
        return redirect(url_for("login"))
        
    db = get_db()
    opinion = db.query(PollResponse).filter_by(id=opinion_id).first()
    
    if opinion:
        try:
            db.delete(opinion)
            db.commit()
            flash("Opinion deleted successfully.")
        except Exception as e:
            db.rollback()
            flash(f"Error deleting opinion: {str(e)}")
    else:
        flash("Opinion not found.")

    return redirect(url_for("manager_dashboard"))

@app.route("/api/delete_message/<int:message_id>", methods=["POST"])
def delete_message(message_id):
    student_code = require_student()
    doctor_username = require_doctor()
    
    if not student_code and not doctor_username:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    db = get_db()
    msg = db.query(Message).filter_by(id=message_id).first()
    
    if not msg:
        return jsonify({"status": "error", "message": "Message not found"}), 404
        
    # Check authorization to delete
    authorized = False
    if student_code and msg.student_code == str(student_code):
        authorized = True
    elif doctor_username and msg.doctor_username == doctor_username:
        authorized = True
        
    if not authorized:
        return jsonify({"status": "error", "message": "Unauthorized to delete this message"}), 403
        
    try:
        db.delete(msg)
        db.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500


    

# ===============================
# Download files
# ===============================
@app.route("/download")
def download_file():
    rel = request.args.get("path","")
    full = safe_join_uploads(rel)
    if not full or not os.path.exists(full): abort(404)
    return send_from_directory(os.path.dirname(full), os.path.basename(full), as_attachment=True)

# ===============================
# Sign Up Routes
# ===============================

@app.route("/signup")
def signup_choice():
    """صفحة اختيار نوع التسجيل"""
    return render_template("signup_choice.html")

@app.route("/signup/student")
def signup_student():
    """صفحة تسجيل الطالب"""
    return render_template("signup_student.html")

@app.route("/signup/doctor")
def signup_doctor():
    """صفحة تسجيل الدكتور"""
    return render_template("signup_doctor.html")

@app.route("/signup/manager")
def signup_manager():
    """صفحة تسجيل المدير"""
    return render_template("signup_manager.html")

@app.route("/register/student", methods=["POST"])
def register_student():
    """معالجة تسجيل الطالب الجديد"""
    error = None
    student_code = (request.form.get("student_code") or "").strip()
    student_name = (request.form.get("student_name") or "").strip()
    student_email = (request.form.get("student_email") or "").strip()
    password = (request.form.get("student_password") or "").strip()
    confirm_password = (request.form.get("student_confirm_password") or "").strip()
    
    # التحقق من البيانات
    if not student_code or not student_name or not student_email or not password:
        error = "All fields are required"
    elif password != confirm_password:
        error = "Passwords do not match"
    elif len(password) < 6:
        error = "Password must be at least 6 characters"
    else:
        # التحقق من عدم وجود الطالب بالفعل
        existing_student = get_student_by_code(student_code)
        if existing_student and existing_student.get("name") != student_code:
            # الطالب موجود بالفعل في قاعدة البيانات
            session.clear()
            session["student_code"] = student_code
            flash(f"Welcome back, {student_name}!")
            return redirect(url_for("student_dashboard"))
        else:
            # تسجيل الطالب الجديد وحفظه في ملف الـ Excel
            try:
                df = load_students()
                col = detect_student_code_column(df)
                if col:
                    # إنشاء صف جديد للطالب
                    new_row = {c: 0 for c in df.columns}
                    new_row[col] = student_code
                    new_row["name"] = student_name
                    # إضافة أي أعمدة أخرى لو موجودة
                    if "email" in df.columns: new_row["email"] = student_email
                    
                    # تحويل الـ dict لـ DataFrame وإضافته
                    new_df = pd.DataFrame([new_row])
                    df = pd.concat([df, new_df], ignore_index=True)
                    
                    # حفظ الملف
                    df.to_excel(Config.EXCEL_PATH, index=False)
                    
                    session.clear()
                    session["student_code"] = student_code
                    flash(f"Account created successfully! Welcome, {student_name}!")
                    return redirect(url_for("student_dashboard"))
                else:
                    error = "System error: Student ID column not found in database."
            except Exception as e:
                logger.error(f"Error saving new student: {e}")
                error = f"Error creating account: {str(e)}"
    
    return render_template("signup_student.html", error=error)

@app.route("/score-analysis")
def score_analysis():
    code = require_student()
    if not code:
        return redirect(url_for("login"))
    
    student = get_student_by_code(code)
    if not student:
        return redirect(url_for("login"))
    
    # Ensure numeric values for the chart/stats
    def safe_num(val):
        try:
            return float(val) if not pd.isna(val) else 0
        except:
            return 0

    processed_student = {
        "attendance": safe_num(student.get("attendance", 0)),
        "assignments": safe_num(student.get("assignments", 0)),
        "midterm": safe_num(student.get("midterm", 0)),
        "final": safe_num(student.get("final", 0)),
        "GPA": safe_num(student.get("gpa", 0))
    }

    return render_template("score_analysis.html", student=processed_student)

@app.route("/register/doctor", methods=["POST"])
def register_doctor():
    """معالجة تسجيل الدكتور الجديد"""
    error = None
    db = get_db()
    
    doctor_username = (request.form.get("doctor_username") or "").strip().lower()
    doctor_name = (request.form.get("doctor_name") or "").strip()
    doctor_email = (request.form.get("doctor_email") or "").strip()
    doctor_department = (request.form.get("doctor_department") or "").strip()
    password = (request.form.get("doctor_password") or "").strip()
    confirm_password = (request.form.get("doctor_confirm_password") or "").strip()
    
    # التحقق من البيانات
    if not doctor_username or not doctor_name or not doctor_email or not password:
        error = "All fields are required"
    elif password != confirm_password:
        error = "Passwords do not match"
    elif len(password) < 6:
        error = "Password must be at least 6 characters"
    elif len(doctor_username) < 3:
        error = "Username must be at least 3 characters"
    else:
        # التحقق من عدم وجود الدكتور بالفعل
        existing_doctor = db.query(Doctor).filter_by(username=doctor_username).first()
        if existing_doctor:
            error = "Username already exists. Please choose another username."
        else:
            try:
                # إنشاء حساب الدكتور الجديد
                new_doctor = Doctor(
                    username=doctor_username,
                    password_hash=generate_password_hash(password)
                )
                db.add(new_doctor)
                db.commit()
                
                # تسجيل الدخول التلقائي
                session.clear()
                session["doctor"] = doctor_username
                flash(f"Account created successfully! Welcome, Dr. {doctor_name}!")
                return redirect(url_for("doctor_dashboard"))
            except Exception as e:
                db.rollback()
                error = f"Error creating account: {str(e)}"
    
    return render_template("signup_doctor.html", error=error)

# ===============================
# Doctor Messages Page (GET + POST)
# ===============================
@app.route("/doctor/messages", methods=["GET", "POST"])
def doctor_messages():
    doctor_username = require_doctor()
    if not doctor_username:
        return redirect(url_for("login"))

    db = get_db()

    if request.method == "POST":
        recipient_type = request.form.get("recipient_type", "all")
        student_code   = request.form.get("student_code", "").strip()
        msg_text       = request.form.get("message", "").strip()

        if not msg_text:
            flash("Message cannot be empty")
            return redirect(url_for("doctor_messages"))

        try:
            if recipient_type == "all":
                df = load_students()
                col = detect_student_code_column(df)
                if col:
                    for code in df[col].astype(str).unique():
                        db.add(Message(student_code=str(code), doctor_username=doctor_username,
                                       text=f"[DOCTOR] {msg_text}"))
                        create_notification(db, code, "New Message 💬", msg_text[:80])
                flash("Broadcast sent to all students!")
            else:
                if not student_code:
                    flash("Please provide a student code")
                    return redirect(url_for("doctor_messages"))
                if not get_student_by_code(student_code):
                    flash(f"Student {student_code} not found")
                    return redirect(url_for("doctor_messages"))
                db.add(Message(student_code=str(student_code), doctor_username=doctor_username,
                               text=f"[DOCTOR] {msg_text}"))
                create_notification(db, student_code, "New Message 💬", msg_text[:80])
                flash(f"Message sent to student {student_code}!")
            db.commit()
        except Exception as e:
            db.rollback()
            flash(f"Error: {str(e)}")

        return redirect(url_for("doctor_messages"))

    messages = db.query(Message).filter_by(doctor_username=doctor_username)\
                 .order_by(Message.created_at.desc()).all()
    return render_template("Doctor_message.html", doctor=doctor_username, messages=messages)


@app.route("/doctor/messages/delete/<int:message_id>", methods=["POST"])
def doctor_delete_message(message_id):
    doctor_username = require_doctor()
    if not doctor_username:
        return redirect(url_for("login"))
    db = get_db()
    msg = db.query(Message).filter_by(id=message_id, doctor_username=doctor_username).first()
    if msg:
        db.delete(msg)
        db.commit()
    return redirect(url_for("doctor_messages"))


# ===============================
# Integrity Report (Doctor sees attendance integrity per session)
# ===============================
@app.route("/doctor/integrity-report")
def integrity_report():
    doctor_username = require_doctor()
    if not doctor_username:
        return redirect(url_for("login"))

    db = get_db()
    sessions = db.query(AttendanceSession).filter_by(doctor_username=doctor_username)\
                 .order_by(AttendanceSession.created_at.desc()).all()

    report_data = []
    for s in sessions:
        records = db.query(AttendanceRecord).filter_by(session_id=s.id).all()
        total        = len(records)
        suspicious   = [r for r in records if r.is_suspicious == 1]
        clean        = total - len(suspicious)
        report_data.append({
            "session":    s,
            "records":    records,
            "total":      total,
            "suspicious": len(suspicious),
            "clean":      clean
        })

    return render_template("integrity_report.html",
                           doctor=doctor_username,
                           report_data=report_data)


@app.route("/register/manager", methods=["POST"])
def register_manager():
    """معالجة تسجيل المدير الجديد"""
    error = None
    
    manager_name = (request.form.get("manager_name") or "").strip()
    manager_email = (request.form.get("manager_email") or "").strip()
    password = (request.form.get("manager_password") or "").strip()
    confirm_password = (request.form.get("manager_confirm_password") or "").strip()
    
    # التحقق من البيانات
    if not manager_name or not manager_email or not password:
        error = "All fields are required"
    elif password != confirm_password:
        error = "Passwords do not match"
    elif len(password) < 6:
        error = "ssword must be at least 6 characters"
    else:
        # تخزين طلب المدير الجديد (يمكن إضافة جدول للطلبات المعلقة)
        # حالياً سنسمح بالدخول مباشرة إذا كانت كلمة المرور صحيحة
        session.clear()
        session["manager"] = True
        flash(f"Manager account created successfully! Welcome, {manager_name}!")
        return redirect(url_for("manager_dashboard"))
    
    return render_template("signup_manager.html", error=error)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)