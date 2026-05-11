"""
Run this file ONCE to add the missing columns to attendance_records table.
Usage:  python migrate_attendance.py
"""

import sqlite3
import os

# ── Change this path if your db file is somewhere else ──
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

COLUMNS_TO_ADD = [
    ("ip_address",       "TEXT"),
    ("latitude",         "REAL"),
    ("longitude",        "REAL"),
    ("attempt_count",    "INTEGER DEFAULT 1"),
    ("is_suspicious",    "INTEGER DEFAULT 0"),
    ("suspicious_reason","TEXT"),
]

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # Get existing columns
    cur.execute("PRAGMA table_info(attendance_records)")
    existing = {row[1] for row in cur.fetchall()}

    added = []
    for col_name, col_type in COLUMNS_TO_ADD:
        if col_name not in existing:
            sql = f"ALTER TABLE attendance_records ADD COLUMN {col_name} {col_type}"
            cur.execute(sql)
            added.append(col_name)
            print(f"  ✅ Added column: {col_name}")
        else:
            print(f"  ⏭  Already exists: {col_name}")

    conn.commit()
    conn.close()

    if added:
        print(f"\nDone! Added {len(added)} column(s). Restart Flask now.")
    else:
        print("\nNothing to add — all columns already exist.")

if __name__ == "__main__":
    migrate()