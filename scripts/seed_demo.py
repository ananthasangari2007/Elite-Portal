"""Idempotent demo data seed for the Elite Portal.

Usage:
    python scripts/seed_demo.py

Creates coordinator/faculty/student accounts, enrollments, learning days,
materials, assessments, Elite Tasks and announcements so every dashboard has
real, database-backed data.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app, db  # noqa: E402
from app.models import (  # noqa: E402
    Announcement,
    Assessment,
    AssessmentOption,
    AssessmentQuestion,
    ContentCompletion,
    Domain,
    DomainAssignment,
    EliteTask,
    LearningDay,
    LearningMaterial,
    PointLedger,
    StudentDomainEnrollment,
    User,
)
from app.models import TestCase  # noqa: E402

DEMO_PASSWORD = "Elite@1234"

STUDENTS = [
    ("Aarthi Raman", "aarthi@elite.edu", "FXEC2025CS001", "CSE"),
    ("Bharath Kumar", "bharath@elite.edu", "FXEC2025CS002", "CSE"),
    ("Charu Nivedita", "charu@elite.edu", "FXEC2025IT003", "IT"),
    ("Dinesh Raj", "dinesh@elite.edu", "FXEC2025AI004", "AI&DS"),
    ("Ezhil Arasan", "ezhil@elite.edu", "FXEC2025EC005", "ECE"),
]


def get_or_create_user(email, **fields):
    user = User.query.filter_by(email=email).first()
    if user is None:
        password = fields.pop("password", DEMO_PASSWORD)
        user = User(email=email, **fields)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    return user


def main():
    app = create_app()
    with app.app_context():
        from app import seed_domains, seed_admin_user

        seed_admin_user()
        seed_domains()
        db.session.commit()

        admin = User.query.filter_by(email="admin@elite.edu").first()
        dsa = Domain.query.filter_by(code="DSA").first()
        fullstack = Domain.query.filter_by(code="FULLSTACK").first()
        aiml = Domain.query.filter_by(code="AIML").first()

        coordinator = get_or_create_user(
            "coordinator@elite.edu",
            name="Kavitha (DSA Coordinator)",
            role="coordinator",
            approval_status="approved",
            profile_completed=True,
            department="CSE",
        )
        coordinator2 = get_or_create_user(
            "coordinator.fs@elite.edu",
            name="Manoj (Full Stack Coordinator)",
            role="coordinator",
            approval_status="approved",
            profile_completed=True,
            department="IT",
        )
        faculty = get_or_create_user(
            "faculty@elite.edu",
            name="Dr. Priya Selvam",
            role="faculty",
            approval_status="approved",
            profile_completed=True,
            department="CSE",
        )

        for user, domain in ((coordinator, dsa), (coordinator2, fullstack)):
            if not DomainAssignment.query.filter_by(
                user_id=user.id, domain_id=domain.id, assignment_type="coordinator"
            ).first():
                db.session.add(
                    DomainAssignment(user_id=user.id, domain_id=domain.id, assignment_type="coordinator", is_primary=True)
                )
        for domain in (dsa, fullstack, aiml):
            if not DomainAssignment.query.filter_by(
                user_id=faculty.id, domain_id=domain.id, assignment_type="faculty"
            ).first():
                db.session.add(DomainAssignment(user_id=faculty.id, domain_id=domain.id, assignment_type="faculty"))
        db.session.commit()

        students = []
        for name, email, reg_no, dept in STUDENTS:
            student = get_or_create_user(
                email,
                name=name,
                role="student",
                approval_status="approved",
                profile_completed=True,
                register_number=reg_no,
                department=dept,
                year=1,
                section="A",
            )
            students.append(student)
            for domain in (dsa, fullstack):
                if not StudentDomainEnrollment.query.filter_by(
                    student_id=student.id, domain_id=domain.id
                ).first():
                    db.session.add(
                        StudentDomainEnrollment(student_id=student.id, domain_id=domain.id, is_active=True)
                    )
            if students.index(student) % 2 == 0:
                if not StudentDomainEnrollment.query.filter_by(
                    student_id=student.id, domain_id=aiml.id
                ).first():
                    db.session.add(StudentDomainEnrollment(student_id=student.id, domain_id=aiml.id, is_active=True))
        db.session.commit()

        _seed_dsa_content(dsa, coordinator)
        _seed_assessments(dsa, coordinator, admin)
        _seed_tasks(admin, dsa)
        _seed_announcements(admin, dsa)
        _seed_progress(students, dsa)

        db.session.commit()
        print("Demo seed complete.")
        print("  Admin:       admin@elite.edu / Admin@1234")
        print("  Coordinator: coordinator@elite.edu / Elite@1234")
        print("  Faculty:     faculty@elite.edu / Elite@1234")
        print("  Student:     aarthi@elite.edu / Elite@1234")


def _seed_dsa_content(domain, coordinator):
    days = [
        ("Arrays and Two Pointers", "Master array traversal and the two-pointer technique.",
         "Understand indexing, sliding windows and pair-sum problems."),
        ("Strings and Hashing", "Work with strings, frequency maps and anagram problems.",
         "Apply hash maps for O(n) lookups."),
        ("Linked Lists", "Build and manipulate singly and doubly linked lists.",
         "Implement traversal, reversal and cycle detection."),
    ]
    for index, (title, description, objectives) in enumerate(days, start=1):
        day = LearningDay.query.filter_by(domain_id=domain.id, day_number=index).first()
        if day is None:
            day = LearningDay(
                domain_id=domain.id,
                day_number=index,
                title=title,
                description=description,
                learning_objectives=objectives,
                status="published",
                published_at=datetime.utcnow(),
                created_by=coordinator.id,
            )
            db.session.add(day)
            db.session.flush()
        if day.materials.count() == 0:
            db.session.add(
                LearningMaterial(
                    learning_day_id=day.id,
                    title=f"{title} — Video",
                    material_type="video",
                    description="Concept walkthrough",
                    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    duration_minutes=18,
                    display_order=1,
                    created_by=coordinator.id,
                )
            )
            db.session.add(
                LearningMaterial(
                    learning_day_id=day.id,
                    title=f"{title} — Notes (PDF)",
                    material_type="pdf",
                    description="Reference notes",
                    file_key=f"materials/dsa-day{index}-notes.pdf",
                    file_name=f"dsa-day{index}-notes.pdf",
                    file_size=248_000,
                    display_order=2,
                    created_by=coordinator.id,
                )
            )
            db.session.add(
                LearningMaterial(
                    learning_day_id=day.id,
                    title=f"{title} — Practice Problems",
                    material_type="problem",
                    description="Solve before the assessment",
                    url="https://leetcode.com/problemset/",
                    display_order=3,
                    created_by=coordinator.id,
                )
            )


def _seed_assessments(domain, coordinator, admin):
    day1 = LearningDay.query.filter_by(domain_id=domain.id, day_number=1).first()
    assessment = Assessment.query.filter_by(domain_id=domain.id, title="DSA Day 1 Quiz").first()
    if assessment is None:
        assessment = Assessment(
            domain_id=domain.id,
            learning_day_id=day1.id if day1 else None,
            title="DSA Day 1 Quiz",
            description="Quick check on arrays and two pointers.",
            assessment_type="mcq",
            total_marks=3,
            time_limit_minutes=15,
            max_attempts=2,
            status="published",
            published_at=datetime.utcnow(),
            instructions="Answer all questions. Each question is worth 1 mark.",
            created_by=coordinator.id,
        )
        db.session.add(assessment)
        db.session.flush()
        questions = [
            ("What is the time complexity of binary search on a sorted array?", ["O(n)", "O(log n)", "O(n log n)"], 1),
            ("Which technique helps find a pair summing to a target in a sorted array?", ["Two pointers", "Bubble sort", "DFS"], 0),
            ("A hash map provides average-case lookup of:", ["O(1)", "O(n)", "O(log n)"], 0),
        ]
        for index, (text, options, correct) in enumerate(questions, start=1):
            question = AssessmentQuestion(
                assessment_id=assessment.id,
                question_type="mcq",
                question_text=text,
                marks=1,
                display_order=index,
            )
            db.session.add(question)
            db.session.flush()
            for o_index, option in enumerate(options):
                db.session.add(
                    AssessmentOption(
                        question_id=question.id,
                        option_text=option,
                        is_correct=(o_index == correct),
                        display_order=o_index + 1,
                    )
                )

    betting = Assessment.query.filter_by(domain_id=domain.id, title="DSA Betting Assessment").first()
    if betting is None:
        betting = Assessment(
            domain_id=domain.id,
            title="DSA Betting Assessment",
            description="Graded betting assessment with attendance points.",
            assessment_type="betting",
            total_marks=100,
            time_limit_minutes=60,
            max_attempts=1,
            status="published",
            published_at=datetime.utcnow(),
            instructions="Attempt all questions. Attendance points apply.",
            created_by=coordinator.id,
        )
        db.session.add(betting)
        db.session.flush()
        for index in range(1, 6):
            question = AssessmentQuestion(
                assessment_id=betting.id,
                question_type="mcq",
                question_text=f"Betting question {index}",
                marks=20,
                display_order=index,
            )
            db.session.add(question)
            db.session.flush()
            for o_index, option in enumerate(["Option A", "Option B", "Option C", "Option D"]):
                db.session.add(
                    AssessmentOption(
                        question_id=question.id,
                        option_text=option,
                        is_correct=(o_index == index % 4),
                        display_order=o_index + 1,
                    )
                )

    coding = Assessment.query.filter_by(domain_id=domain.id, title="DSA Coding Challenge").first()
    if coding is None:
        coding = Assessment(
            domain_id=domain.id,
            title="DSA Coding Challenge",
            description="Implement a function and submit code for review.",
            assessment_type="coding",
            total_marks=10,
            time_limit_minutes=45,
            max_attempts=1,
            status="published",
            published_at=datetime.utcnow(),
            instructions="Choose a language and implement the solution.",
            created_by=coordinator.id,
        )
        db.session.add(coding)
        db.session.flush()
        question = AssessmentQuestion(
            assessment_id=coding.id,
            question_type="coding",
            question_text="Return the sum of all elements in the given list.",
            marks=10,
            display_order=1,
            constraints="1 <= n <= 10^5",
            sample_input="[1, 2, 3]",
            sample_output="6",
        )
        db.session.add(question)
        db.session.flush()
        db.session.add(
            TestCase(
                question_id=question.id,
                input_data="[1, 2, 3]",
                expected_output="6",
                points=5,
                is_sample=True,
                display_order=1,
            )
        )
        db.session.add(
            TestCase(
                question_id=question.id,
                input_data="[10, -5]",
                expected_output="5",
                points=5,
                is_sample=False,
                display_order=2,
            )
        )


def _seed_tasks(admin, domain):
    tasks = [
        ("Solve 3 Two-Pointer Problems", "Complete three two-pointer problems and share your solutions.", 100),
        ("Write a Blog on Hashing", "Publish a short blog explaining hash maps with examples.", 80),
        ("Build a Linked List Visualiser", "Create a small visualiser and share the repository link.", 120),
    ]
    for title, description, points in tasks:
        if EliteTask.query.filter_by(title=title).first() is None:
            db.session.add(
                EliteTask(
                    title=title,
                    description=description,
                    instructions="Submit evidence (PDF, image or link) before 11:59 PM IST.",
                    domain_id=domain.id,
                    category="general",
                    potential_points=points,
                    allowed_evidence_formats=["pdf", "image", "zip", "link"],
                    status="active",
                    due_date=datetime.utcnow() + timedelta(days=7),
                    publish_at=datetime.utcnow() - timedelta(days=1),
                    created_by=admin.id,
                )
            )


def _seed_announcements(admin, domain):
    items = [
        ("Elite Batch Orientation", "Welcome to the Elite Portal. Complete your domain selection this week.", "general", "all"),
        ("DSA Week 1 Published", "Learning days 1–3 are now available for all students.", "academic", "students"),
    ]
    for title, content, category, audience in items:
        if Announcement.query.filter_by(title=title).first() is None:
            db.session.add(
                Announcement(
                    title=title,
                    content=content,
                    category=category,
                    target_audience=audience,
                    status="published",
                    publish_at=datetime.utcnow() - timedelta(days=1),
                    created_by=admin.id,
                )
            )


def _seed_progress(students, domain):
    day1 = LearningDay.query.filter_by(domain_id=domain.id, day_number=1).first()
    if day1 is None:
        return
    for index, student in enumerate(students):
        if index > 2:
            continue
        completion = ContentCompletion.query.filter_by(
            student_id=student.id, learning_day_id=day1.id
        ).first()
        if completion is None:
            db.session.add(
                ContentCompletion(
                    student_id=student.id,
                    learning_day_id=day1.id,
                    is_day_complete=True,
                    completed_at=datetime.utcnow(),
                    videos_watched=["1"],
                )
            )
        if not PointLedger.query.filter_by(
            student_id=student.id, transaction_type="bonus", reference_type="DemoSeed", reference_id=student.id
        ).first():
            db.session.add(
                PointLedger(
                    student_id=student.id,
                    points=200 - index * 40,
                    transaction_type="bonus",
                    reference_type="DemoSeed",
                    reference_id=student.id,
                    domain_id=domain.id,
                    description="Welcome bonus",
                    created_by=student.id,
                )
            )


if __name__ == "__main__":
    main()
