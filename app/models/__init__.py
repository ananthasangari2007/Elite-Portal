"""
Elite Portal — Models Package
All models are imported here for SQLAlchemy discovery and Flask-Migrate.
"""

# Legacy models (retained for backward compatibility)
from app.models.user import User, PasswordResetToken
from app.models.task import Task
from app.models.point_transaction import PointTransaction
from app.models.point_rule import PointRule
from app.models.submission import Submission
from app.models.support_message import SupportMessage
from app.models.elite_sprint import EliteSprintBid, EliteSprintSession

# New Elite Portal models
from app.models.domain import (
    Domain,
    DomainAssignment,
    StudentDomainEnrollment,
    LearningDay,
    LearningMaterial,
    ContentCompletion,
)
from app.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentOption,
    TestCase,
    AssessmentAttempt,
    AssessmentAnswer,
    CodingSubmission,
)
from app.models.platform import (
    EliteTask,
    TaskEvidence,
    PointLedger,
    PointAdjustmentRequest,
    Appeal,
    StudentRequest,
    RequestMessage,
    Announcement,
    Notification,
    AuditLog,
    SystemSetting,
    GradingHistory,
)

__all__ = [
    "User", "PasswordResetToken",
    "Task", "PointTransaction", "PointRule", "Submission",
    "SupportMessage", "EliteSprintBid", "EliteSprintSession",
    "Domain", "DomainAssignment", "StudentDomainEnrollment",
    "LearningDay", "LearningMaterial", "ContentCompletion",
    "Assessment", "AssessmentQuestion", "AssessmentOption",
    "TestCase", "AssessmentAttempt", "AssessmentAnswer", "CodingSubmission",
    "EliteTask", "TaskEvidence", "PointLedger", "PointAdjustmentRequest",
    "Appeal", "StudentRequest", "RequestMessage",
    "Announcement", "Notification", "AuditLog", "SystemSetting",
    "GradingHistory",
]
