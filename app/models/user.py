import secrets
from datetime import datetime, timedelta

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True, index=True)
    role = db.Column(db.String(30), nullable=False, index=True)
    # Roles: student | coordinator | faculty | admin
    approval_status = db.Column(db.String(30), default="approved", nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    has_active_sprint_penalty = db.Column(db.Boolean, default=False, nullable=False, index=True)
    profile_completed = db.Column(db.Boolean, default=False, nullable=False)
    register_number = db.Column(db.String(80), index=True)
    phone_number = db.Column(db.String(30))
    department = db.Column(db.String(120), index=True)
    year = db.Column(db.Integer)
    section = db.Column(db.String(10))
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    leetcode_url = db.Column(db.String(500))
    preferred_domain = db.Column(db.String(120))
    avatar_url = db.Column(db.String(500))
    bio = db.Column(db.Text)
    # Password reset
    reset_token = db.Column(db.String(100), index=True)
    reset_token_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)

    # Relationships
    domain_enrollments = db.relationship(
        "StudentDomainEnrollment", back_populates="student",
        foreign_keys="StudentDomainEnrollment.student_id", lazy="dynamic"
    )
    content_completions = db.relationship("ContentCompletion", back_populates="student", lazy="dynamic")
    assessment_attempts = db.relationship(
        "AssessmentAttempt", back_populates="student",
        foreign_keys="AssessmentAttempt.student_id", lazy="dynamic"
    )
    point_ledger_entries = db.relationship("PointLedger", back_populates="student",
                                           foreign_keys="PointLedger.student_id", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic")
    sent_requests = db.relationship("StudentRequest", back_populates="student",
                                    foreign_keys="StudentRequest.student_id", lazy="dynamic")

    @property
    def is_active(self):
        return self.is_active_account

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    def verify_reset_token(self, token):
        if not self.reset_token or self.reset_token != token:
            return False
        if not self.reset_token_expires or datetime.utcnow() > self.reset_token_expires:
            return False
        return True

    def clear_reset_token(self):
        self.reset_token = None
        self.reset_token_expires = None

    def total_points(self):
        from sqlalchemy import func
        from app import db
        result = db.session.query(func.coalesce(func.sum(PointLedger.points), 0)).filter(
            PointLedger.student_id == self.id
        ).scalar()
        return int(result or 0)

    def __repr__(self):
        return f"<User {self.email} [{self.role}]>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class PasswordResetToken(db.Model):
    """Separate single-use password reset tokens."""
    __tablename__ = "password_reset_token"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref="reset_tokens")

    @classmethod
    def generate(cls, user_id):
        token = secrets.token_urlsafe(40)
        expires = datetime.utcnow() + timedelta(hours=1)
        return cls(user_id=user_id, token=token, expires_at=expires)

    @property
    def is_valid(self):
        return not self.used and datetime.utcnow() < self.expires_at
