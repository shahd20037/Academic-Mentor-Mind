# I will create a separate script to apply changes to app.py to avoid rewriting the whole 1800+ lines file.
# However, for simplicity and to ensure it works, I will define the new routes and logic here.

@app.route("/doctor/attendance/toggle", methods=["POST"])
def toggle_attendance():
    doctor_username = require_doctor()
    if not doctor_username: return jsonify({"error": "Unauthorized"}), 401
    
    db = get_db()
    # Check if there's an active session
    active_session = db.query(AttendanceSession).filter_by(
        doctor_username=doctor_username, 
        is_active=1
    ).first()
    
    if active_session:
        # Close it
        active_session.is_active = 0
        db.commit()
        return jsonify({"status": "closed", "message": "Attendance closed"})
    else:
        # Create new session
        import uuid
        token = str(uuid.uuid4())
        new_session = AttendanceSession(
            doctor_username=doctor_username,
            session_name=f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            qr_code_token=token,
            is_active=1
        )
        db.add(new_session)
        db.commit()
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
    
    db = get_db()
    active_session = db.query(AttendanceSession).filter_by(
        doctor_username=doctor_username, 
        is_active=1
    ).first()
    
    if active_session:
        count = db.query(AttendanceRecord).filter_by(session_id=active_session.id).count()
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
    
    db = get_db()
    session = db.query(AttendanceSession).filter_by(qr_code_token=token, is_active=1).first()
    if not session:
        return jsonify({"error": "Attendance session is closed or invalid"}), 400
    
    # Check if already marked
    exists = db.query(AttendanceRecord).filter_by(
        session_id=session.id, 
        student_code=student_code
    ).first()
    
    if exists:
        return jsonify({"message": "Already marked"})
    
    record = AttendanceRecord(
        session_id=session.id,
        student_code=student_code
    )
    db.add(record)
    db.commit()
    
    return jsonify({"message": "Attendance marked successfully"})