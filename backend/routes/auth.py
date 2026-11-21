from functools import wraps
from flask import Blueprint, jsonify, g
from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies, verify_jwt_in_request, get_jwt_identity, get_jwt
from backend.models import db, User, Student, Examiner
from backend.common import require, payload, string

auth_bp = Blueprint('auth', __name__)
jwt = JWTManager()

def user_data(user):
    return {'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role, 'active': user.active}

def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            verify_jwt_in_request()
            user = db.session.get(User, int(get_jwt_identity()))
            require(user and user.active and user.token_version == get_jwt().get('version'), 'Session expired; please log in', 401)
            require(not allowed or user.role in allowed, 'Access denied', 403)
            g.user = user
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def create_user(data, role):
    email = string(data, 'email', 120).lower()
    require('@' in email and '.' in email.rsplit('@', 1)[-1], 'Enter a valid email address')
    password = string(data, 'password', 128)
    require(len(password) >= 8, 'Password must contain at least 8 characters')
    require(not User.query.filter_by(email=email).first(), 'Email already registered', 409)
    user = User(email=email, name=string(data, 'name', 100), role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    if role == 'student':
        sid = string(data, 'student_id', 50)
        require(not Student.query.filter_by(student_id=sid).first(), 'Student ID already registered', 409)
        db.session.add(Student(user_id=user.id, student_id=sid, contact_details=string(data, 'contact_details', 200, False)))
    elif role == 'examiner':
        db.session.add(Examiner(user_id=user.id, department=string(data, 'department', 100), contact_details=string(data, 'contact_details', 200, False)))
    return user

@auth_bp.post('/register')
def register():
    user = create_user(payload(), 'student')
    db.session.commit()
    return jsonify(message='Registration complete. Please log in.', user=user_data(user)), 201

@auth_bp.post('/login')
def login():
    data = payload()
    user = User.query.filter_by(email=string(data, 'email', 120).lower()).first()
    require(user and user.check_password(string(data, 'password', 128)), 'Invalid email or password', 401)
    require(user.active, 'This account is inactive', 403)
    token = create_access_token(identity=str(user.id), additional_claims={'version': user.token_version})
    response = jsonify(user=user_data(user))
    set_access_cookies(response, token)
    return response

@auth_bp.get('/me')
@roles()
def me():
    return jsonify(user=user_data(g.user))

@auth_bp.post('/logout')
@roles()
def logout():
    g.user.token_version += 1
    db.session.commit()
    response = jsonify(message='Logged out')
    unset_jwt_cookies(response)
    return response
