"""
migrate_integrity.py
--------------------
Run this ONCE to add the new Integrity Report columns to the
existing attendance_records table without losing any data.

Usage:
    python migrate_integrity.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "app.db")

# Also try the root app.db if instance one not found
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

print(f"[migrate] Using DB: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

# Get existing columns
cur.execute("PRAGMA table_info(attendance_records)")
existing = {row[1] for row in cur.fetchall()}
print(f"[migrate] Existing columns: {existing}")

new_columns = {
    "ip_address":        "TEXT",
    "latitude":          "TEXT",
    "longitude":         "TEXT",
    "attempt_count":     "INTEGER DEFAULT 1",
    "is_suspicious":     "INTEGER DEFAULT 0",
    "suspicious_reason": "TEXT",
}

for col, col_type in new_columns.items():
    if col not in existing:
        sql = f"ALTER TABLE attendance_records ADD COLUMN {col} {col_type}"
        cur.execute(sql)
        print(f"[migrate] ✅ Added column: {col}")
    else:
        print(f"[migrate] ⏭  Column already exists: {col}")

conn.commit()
conn.close()
print("[migrate] Done — DB updated successfully.")