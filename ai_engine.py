import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier

# --- إعداد المسارات ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "student_model.pkl")
# إذا كان ملف الاكسيل في مجلد اسمه data بجانب الكود:
EXCEL_PATH = os.path.join(BASE_DIR, 'data', 'Student_performance_dataset.xlsx')

# --- الميزات المطلوبة للتدريب ---
features = [
    "attendance", "assignment_avg", "midterm", "practical", "project", 
    "final", "quiz_avg", "oral_avg", "gpa", "participation", 
    "study_hours", "previous_gpa", "class_interaction"
]

# --- تحميل الموديل أو تدريبه من جديد ---
if os.path.exists(MODEL_PATH):
    model = joblib.load(MODEL_PATH)
    print("✅ The model was successfully uploaded.")
else:
    if os.path.exists(EXCEL_PATH):
        print("⏳ The model is currently being trained, please wait...")
        df = pd.read_excel(EXCEL_PATH)
        
        # تنظيف العناوين لتتطابق مع الـ features (حروف صغيرة وتبديل المسافات بـ _)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        
        # التأكد من وجود الأعمدة المطلوبة
        X = df[features]
        y = df["risk_level"]

        # تدريب الموديل
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        model = RandomForestClassifier(n_estimators=100)
        model.fit(X_train, y_train)
        
        joblib.dump(model, MODEL_PATH)
        print("✅The model was trained and saved.")
    else:
        print(f"❌ Error: The Excel file is not found in: {EXCEL_PATH}")
        model = None

def analyze_student_data(student: dict) -> dict:
    if model is None:
        return {"error": "Model is not initialized."}
    try:
        # ترتيب البيانات القادمة من الطالب بنفس ترتيب الـ features
        # نحول مفاتيح القاموس لـ lowercase لضمان التطابق
        std_data = {k.lower().replace(" ", "_"): v for k, v in student.items()}
        input_row = [float(std_data.get(f, 0)) for f in features]
        
        prediction = model.predict([input_row])[0]
        
        return {
            "risk_level": prediction,
            "advice": "Keep up the good work!" if prediction.lower() == 'low' else "Focus more on your studies."
        }
    except Exception as e:
        return {"error": str(e)}