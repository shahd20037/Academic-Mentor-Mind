import os
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ==========================================
# 1. AI TUTOR (شرح الملفات والأسئلة)
# ==========================================
def process_pdf_and_answer(question, pdf_path=None):
    """
    هذه الدالة هي المعلم الخاص (Tutor). 
    تستخدم الـ ML للبحث داخل الـ PDF عن إجابة لسؤال الطالب.
    """
    try:
        context = ""
        # استخراج النص من ملف الـ PDF
        if pdf_path and os.path.exists(pdf_path):
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    context += text + " "
        
        if not context or len(context.strip()) < 20:
            return "Please upload a lesson (PDF) so I can help you with a specific answer."

        # تقسيم النص إلى جمل
        sentences = [s.strip() for s in context.split('.') if len(s.strip()) > 10]
        
        # إضافة سؤال الطالب للمجموعة للمقارنة بينه وبين الجمل
        all_texts = sentences + [question]
        
        # تحويل النصوص إلى أرقام (Vectors) باستخدام TF-IDF
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(all_texts)
        
        # حساب مدى تشابه السؤال مع كل جملة في الملف
        scores = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
        
        # اختيار الجملة الأكثر تشابهاً
        best_match_idx = scores.argsort()[0][-1]
        
        # إذا كان التشابه ضعيفاً جداً (أقل من 10%)
        if scores[0][best_match_idx] < 0.1:
            return "I couldn't find a direct answer in the file, but I've notified your doctor to help you further."

        return f"From the materials: {sentences[best_match_idx]}"

    except Exception as e:
        return f"Error in AI Tutor: {str(e)}"


# ==========================================
# 2. AI ADVISOR (نصيحة المستوى الدراسي واقتراح القسم)
# ==========================================
def generate_ai_student_advice(student_data):
    """
    هذه الدالة هي المستشار (Advisor).
    تحلل بيانات الطالب وتحدد مستوى الخطورة والنصيحة، بالإضافة لاقتراح القسم المناسب.
    تعتمد على GPA والدرجات الفعلية للمواد.
    """
    try:
        # تحويل القيم لأرقام لضمان عمل العمليات الحسابية
        attendance = float(student_data.get('attendance', 100))
        fail_prob = float(student_data.get('fail_probability', 0))
        risk = str(student_data.get('risk_level', 'Low')).capitalize()
        
        # استخراج GPA
        gpa = None
        gpa_val = student_data.get('gpa') or student_data.get('GPA')
        if gpa_val:
            try:
                gpa = float(gpa_val)
            except:
                gpa = None
        
        # منطق النصيحة المعتمد على الحالة العامة و GPA
        advice_text = ""
        
        if risk == "High" or fail_prob > 0.7:
            advice_text = "⚠️ CRITICAL: Your academic performance is at high risk. Immediate focus on pending tasks and meeting your doctor is required. Don't give up - you can turn this around!"
        elif gpa and gpa < 2.0:
            advice_text = "⚠️ WARNING: Your GPA is below 2.0. This is a critical moment. Focus on improving your grades in upcoming assessments. Use the AI Tutor to strengthen weak areas."
        elif gpa and gpa < 2.5:
            advice_text = "⚠️ CAUTION: Your GPA is around 2.5. You need to improve your performance. Increase your study hours and engage more actively in class."
        elif attendance < 70:
            advice_text = "📌 ATTENTION: Your low attendance rate ({}%) is affecting your progress. Please attend more sessions to stay on track and improve your grades.".format(int(attendance))
        elif fail_prob > 0.3:
            advice_text = "📚 IMPROVEMENT NEEDED: Your grades are showing some instability. Use the AI Tutor to review difficult topics and practice more."
        elif gpa and gpa >= 3.5:
            advice_text = "🌟 EXCELLENT: Your performance is outstanding with a GPA of {:.2f}! Keep up the great work and maintain your high standards.".format(gpa)
        elif gpa and gpa >= 3.0:
            advice_text = "✅ GOOD: Your performance is solid with a GPA of {:.2f}. Keep maintaining this level and aim for continuous improvement.".format(gpa)
        else:
            advice_text = "✅ CONSISTENT: Your performance is consistent. Keep up the great work and maintain your participation level."
        
        # --- Career Path Advice (Enhanced with GPA) ---
        career_advice = ""
        
        # قائمة المواد المحتملة في الإكسيل
        subject_columns = {
            "midterm": "Midterm Exam",
            "practical": "Practical Work",
            "project": "Project Work",
            "final": "Final Exam",
            "quiz_avg": "Quizzes",
            "oral_avg": "Oral Exams",
            "assignment_avg": "Assignments"
        }
        
        # استخراج الدرجات الفعلية للمواد الموجودة في بيانات الطالب
        actual_scores = {}
        for col, display_name in subject_columns.items():
            val = student_data.get(col)
            if val is not None:
                try:
                    actual_scores[display_name] = float(val)
                except:
                    continue

        if actual_scores:
            # العثور على أعلى الدرجات (قد يكون هناك أكثر من مادة بنفس الدرجة العالية)
            max_val = max(actual_scores.values())
            top_subjects = [sub for sub, score in actual_scores.items() if score == max_val]
            
            # خريطة الأقسام بناءً على التميز في نوع معين من التقييمات
            dept_mapping = {
                "Midterm Exam": "Academic Research & Theoretical Sciences",
                "Practical Work": "Information Technology / Engineering / Computer Science",
                "Project Work": "Software Development / Project Management / Systems Engineering",
                "Final Exam": "Theoretical Sciences / Research",
                "Quizzes": "Data Analysis / Statistics / Business Analytics",
                "Oral Exams": "Communications / Marketing / Public Relations",
                "Assignments": "Technical Writing / Documentation / Software Engineering"
            }
            
            suggested_depts = list(set([dept_mapping.get(sub, "General Specialization") for sub in top_subjects]))
            subjects_str = " and ".join(top_subjects)
            depts_str = " or ".join(suggested_depts)
            
            career_advice = f"\n\n💡 **Career Guidance:** Based on your performance, your highest scores are in **{subjects_str}**. This suggests you might excel in the **{depts_str}** department. Explore these fields to leverage your strengths!"
        
        # إضافة نصيحة إضافية بناءً على GPA
        if gpa:
            if gpa >= 3.8:
                career_advice += "\n\n🎓 **Recommendation:** With your exceptional GPA, consider applying for advanced programs, scholarships, or research opportunities!"
            elif gpa >= 3.5:
                career_advice += "\n\n🎓 **Recommendation:** Your strong GPA opens doors to competitive programs and internships. Aim higher!"
            elif gpa >= 3.0:
                career_advice += "\n\n🎓 **Recommendation:** Your GPA is competitive. Focus on gaining practical experience through internships and projects."
            elif gpa >= 2.5:
                career_advice += "\n\n🎓 **Recommendation:** Work on improving your GPA to unlock more opportunities. Consistency is key!"
            else:
                career_advice += "\n\n🎓 **Recommendation:** Your GPA needs improvement. Focus on mastering the fundamentals and seek help from your instructors."
        
        return {
            "risk_level": risk,
            "advice": advice_text + career_advice,
            "gpa": gpa
        }
    except Exception as e:
        return {
            "risk_level": "N/A",
            "advice": "Keep working hard and follow your study plan. You've got this! 💪",
            "gpa": None
        }