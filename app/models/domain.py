from datetime import datetime

from app import db


class Domain(db.Model):
    """A learning domain (DSA, Full Stack, AI/ML, Embedded Systems)."""
    __tablename__ = "domain"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False, index=True)
    # Codes: DSA, FULLSTACK, AIML, EMBEDDED
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default="book")
    color = db.Column(db.String(20), default="#4f46e5")
    is_compulsory = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    enrollment_limit = db.Column(db.Integer)
    domain_change_allowed_until = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    enrollments = db.relationship("StudentDomainEnrollment", back_populates="domain", lazy="dynamic")
    learning_days = db.relationship("LearningDay", back_populates="domain",
                                    order_by="LearningDay.day_number", lazy="dynamic")
    assessments = db.relationship("Assessment", back_populates="domain", lazy="dynamic")
    assignments = db.relationship("DomainAssignment", back_populates="domain", lazy="dynamic")

    @property
    def published_days_count(self):
        return self.learning_days.filter_by(status="published").count()

    @property
    def student_count(self):
        return self.enrollments.filter_by(is_active=True).count()

    def __repr__(self):
        return f"<Domain {self.code}>"


class DomainAssignment(db.Model):
    """Assigns coordinators and faculty to domains."""
    __tablename__ = "domain_assignment"

    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    assignment_type = db.Column(db.String(30), nullable=False)
    # Types: coordinator | faculty
    is_primary = db.Column(db.Boolean, default=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    domain = db.relationship("Domain", back_populates="assignments")
    user = db.relationship("User", foreign_keys=[user_id], backref="domain_assignments")

    __table_args__ = (
        db.UniqueConstraint("domain_id", "user_id", "assignment_type",
                            name="uq_domain_assignment"),
    )


class StudentDomainEnrollment(db.Model):
    """Student enrollment in a domain."""
    __tablename__ = "student_domain_enrollment"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    enrolled_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    # If domain change was authorized
    change_authorized_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    change_authorized_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    student = db.relationship("User", back_populates="domain_enrollments",
                              foreign_keys=[student_id])
    domain = db.relationship("Domain", back_populates="enrollments")

    __table_args__ = (
        db.UniqueConstraint("student_id", "domain_id",
                            name="uq_student_domain_enrollment"),
    )


class LearningDay(db.Model):
    """A single learning day within a domain."""
    __tablename__ = "learning_day"

    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey("domain.id"), nullable=False, index=True)
    day_number = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    learning_objectives = db.Column(db.Text)
    status = db.Column(db.String(30), default="draft", nullable=False, index=True)
    # Statuses: draft | published | locked | archived
    is_locked = db.Column(db.Boolean, default=False, nullable=False)
    prerequisite_day_id = db.Column(db.Integer, db.ForeignKey("learning_day.id"))
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    domain = db.relationship("Domain", back_populates="learning_days")
    materials = db.relationship("LearningMaterial", back_populates="learning_day",
                                order_by="LearningMaterial.display_order", lazy="dynamic")
    assessments = db.relationship("Assessment", back_populates="learning_day", lazy="dynamic")
    completions = db.relationship("ContentCompletion", back_populates="learning_day", lazy="dynamic")
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint("domain_id", "day_number", name="uq_domain_day_number"),
    )

    def is_completed_by(self, student_id):
        return ContentCompletion.query.filter_by(
            student_id=student_id, learning_day_id=self.id, is_day_complete=True
        ).first() is not None


class LearningMaterial(db.Model):
    """A piece of content within a learning day."""
    __tablename__ = "learning_material"

    id = db.Column(db.Integer, primary_key=True)
    learning_day_id = db.Column(db.Integer, db.ForeignKey("learning_day.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    material_type = db.Column(db.String(30), nullable=False, index=True)
    # Types: video | pdf | code | link | problem
    description = db.Column(db.Text)
    url = db.Column(db.String(1000))
    file_key = db.Column(db.String(500))  # R2 object key
    file_size = db.Column(db.BigInteger)  # bytes
    file_name = db.Column(db.String(200))
    duration_minutes = db.Column(db.Integer)  # for videos
    display_order = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(30), default="published", nullable=False)
    tags = db.Column(db.JSON, default=list)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    learning_day = db.relationship("LearningDay", back_populates="materials")
    creator = db.relationship("User", foreign_keys=[created_by])

    @property
    def file_size_display(self):
        if not self.file_size:
            return None
        if self.file_size > 1024 * 1024:
            return f"{self.file_size / (1024*1024):.1f} MB"
        return f"{self.file_size / 1024:.0f} KB"


class ContentCompletion(db.Model):
    """Tracks student progress through learning days."""
    __tablename__ = "content_completion"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    learning_day_id = db.Column(db.Integer, db.ForeignKey("learning_day.id"), nullable=False, index=True)
    is_day_complete = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime)
    videos_watched = db.Column(db.JSON, default=list)  # list of material IDs
    notes_read = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("User", back_populates="content_completions")
    learning_day = db.relationship("LearningDay", back_populates="completions")

    __table_args__ = (
        db.UniqueConstraint("student_id", "learning_day_id", name="uq_content_completion"),
    )
