import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from sqlalchemy import text

def run_migration():
    app = create_app()
    with app.app_context():
        print("Migrating assessment allowed_languages and task_evidence constraint...")

        # 1. Add allowed_languages column to assessment table
        try:
            db.session.execute(text("ALTER TABLE assessment ADD COLUMN IF NOT EXISTS allowed_languages JSONB DEFAULT '[]'::jsonb;"))
            print("Successfully ensured 'allowed_languages' column on assessment.")
        except Exception as e:
            print("Error adding allowed_languages column:", e)

        # 2. Update task_evidence unique constraint to per-task per-day
        try:
            db.session.execute(text("ALTER TABLE task_evidence DROP CONSTRAINT IF EXISTS uq_daily_task_evidence;"))
            print("Dropped old constraint uq_daily_task_evidence if existed.")
        except Exception as e:
            print("Error dropping old constraint:", e)

        try:
            db.session.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_daily_task_evidence_per_task'
                    ) THEN
                        ALTER TABLE task_evidence ADD CONSTRAINT uq_daily_task_evidence_per_task UNIQUE (student_id, task_id, submission_date);
                    END IF;
                END $$;
            """))
            print("Successfully ensured uq_daily_task_evidence_per_task constraint.")
        except Exception as e:
            print("Error creating per-task constraint:", e)

        db.session.commit()
        print("Migration complete!")

if __name__ == '__main__':
    run_migration()
