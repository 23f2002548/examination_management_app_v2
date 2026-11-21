import os
import secrets
from pathlib import Path
from datetime import timedelta
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.exceptions import HTTPException
from backend.models import db, User
from backend.routes.auth import jwt, auth_bp
from backend.cache import cache, invalidate

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent

@event.listens_for(Engine, 'connect')
def sqlite_options(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=15000')

def create_app(config=None):
    secret_path = BACKEND_DIR / '.secret'
    if not secret_path.exists():
        secret_path.write_text(secrets.token_hex(32))
    app = Flask(__name__, static_folder=None)
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', secret_path.read_text().strip()),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///' + str(BACKEND_DIR / 'examination_portal.db')),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_TOKEN_LOCATION=['cookies'], JWT_COOKIE_CSRF_PROTECT=True, JWT_COOKIE_SAMESITE='Strict',
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=8),
        CACHE_TYPE='RedisCache', CACHE_REDIS_URL=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        CACHE_KEY_PREFIX='emp:', CACHE_DEFAULT_TIMEOUT=120,
        APP_TIMEZONE=os.environ.get('APP_TIMEZONE', 'Asia/Kolkata'),
        CELERY_BROKER_URL=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        CELERY_RESULT_BACKEND=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        MAIL_HOST=os.environ.get('MAIL_HOST', 'localhost'), MAIL_PORT=int(os.environ.get('MAIL_PORT', '1025')),
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'), MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        MAIL_TLS=os.environ.get('MAIL_TLS', 'false').lower() == 'true',
        MAIL_FROM=os.environ.get('MAIL_FROM', 'exams@localhost'), MAX_CONTENT_LENGTH=1024*1024,
    )
    if config:
        app.config.update(config if isinstance(config, dict) else {k: getattr(config, k) for k in dir(config) if k.isupper()})
    if not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:'):
        raise RuntimeError('This project requires SQLite')
    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    from backend.routes.admin import admin_bp
    from backend.routes.examiner import examiner_bp
    from backend.routes.student import student_bp
    for blueprint, prefix in [(auth_bp, '/api'), (admin_bp, '/api/admin'), (examiner_bp, '/api/examiner'), (student_bp, '/api/student')]:
        app.register_blueprint(blueprint, url_prefix=prefix)

    @app.before_request
    def serialize_writes():
        if request.path.startswith('/api/') and request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            db.session.execute(text('BEGIN IMMEDIATE'))

    @app.after_request
    def finish(response):
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            if response.status_code < 400:
                invalidate()
            db.session.rollback()
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        db.session.rollback()
        return jsonify(error=error.description), error.code

    @app.errorhandler(IntegrityError)
    def conflict(error):
        db.session.rollback()
        return jsonify(error='Conflicting or referenced record. Check duplicates; archive records with history.'), 409

    @app.errorhandler(OperationalError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception('Database operation failed')
        return jsonify(error='Database is busy or unavailable. Please retry.'), 503

    @app.get('/api/health')
    def health():
        return jsonify(status='ok', timezone=app.config['APP_TIMEZONE'])

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path=''):
        if path.startswith('api/'):
            return jsonify(error='Endpoint not found'), 404
        dist = ROOT / 'frontend' / 'dist'
        if not (dist / 'index.html').exists():
            return 'Build the frontend: cd frontend && npm install && npm run build', 503
        target = (dist / path).resolve()
        if path and target.is_relative_to(dist.resolve()) and target.is_file():
            return send_from_directory(dist, path)
        return send_from_directory(dist, 'index.html')

    with app.app_context():
        db.create_all()
        if not User.query.filter_by(role='admin').first():
            admin = User(email=os.environ.get('ADMIN_EMAIL', 'admin@emp.edu'), name='System Administrator', role='admin')
            admin.set_password(os.environ.get('ADMIN_PASSWORD', 'Admin123!'))
            db.session.add(admin)
            db.session.commit()
    from backend.celery_app import make_celery
    make_celery(app)
    return app
