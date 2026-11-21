from .auth import auth_bp, jwt, roles, create_user, user_data
from .admin import admin_bp
from .examiner import examiner_bp
from .student import student_bp

__all__ = [
    'auth_bp',
    'admin_bp',
    'examiner_bp',
    'student_bp',
    'jwt',
    'roles',
    'create_user',
    'user_data'
]
