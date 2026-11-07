"""Safe database enrichment & dummy cleanup script for Elite Portal production readiness.

Removes temporary smoke-test artifacts while preserving all valid users, real assessments,
point ledgers, and institutional configurations.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db
from app.models import (
    Announcement,
    Appeal,
    Assessment,
    AssessmentAnswer,
    AssessmentAttempt,
    AssessmentAuthorization,
    AssessmentOption,
    AssessmentQuestion,
    AuditLog,
    CodingSubmission,
    ContentCompletion,
    Domain,
    DomainAssignment,
    EliteSprintBid,
    EliteSprintSession,
    GradingHistory,
    LearningDay,
    LearningMaterial,
    Notification,
    PasswordResetToken,
    PointAdjustmentRequest,
    PointLedger,
    PointTransaction,
    RequestMessage,
    StudentDomainEnrollment,
    StudentRequest,
    Submission,
    SupportMessage,
    SystemSetting,
    TaskEvidence,
    TestCase,
    User,
)

def clean_and_enrich():
    app = create_app()
    with app.app_context():
        print("Starting production data cleanup and enrichment...", flush=True)

        # 1. Clean dummy smoke test announcements
        deleted_ann = Announcement.query.filter(
            Announcement.title.ilike("%smoke test%")
        ).delete(synchronize_session=False)
        db.session.commit()
        print(f"[OK] Removed {deleted_ann} smoke test announcements.", flush=True)

        # 2. Clean dummy assessments (IDs 7..13 created by automated smoke runner)
        dummy_assessments = Assessment.query.filter(
            Assessment.id.in_([7, 8, 9, 10, 11, 12, 13])
        ).all()
        for a in dummy_assessments:
            for att in a.attempts:
                AssessmentAnswer.query.filter_by(attempt_id=att.id).delete(synchronize_session=False)
                CodingSubmission.query.filter_by(attempt_id=att.id).delete(synchronize_session=False)
                db.session.delete(att)
            AssessmentAuthorization.query.filter_by(assessment_id=a.id).delete(synchronize_session=False)
            for q in a.questions:
                AssessmentOption.query.filter_by(question_id=q.id).delete(synchronize_session=False)
                TestCase.query.filter_by(question_id=q.id).delete(synchronize_session=False)
                db.session.delete(q)
            db.session.delete(a)
        db.session.commit()
        print(f"[OK] Removed {len(dummy_assessments)} dummy assessments.", flush=True)

        # 3. Clean dummy learning days & materials
        ContentCompletion.query.filter(ContentCompletion.learning_day_id.in_([4, 5, 6, 7, 8, 9])).delete(synchronize_session=False)
        LearningMaterial.query.filter(
            (LearningMaterial.learning_day_id.in_([4, 5, 6, 7, 8, 9])) |
            (LearningMaterial.id.in_([10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]))
        ).delete(synchronize_session=False)
        deleted_days = LearningDay.query.filter(LearningDay.id.in_([4, 5, 6, 7, 8, 9])).delete(synchronize_session=False)
        db.session.commit()
        print(f"[OK] Removed {deleted_days} dummy learning days and related materials.", flush=True)

        # 4. Clean temporary dev users (@example.com)
        dummy_users = User.query.filter(User.email.ilike("%@example.com%")).all()
        dummy_user_ids = [u.id for u in dummy_users]

        if dummy_user_ids:
            print(f"Found {len(dummy_user_ids)} dev users to delete: {dummy_user_ids}", flush=True)
            admin_user = User.query.filter(User.email == "admin@elite.edu").first()
            admin_id = admin_user.id if admin_user else 1

            # 1. Reassign administrative ownership
            Domain.query.filter(Domain.created_by.in_(dummy_user_ids)).update({Domain.created_by: admin_id}, synchronize_session=False)
            LearningDay.query.filter(LearningDay.created_by.in_(dummy_user_ids)).update({LearningDay.created_by: admin_id}, synchronize_session=False)
            LearningMaterial.query.filter(LearningMaterial.created_by.in_(dummy_user_ids)).update({LearningMaterial.created_by: admin_id}, synchronize_session=False)
            Assessment.query.filter(Assessment.created_by.in_(dummy_user_ids)).update({Assessment.created_by: admin_id}, synchronize_session=False)
            Announcement.query.filter(Announcement.created_by.in_(dummy_user_ids)).update({Announcement.created_by: admin_id}, synchronize_session=False)
            SystemSetting.query.filter(SystemSetting.updated_by.in_(dummy_user_ids)).update({SystemSetting.updated_by: admin_id}, synchronize_session=False)

            # 2. Grading History (must be deleted before task evidence and attempts)
            GradingHistory.query.filter(
                (GradingHistory.graded_by.in_(dummy_user_ids)) |
                (GradingHistory.evidence_id.in_(
                    db.session.query(TaskEvidence.id).filter(
                        (TaskEvidence.student_id.in_(dummy_user_ids)) | (TaskEvidence.reviewed_by.in_(dummy_user_ids))
                    )
                )) |
                (GradingHistory.attempt_id.in_(
                    db.session.query(AssessmentAttempt.id).filter(AssessmentAttempt.student_id.in_(dummy_user_ids))
                ))
            ).delete(synchronize_session=False)

            # 3. Appeals & Point Adjustment Requests
            Appeal.query.filter(
                (Appeal.student_id.in_(dummy_user_ids)) |
                (Appeal.assigned_to.in_(dummy_user_ids)) |
                (Appeal.resolved_by.in_(dummy_user_ids))
            ).delete(synchronize_session=False)

            PointAdjustmentRequest.query.filter(
                (PointAdjustmentRequest.student_id.in_(dummy_user_ids)) |
                (PointAdjustmentRequest.requested_by.in_(dummy_user_ids)) |
                (PointAdjustmentRequest.reviewed_by.in_(dummy_user_ids))
            ).delete(synchronize_session=False)

            # 4. Task Evidence
            TaskEvidence.query.filter(
                (TaskEvidence.student_id.in_(dummy_user_ids)) |
                (TaskEvidence.reviewed_by.in_(dummy_user_ids))
            ).delete(synchronize_session=False)

            # 5. Point Ledger & Transactions
            PointLedger.query.filter(PointLedger.reversed_by.in_(dummy_user_ids)).update({PointLedger.reversed_by: None}, synchronize_session=False)
            PointLedger.query.filter(PointLedger.created_by.in_(dummy_user_ids)).update({PointLedger.created_by: admin_id}, synchronize_session=False)
            PointLedger.query.filter(PointLedger.student_id.in_(dummy_user_ids)).delete(synchronize_session=False)
            PointTransaction.query.filter(
                (PointTransaction.student_id.in_(dummy_user_ids)) | (PointTransaction.approved_by.in_(dummy_user_ids))
            ).delete(synchronize_session=False)

            # 6. Domain Assignments
            DomainAssignment.query.filter(
                (DomainAssignment.user_id.in_(dummy_user_ids)) | (DomainAssignment.assigned_by.in_(dummy_user_ids))
            ).delete(synchronize_session=False)

            # 7. Attempts & student progress
            student_attempts = AssessmentAttempt.query.filter(AssessmentAttempt.student_id.in_(dummy_user_ids)).all()
            for att in student_attempts:
                AssessmentAnswer.query.filter_by(attempt_id=att.id).delete(synchronize_session=False)
                CodingSubmission.query.filter_by(attempt_id=att.id).delete(synchronize_session=False)
                db.session.delete(att)

            AssessmentAuthorization.query.filter(
                (AssessmentAuthorization.student_id.in_(dummy_user_ids)) | (AssessmentAuthorization.authorized_by.in_(dummy_user_ids))
            ).delete(synchronize_session=False)

            StudentDomainEnrollment.query.filter(StudentDomainEnrollment.student_id.in_(dummy_user_ids)).delete(synchronize_session=False)
            ContentCompletion.query.filter(ContentCompletion.student_id.in_(dummy_user_ids)).delete(synchronize_session=False)
            AuditLog.query.filter(AuditLog.actor_id.in_(dummy_user_ids)).delete(synchronize_session=False)
            Notification.query.filter(Notification.user_id.in_(dummy_user_ids)).delete(synchronize_session=False)
            PasswordResetToken.query.filter(PasswordResetToken.user_id.in_(dummy_user_ids)).delete(synchronize_session=False)

            # 8. Elite Sprint, Submissions & Student Requests
            EliteSprintBid.query.filter(EliteSprintBid.student_id.in_(dummy_user_ids)).delete(synchronize_session=False)
            EliteSprintSession.query.filter(EliteSprintSession.created_by.in_(dummy_user_ids)).update({EliteSprintSession.created_by: admin_id}, synchronize_session=False)

            Submission.query.filter(
                (Submission.student_id.in_(dummy_user_ids)) | (Submission.reviewed_by.in_(dummy_user_ids))
            ).delete(synchronize_session=False)
            SupportMessage.query.filter(SupportMessage.student_id.in_(dummy_user_ids)).delete(synchronize_session=False)

            reqs = StudentRequest.query.filter(StudentRequest.student_id.in_(dummy_user_ids)).all()
            for r in reqs:
                RequestMessage.query.filter_by(request_id=r.id).delete(synchronize_session=False)
                db.session.delete(r)

            db.session.commit()

            User.query.filter(User.id.in_(dummy_user_ids)).delete(synchronize_session=False)
            db.session.commit()
            print("[OK] Dev users (@example.com) and associated records deleted.", flush=True)

        # 5. Enrich DSA Learning Materials with real educational URLs
        m1 = db.session.get(LearningMaterial, 1)
        if m1:
            m1.url = "https://www.youtube.com/watch?v=-b2l3ptgST4"
            m1.description = "Core two-pointer technique patterns for array searching and sorting."

        m3 = db.session.get(LearningMaterial, 3)
        if m3:
            m3.url = "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/"
            m3.description = "Solve Two Sum II on LeetCode using the Two Pointer approach."

        m4 = db.session.get(LearningMaterial, 4)
        if m4:
            m4.url = "https://www.youtube.com/watch?v=73r3msbvU5g"
            m4.description = "Hashing internals, collision handling, and frequency mapping."

        m6 = db.session.get(LearningMaterial, 6)
        if m6:
            m6.url = "https://leetcode.com/problems/valid-anagram/"
            m6.description = "Solve Valid Anagram on LeetCode with hash map frequency counts."

        m7 = db.session.get(LearningMaterial, 7)
        if m7:
            m7.url = "https://www.youtube.com/watch?v=G0_I-ZF0S38"
            m7.description = "Singly vs Doubly Linked Lists, pointer manipulation, and traversal."

        m9 = db.session.get(LearningMaterial, 9)
        if m9:
            m9.url = "https://leetcode.com/problems/reverse-linked-list/"
            m9.description = "Reverse a Singly Linked List iteratively and recursively on LeetCode."

        # 6. Ensure Full Stack, AI/ML, and Embedded have initial curriculum
        fs_domain = Domain.query.filter_by(code="FULLSTACK").first()
        admin_user = User.query.filter_by(role="admin").first()
        admin_id = admin_user.id if admin_user else 1

        if fs_domain and LearningDay.query.filter_by(domain_id=fs_domain.id).count() == 0:
            print("Seeding initial Full Stack curriculum...", flush=True)
            fs_day1 = LearningDay(
                domain_id=fs_domain.id,
                day_number=1,
                title="Modern React Architecture & Component Patterns",
                description="Hooks, component composition, TypeScript integration, and state design.",
                status="published",
                created_by=admin_id,
            )
            db.session.add(fs_day1)
            db.session.flush()

            db.session.add(
                LearningMaterial(
                    learning_day_id=fs_day1.id,
                    title="React 18 & TypeScript Masterclass",
                    material_type="video",
                    url="https://www.youtube.com/watch?v=2OTq15x542U",
                    description="Deep dive into modern component architectures, custom hooks, and memoization.",
                    display_order=1,
                    status="published",
                    created_by=admin_id,
                )
            )
            db.session.add(
                LearningMaterial(
                    learning_day_id=fs_day1.id,
                    title="React Official Documentation & Best Practices",
                    material_type="link",
                    url="https://react.dev/learn",
                    description="Official React documentation covering pure components and state management.",
                    display_order=2,
                    status="published",
                    created_by=admin_id,
                )
            )

        aiml_domain = Domain.query.filter_by(code="AIML").first()
        if aiml_domain and LearningDay.query.filter_by(domain_id=aiml_domain.id).count() == 0:
            print("Seeding initial AI/ML curriculum...", flush=True)
            aiml_day1 = LearningDay(
                domain_id=aiml_domain.id,
                day_number=1,
                title="NumPy, Pandas & Exploratory Data Analysis",
                description="Vectorized operations, data cleaning, feature analysis, and statistical distributions.",
                status="published",
                created_by=admin_id,
            )
            db.session.add(aiml_day1)
            db.session.flush()

            db.session.add(
                LearningMaterial(
                    learning_day_id=aiml_day1.id,
                    title="Data Analysis with Python & Pandas",
                    material_type="video",
                    url="https://www.youtube.com/watch?v=vmEHCJofslg",
                    description="Practical tutorial on dataframe manipulation, grouping, and transformations.",
                    display_order=1,
                    status="published",
                    created_by=admin_id,
                )
            )
            db.session.add(
                LearningMaterial(
                    learning_day_id=aiml_day1.id,
                    title="Kaggle Pandas Exercises & Cheat Sheet",
                    material_type="link",
                    url="https://www.kaggle.com/learn/pandas",
                    description="Hands-on interactive tutorial and practice on real tabular datasets.",
                    display_order=2,
                    status="published",
                    created_by=admin_id,
                )
            )

        emb_domain = Domain.query.filter_by(code="EMBEDDED").first()
        if emb_domain and LearningDay.query.filter_by(domain_id=emb_domain.id).count() == 0:
            print("Seeding initial Embedded Systems curriculum...", flush=True)
            emb_day1 = LearningDay(
                domain_id=emb_domain.id,
                day_number=1,
                title="Microcontroller Architecture & GPIO Programming",
                description="Memory maps, register manipulation, digital I/O, and hardware timers.",
                status="published",
                created_by=admin_id,
            )
            db.session.add(emb_day1)
            db.session.flush()

            db.session.add(
                LearningMaterial(
                    learning_day_id=emb_day1.id,
                    title="Embedded C & Microcontroller Fundamentals",
                    material_type="video",
                    url="https://www.youtube.com/watch?v=3V9eqskKs00",
                    description="Embedded systems programming paradigms, interrupts, and memory layout.",
                    display_order=1,
                    status="published",
                    created_by=admin_id,
                )
            )
            db.session.add(
                LearningMaterial(
                    learning_day_id=emb_day1.id,
                    title="ARM Cortex-M Architecture Manual",
                    material_type="link",
                    url="https://developer.arm.com/documentation",
                    description="Official reference manual for Cortex-M programming and peripheral registers.",
                    display_order=2,
                    status="published",
                    created_by=admin_id,
                )
            )

        db.session.commit()
        print("Database cleanup and enrichment complete!", flush=True)

if __name__ == "__main__":
    clean_and_enrich()
