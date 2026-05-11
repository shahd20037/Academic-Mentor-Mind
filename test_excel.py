import pandas as pd

EXCEL_PATH = "C:\Users\salma - Personal\Desktop\backend\data\Student_performance_dataset.xlsx"

df = pd.read_excel(EXCEL_PATH)
print(df.head())