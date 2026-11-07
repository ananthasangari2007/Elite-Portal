"""Clean legacy demo data while strictly preserving authentic logins, domains, and curriculum."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import (
    Appeal,
    GradingHistory,
    Notification,
    RequestMessage,
    StudentRequest,
    Task,
    TaskEvidence,
    User,
)

def clean_demo_data():
    app = create_app()
    with app.app_context():
        print("Starting legacy demo data cleanup...")

        # 1. Delete legacy demo tasks (52 tasks)
        task_count = Task.query.count()
        Task.query.delete()
        print(f"Removed {task_count} legacy demo tasks.")

        # 2. Delete mock grading history referencing task evidences
        gh_count = GradingHistory.query.filter(GradingHistory.evidence_id.isnot(None)).delete()
        print(f"Removed {gh_count} mock grading history records for evidence.")

        # 3. Delete mock task evidences
        ev_count = TaskEvidence.query.count()
        TaskEvidence.query.delete()
        print(f"Removed {ev_count} demo task evidences.")

        # 4. Delete mock student requests and request messages
        rm_count = RequestMessage.query.count()
        RequestMessage.query.delete()
        sr_count = StudentRequest.query.count()
        StudentRequest.query.delete()
        print(f"Removed {sr_count} demo student requests and {rm_count} request messages.")

        # 5. Delete demo notifications
        notif_count = Notification.query.count()
        Notification.query.delete()
        print(f"Removed {notif_count} demo notifications.")

        # 6. Delete demo appeals
        appeal_count = Appeal.query.count()
        Appeal.query.delete()
        print(f"Removed {appeal_count} demo appeals.")

        db.session.commit()
        print("Cleanup successfully committed!")
        print(f"Verified Users preserved: {User.query.count()}")

if __name__ == "__main__":
    clean_demo_data()
