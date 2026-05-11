# ===============================
# Doctor Messages (send to students, replaces old doctor_chat for students)
# ===============================
@app.route("/doctor/messages", methods=["GET", "POST"])
def doctor_messages():
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))

    db = get_db()

    if request.method == "POST":
        recipient_type = request.form.get("recipient_type", "all")
        msg_text = request.form.get("message", "").strip()
        student_code = request.form.get("student_code", "").strip()

        if not msg_text:
            flash("Message cannot be empty.", "error")
            return redirect(url_for("doctor_messages"))

        try:
            if recipient_type == "all":
                df = load_students()
                col = detect_student_code_column(df)
                if col:
                    for code in df[col].astype(str).unique():
                        db.add(Message(
                            student_code=str(code),
                            doctor_username=doctor,
                            text=f"[DOCTOR] {msg_text}"
                        ))
                    log_activity(db, doctor, "SEND_MESSAGE", f"Broadcast to all students: {msg_text[:80]}")
                    flash("Message sent to all students!", "success")
            else:
                if not student_code:
                    flash("Please enter a student code.", "error")
                    return redirect(url_for("doctor_messages"))
                if not get_student_by_code(student_code):
                    flash(f"No student found with code: {student_code}", "error")
                    return redirect(url_for("doctor_messages"))
                db.add(Message(
                    student_code=student_code,
                    doctor_username=doctor,
                    text=f"[DOCTOR] {msg_text}"
                ))
                create_notification(db, student_code, f"New message from Dr. {doctor}", msg_text[:80])
                log_activity(db, doctor, "SEND_MESSAGE", f"Sent message to student {student_code}: {msg_text[:80]}")
                flash(f"Message sent to student {student_code}!", "success")
            db.commit()
        except Exception as e:
            db.rollback()
            flash(f"Error: {str(e)}", "error")

        return redirect(url_for("doctor_messages"))

    # GET — show all messages sent by this doctor
    messages = db.query(Message).filter(
        Message.doctor_username == doctor
    ).order_by(Message.created_at.desc()).all()

    return render_template("doctor_messages.html", doctor=doctor, messages=messages)


@app.route("/doctor/messages/delete/<int:message_id>", methods=["POST"])
def doctor_delete_message(message_id):
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))

    db = get_db()
    msg = db.query(Message).filter_by(id=message_id, doctor_username=doctor).first()
    if msg:
        db.delete(msg)
        db.commit()
        flash("Message deleted.", "success")
    return redirect(url_for("doctor_messages"))


# Student inbox for doctor messages
@app.route("/student/doctor-messages")
def student_doctor_messages():
    code = require_student()
    if not code: return redirect(url_for("login"))

    db = get_db()
    messages = db.query(Message).filter(
        Message.student_code == str(code),
        Message.doctor_username != "Manager"
    ).order_by(Message.created_at.desc()).all()

    return render_template("student_doctor_messages.html", messages=messages)


@app.route("/student/doctor-messages/delete/<int:message_id>", methods=["POST"])
def student_delete_doctor_message(message_id):
    code = require_student()
    if not code: return redirect(url_for("login"))

    db = get_db()
    msg = db.query(Message).filter_by(id=message_id, student_code=str(code)).first()
    if msg and msg.doctor_username != "Manager":
        db.delete(msg)
        db.commit()
        flash("Message deleted.", "success")
    return redirect(url_for("student_doctor_messages"))


# Keep old doctor_chat route for backwards compat — redirect to new page
@app.route("/doctor-chat")
def doctor_chat():
    if session.get("student_code"):
        return redirect(url_for("student_doctor_messages"))
    if session.get("doctor"):
        return redirect(url_for("doctor_messages"))
    return redirect(url_for("login"))
# ===============================
# Doctor task center
# ===============================

@app.route("/doctor/task_center", methods=["GET", "POST"])
def doctor_task_center():
    doctor = require_doctor()
    if not doctor: return redirect(url_for("login"))