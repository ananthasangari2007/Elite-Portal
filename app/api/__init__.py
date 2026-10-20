"""Versioned REST API blueprint registration."""
from app import csrf


def register_api(app):
    from app.api.auth import auth_api
    from app.api.student import student_api
    from app.api.coordinator import coordinator_api
    from app.api.faculty import faculty_api
    from app.api.admin import admin_api
    from app.api.common import common_api

    blueprints = [auth_api, common_api, student_api, coordinator_api, faculty_api, admin_api]
    for bp in blueprints:
        csrf.exempt(bp)
        app.register_blueprint(bp)
    return blueprints
