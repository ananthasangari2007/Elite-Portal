import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS phone_number VARCHAR(30)'))
        conn.execute(db.text("ALTER TABLE assessment ADD COLUMN IF NOT EXISTS grading_mode VARCHAR(30) DEFAULT 'automatic'"))
        conn.execute(db.text("ALTER TABLE assessment ADD COLUMN IF NOT EXISTS attendance_points INTEGER DEFAULT 5"))
        conn.commit()
    print("Database columns verified and added successfully.")
