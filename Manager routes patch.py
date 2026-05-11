@app.route("/manager/dashboard")
def manager_dashboard():
    if not require_manager(): return redirect(url_for("login"))

    search_code = request.args.get("search_code", "").strip()
    student_data = None
    student_db = None
    error_msg = None

    if search_code:
        student_data = get_student_by_code(search_code)
        if not student_data:
            error_msg = f"No student found with code: {search_code}"
        else:
            # Try to get profile image from SQLAlchemy Student model
            try:
                from models import Student as StudentModel
                from extensions import db as flask_db
                student_db = flask_db.session.query(StudentModel).filter_by(code=search_code).first()
            except Exception:
                student_db = None

    db = get_db()
    all_opinions = db.query(PollResponse).order_by(PollResponse.created_at.desc()).all()
    all_doctors = db.query(Doctor).order_by(Doctor.username).all()

    return render_template("manager_dashboard.html",
                           search_code=search_code,
                           student_data=student_data,
                           student_db=student_db,
                           error_msg=error_msg,
                           all_fields=True,
                           all_opinions=all_opinions,
                           all_doctors=all_doctors)

@app.route("/manager/send_message", methods=["POST"])
def send_manager_message():
    if not require_manager(): return redirect(url_for("login"))

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
                    db.add(Message(
                        student_code=str(code),
                        doctor_username="Manager",
                        text=f"[MANAGER] {message_text}"
                    ))

        if recipient_type == "doctors" or recipient_type == "all":
            # Send to all doctors — logged in their Activity Log
            doctors = db.query(Doctor).all()
            for doc in doctors:
                db.add(ActivityLog(
                    doctor_username=doc.username,
                    action="MANAGER_MESSAGE",
                    details=f"[Manager] {message_text}"
                ))

        if recipient_type == "one_student":
            target_code = request.form.get("target_code", "").strip()
            if not target_code:
                flash("Please enter a student code.")
                return redirect(url_for("manager_dashboard"))
            db.add(Message(
                student_code=target_code,
                doctor_username="Manager",
                text=f"[MANAGER] {message_text}"
            ))

        if recipient_type == "one_doctor":
            target_doctor = request.form.get("target_doctor", "").strip()
            if not target_doctor:
                flash("Please select or enter a doctor username.")
                return redirect(url_for("manager_dashboard"))
            db.add(ActivityLog(
                doctor_username=target_doctor,
                action="MANAGER_MESSAGE",
                details=f"[Manager] {message_text}"
            ))