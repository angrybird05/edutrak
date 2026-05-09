"""
Identity Module — User profiles, Student records, Parent-student linking.

Public API:
    - router: FastAPI router for identity endpoints
    - Student, parent_student: Identity models
"""
from app.modules.identity.endpoints import router  # noqa
from app.modules.identity.models import Student, parent_student  # noqa
