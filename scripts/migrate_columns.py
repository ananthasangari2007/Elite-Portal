import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from sqlalchemy import inspect

app = create_app()
with app.app_context():
    inspector = inspect(db.engine)
    with db.engine.connect() as conn:
        # Check user columns
        user_cols = {c["name"] for c in inspector.get_columns("user")}
        if "phone_number" not in user_cols:
            conn.execute(db.text('ALTER TABLE "user" ADD COLUMN phone_number VARCHAR(30)'))
            print("Added phone_number to user table")

        # Check assessment columns
        assessment_cols = {c["name"] for c in inspector.get_columns("assessment")}
        if "grading_mode" not in assessment_cols:
            conn.execute(db.text("ALTER TABLE assessment ADD COLUMN grading_mode VARCHAR(30) DEFAULT 'automatic'"))
            print("Added grading_mode to assessment table")
        if "attendance_points" not in assessment_cols:
            conn.execute(db.text("ALTER TABLE assessment ADD COLUMN attendance_points INTEGER DEFAULT 5"))
            print("Added attendance_points to assessment table")
        if "allowed_languages" not in assessment_cols:
            conn.execute(db.text("ALTER TABLE assessment ADD COLUMN allowed_languages TEXT DEFAULT '[]'"))
            print("Added allowed_languages to assessment table")

        conn.commit()
    print("Database columns verified and added successfully.")
