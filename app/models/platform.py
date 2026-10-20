from datetime import datetime

from app import db


class EliteTask(db.Model):
    """An Elite Task (daily challenge with evidence submission)."""
    __tablename__ = "elite_task"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    instructions = db.Column(db.Text)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), index=True)
    # None = all domains
    category = db.Column(db.String(50), default="general")
    # general | problem_solving | technical_writing | web_dev | etc
    potential_points = db.Column(db.Integer, nullable=False, default=100)
    allowed_evidence_formats = db.Column(db.JSON, default=list)
    # ["pdf", "image", "zip", "link"]
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    # draft | active | upcoming | completed
    due_date = db.Column(db.DateTime)
    publish_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    domain = db.relationship("Domain", backref="elite_tasks")
    creator = db.relationship("User", foreign_keys=[created_by])
    evidences = db.relationship("TaskEvidence", back_populates="task", lazy="dynamic")

    @property
    def is_available(self):
        if self.status != "active":
            return False
        if self.publish_at and datetime.utcnow() < self.publish_at:
            return False
        if self.due_date and datetime.utcnow() > self.due_date:
            return False
        return True


class TaskEvidence(db.Model):
    """Evidence submitted by a student for an Elite Task."""
    __tablename__ = "task_evidence"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("elite_task.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    evidence_type = db.Column(db.String(30), nullable=False)
    # file | link
    file_key = db.Column(db.String(500))  # R2 key
    file_name = db.Column(db.String(200))
    file_size = db.Column(db.BigInteger)
    file_type = db.Column(db.String(50))
    link_url = db.Column(db.String(1000))
    notes = db.Column(db.Text)
    submission_date = db.Column(db.Date, nullable=False)  # business day (Asia/Kolkata)
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    # pending | approved | rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_at = db.Column(db.DateTime)
    reviewer_feedback = db.Column(db.Text)
    points_awarded = db.Column(db.Integer, default=0, nullable=False)
    point_ledger_id = db.Column(db.Integer, db.ForeignKey("point_ledger.id"))
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    task = db.relationship("EliteTask", back_populates="evidences")
    student = db.relationship("User", foreign_keys=[student_id], backref="task_evidences")
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])
    point_ledger_entry = db.relationship("PointLedger", foreign_keys=[point_ledger_id])

    __table_args__ = (
        db.UniqueConstraint("student_id", "submission_date",
                            name="uq_daily_task_evidence"),
        # One submission per student per business day
    )


class PointLedger(db.Model):
    """Immutable audit trail of all point transactions."""
    __tablename__ = "point_ledger"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    points = db.Column(db.Integer, nullable=False)
    # Positive = award; Negative = deduction
    transaction_type = db.Column(db.String(50), nullable=False, index=True)
    # types: task_approval | assessment | betting_assessment | adjustment | penalty | bonus
    reference_type = db.Column(db.String(50))
    # The model this relates to: TaskEvidence | AssessmentAttempt | Appeal | etc
    reference_id = db.Column(db.Integer)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), index=True)
    description = db.Column(db.String(300))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # For overrides
    is_override = db.Column(db.Boolean, default=False, nullable=False)
    override_reason = db.Column(db.Text)
    is_reversed = db.Column(db.Boolean, default=False, nullable=False)
    reversed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reversed_at = db.Column(db.DateTime)

    student = db.relationship("User", back_populates="point_ledger_entries",
                              foreign_keys=[student_id])
    domain = db.relationship("Domain", backref="point_ledger_entries")
    created_by_user = db.relationship("User", foreign_keys=[created_by])


class PointAdjustmentRequest(db.Model):
    """A request to adjust a student's points."""
    __tablename__ = "point_adjustment_request"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    request_type = db.Column(db.String(50), nullable=False)
    # types: assessment_correction | task_recount | bonus | penalty_reversal | other
    current_points = db.Column(db.Integer, nullable=False)
    requested_points = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(30), default="pending", nullable=False, index=True)
    # pending | approved | rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    review_notes = db.Column(db.Text)
    reviewed_at = db.Column(db.DateTime)
    point_ledger_id = db.Column(db.Integer, db.ForeignKey("point_ledger.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("User", foreign_keys=[student_id], backref="point_adjustment_requests")
    requester = db.relationship("User", foreign_keys=[requested_by])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by])


class Appeal(db.Model):
    """A grade appeal submitted by a student."""
    __tablename__ = "appeal"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("assessment_attempt.id"), index=True)
    evidence_id = db.Column(db.Integer, db.ForeignKey("task_evidence.id"), index=True)
    original_score = db.Column(db.Integer)
    reason = db.Column(db.Text, nullable=False)
    supporting_info = db.Column(db.Text)
    status = db.Column(db.String(30), default="open", nullable=False, index=True)
    # open | in_review | resolved | rejected
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"))
    review_comments = db.Column(db.Text)
    decision = db.Column(db.String(30))
    # upheld | overturned | partial
    new_score = db.Column(db.Integer)
    resolved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student = db.relationship("User", foreign_keys=[student_id], backref="appeals")
    attempt = db.relationship("AssessmentAttempt", backref="appeals")
    assigned_reviewer = db.relationship("User", foreign_keys=[assigned_to])
    resolver = db.relationship("User", foreign_keys=[resolved_by])


class StudentRequest(db.Model):
    """A private support request from a student."""
    __tablename__ = "student_request"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    category = db.Column(db.String(50), nullable=False)
    # assessment_reeval | content_access | technical | point_discrepancy | general
    subject = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(30), default="open", nullable=False, index=True)
    # open | in_progress | resolved | closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    student = db.relationship("User", back_populates="sent_requests", foreign_keys=[student_id])
    handler = db.relationship("User", foreign_keys=[assigned_to])
    messages = db.relationship("RequestMessage", back_populates="request",
                               order_by="RequestMessage.created_at", cascade="all, delete-orphan")


class RequestMessage(db.Model):
    """A message in a student request conversation."""
    __tablename__ = "request_message"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("student_request.id"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)
    # Internal notes only visible to staff
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    request = db.relationship("StudentRequest", back_populates="messages")
    sender = db.relationship("User", foreign_keys=[sender_id])


class GradingHistory(db.Model):
    """Immutable history of grading actions on an assessment attempt or task evidence."""
    __tablename__ = "grading_history"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("assessment_attempt.id"), index=True)
    evidence_id = db.Column(db.Integer, db.ForeignKey("task_evidence.id"), index=True)
    graded_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    # graded | updated | change_requested | betting_adjusted
    score = db.Column(db.Integer)
    previous_score = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    grader = db.relationship("User", foreign_keys=[graded_by])
    attempt = db.relationship("AssessmentAttempt", backref="grading_history")
    evidence = db.relationship("TaskEvidence", backref="grading_history")


class Announcement(db.Model):
    """A platform announcement."""
    __tablename__ = "announcement"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default="general")
    # academic | technical | events | maintenance | general
    target_audience = db.Column(db.String(50), default="all")
    # all | students | coordinators | faculty | admin
    target_domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"))
    status = db.Column(db.String(30), default="draft", nullable=False)
    # draft | published | archived
    publish_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])
    target_domain = db.relationship("Domain", backref="announcements")

    @property
    def is_active(self):
        if self.status != "published":
            return False
        now = datetime.utcnow()
        if self.publish_at and now < self.publish_at:
            return False
        if self.expires_at and now > self.expires_at:
            return False
        return True


class Notification(db.Model):
    """A notification for a specific user."""
    __tablename__ = "notification"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    notification_type = db.Column(db.String(50), default="info")
    # info | success | warning | error
    link_url = db.Column(db.String(500))
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="notifications")


class AuditLog(db.Model):
    """Immutable audit log for sensitive administrative actions."""
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    # e.g. user.create, user.deactivate, grade.override, point.adjust
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    old_value = db.Column(db.JSON)
    new_value = db.Column(db.JSON)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    actor = db.relationship("User", foreign_keys=[actor_id], backref="audit_logs")


class SystemSetting(db.Model):
    """Key-value store for system configuration."""
    __tablename__ = "system_setting"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text)
    value_type = db.Column(db.String(20), default="string")
    # string | integer | boolean | json
    description = db.Column(db.String(300))
    updated_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    updater = db.relationship("User", foreign_keys=[updated_by])
