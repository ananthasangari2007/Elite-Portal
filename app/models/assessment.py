from datetime import datetime

from app import db


class Assessment(db.Model):
    """An assessment linked to a learning day."""
    __tablename__ = "assessment"

    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=False, index=True)
    learning_day_id = db.Column(db.Integer, db.ForeignKey("learning_day.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    assessment_type = db.Column(db.String(30), nullable=False, index=True)
    # Types: mcq | coding | betting
    total_marks = db.Column(db.Integer, default=0, nullable=False)
    time_limit_minutes = db.Column(db.Integer)
    max_attempts = db.Column(db.Integer, default=1, nullable=False)
    shuffle_options = db.Column(db.Boolean, default=False, nullable=False)
    shuffle_questions = db.Column(db.Boolean, default=False, nullable=False)
    show_results_after = db.Column(db.String(30), default="submission")
    # Options: submission | grading | never
    show_correct_answers = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    # Statuses: draft | published | scheduled | closed
    scheduled_start = db.Column(db.DateTime)
    scheduled_end = db.Column(db.DateTime)
    instructions = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    domain = db.relationship("Domain", back_populates="assessments")
    learning_day = db.relationship("LearningDay", back_populates="assessments")
    questions = db.relationship("AssessmentQuestion", back_populates="assessment",
                                order_by="AssessmentQuestion.display_order", cascade="all, delete-orphan")
    attempts = db.relationship("AssessmentAttempt", back_populates="assessment", lazy="dynamic")
    creator = db.relationship("User", foreign_keys=[created_by])

    @property
    def is_available(self):
        if self.status != "published":
            return False
        now = datetime.utcnow()
        if self.scheduled_start and now < self.scheduled_start:
            return False
        if self.scheduled_end and now > self.scheduled_end:
            return False
        return True

    @property
    def question_count(self):
        return len(self.questions)


class AssessmentQuestion(db.Model):
    """A question within an assessment."""
    __tablename__ = "assessment_question"

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessment.id"), nullable=False, index=True)
    question_type = db.Column(db.String(30), nullable=False)
    # Types: mcq | coding
    question_text = db.Column(db.Text, nullable=False)
    marks = db.Column(db.Integer, default=1, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    # For coding questions
    constraints = db.Column(db.Text)
    sample_input = db.Column(db.Text)
    sample_output = db.Column(db.Text)
    explanation = db.Column(db.Text)
    # For MCQ: correct option stored server-side
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assessment = db.relationship("Assessment", back_populates="questions")
    options = db.relationship("AssessmentOption", back_populates="question",
                              order_by="AssessmentOption.display_order", cascade="all, delete-orphan")
    test_cases = db.relationship("TestCase", back_populates="question", cascade="all, delete-orphan")


class AssessmentOption(db.Model):
    """An answer option for an MCQ question."""
    __tablename__ = "assessment_option"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("assessment_question.id"), nullable=False, index=True)
    option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)

    question = db.relationship("AssessmentQuestion", back_populates="options")


class TestCase(db.Model):
    """A test case for a coding question."""
    __tablename__ = "test_case"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("assessment_question.id"), nullable=False, index=True)
    input_data = db.Column(db.Text)
    expected_output = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, default=0, nullable=False)
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    # is_sample=True → shown to student; False → hidden
    display_order = db.Column(db.Integer, default=0, nullable=False)

    question = db.relationship("AssessmentQuestion", back_populates="test_cases")


class AssessmentAttempt(db.Model):
    """A student's attempt at an assessment."""
    __tablename__ = "assessment_attempt"

    id = db.Column(db.Integer, primary_key=True)
    assessment_id = db.Column(db.Integer, db.ForeignKey("assessment.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    status = db.Column(db.String(30), default="in_progress", nullable=False, index=True)
    # Statuses: in_progress | submitted | graded | absent
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = db.Column(db.DateTime)
    graded_at = db.Column(db.DateTime)
    graded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    score = db.Column(db.Integer)
    total_marks = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    time_taken_seconds = db.Column(db.Integer)
    # Attendance and betting fields
    attended = db.Column(db.Boolean, default=True, nullable=False)
    locked_points = db.Column(db.Integer, default=0)
    attendance_points = db.Column(db.Integer, default=0)
    total_points_awarded = db.Column(db.Integer, default=0)
    points_rule_applied = db.Column(db.String(100))
    points_override_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    points_override_reason = db.Column(db.Text)
    # Integrity flags
    integrity_flags = db.Column(db.JSON, default=list)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assessment = db.relationship("Assessment", back_populates="attempts")
    student = db.relationship("User", back_populates="assessment_attempts", foreign_keys=[student_id])
    grader = db.relationship("User", foreign_keys=[graded_by])
    answers = db.relationship("AssessmentAnswer", back_populates="attempt",
                              cascade="all, delete-orphan")
    coding_submissions = db.relationship("CodingSubmission", back_populates="attempt",
                                         cascade="all, delete-orphan")

    __table_args__ = (
        db.Index("ix_attempt_assessment_student", "assessment_id", "student_id"),
    )


class AssessmentAnswer(db.Model):
    """A student's saved answer to an MCQ question."""
    __tablename__ = "assessment_answer"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("assessment_attempt.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("assessment_question.id"), nullable=False, index=True)
    selected_option_id = db.Column(db.Integer, db.ForeignKey("assessment_option.id"))
    marked_for_review = db.Column(db.Boolean, default=False, nullable=False)
    is_correct = db.Column(db.Boolean)
    marks_awarded = db.Column(db.Integer, default=0)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attempt = db.relationship("AssessmentAttempt", back_populates="answers")
    question = db.relationship("AssessmentQuestion")
    selected_option = db.relationship("AssessmentOption")

    __table_args__ = (
        db.UniqueConstraint("attempt_id", "question_id", name="uq_attempt_answer"),
    )


class CodingSubmission(db.Model):
    """A student's code submission for a coding question."""
    __tablename__ = "coding_submission"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("assessment_attempt.id"), nullable=False, index=True)
    question_id = db.Column(db.Integer, db.ForeignKey("assessment_question.id"), nullable=False, index=True)
    language = db.Column(db.String(30), nullable=False)
    code = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="pending")
    # pending | running | passed | failed | error
    test_results = db.Column(db.JSON, default=list)
    marks_awarded = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    attempt = db.relationship("AssessmentAttempt", back_populates="coding_submissions")
    question = db.relationship("AssessmentQuestion")
