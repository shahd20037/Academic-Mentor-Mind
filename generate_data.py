wfrom faker import Faker
import pandas as pd

# إعداد مكتبة Faker
fake = Faker()

# إنشاء بيانات وهمية لعدد من الطلاب
students_data = []
for _ in range(1000):  # لإنشاء 1000 سجل طلاب
    student = {
        "Student ID": fake.unique.random_number(digits=6),
        "Full Name": fake.name(),
        "Level": fake.random_element(elements=("Beginner", "Intermediate", "Advanced")),
        "Department": fake.random_element(elements=("Computer Science", "Engineering", "Medicine", "Business")),
        "Risk Level": fake.random_element(elements=("High", "Medium", "Low")),
        "Email": fake.email(),
        "Phone": fake.phone_number(),
        "Date of Birth": fake.date_of_birth(minimum_age=18, maximum_age=25),
    }
    students_data.append(student)

# تحويل البيانات إلى DataFrame
df = pd.DataFrame(students_data)

# حفظ البيانات في ملف Excel
df.to_excel("students_data.xlsx", index=False)

print("Data generated successfully and saved to 'students_data.xlsx'.")
