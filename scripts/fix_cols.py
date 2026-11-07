import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, db
app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        for sql in [
            'ALTER TABLE "user" ADD COLUMN phone_number VARCHAR(30)',
            "ALTER TABLE assessment ADD COLUMN grading_mode VARCHAR(30) DEFAULT 'automatic'",
            "ALTER TABLE assessment ADD COLUMN attendance_points INTEGER DEFAULT 5",
        ]:
            try:
                conn.execute(db.text(sql)); conn.commit(); print("ok", sql)
            except Exception as e:
                print("skip", sql, e)
