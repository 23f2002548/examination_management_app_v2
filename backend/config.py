"""Application configuration. Imported by backend/__init__.py."""
import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + str(BACKEND_DIR / 'examination_portal.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_COOKIE_SAMESITE = 'Strict'
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_KEY_PREFIX = 'emp:'
    CACHE_DEFAULT_TIMEOUT = 120
    APP_TIMEZONE = os.environ.get('APP_TIMEZONE', 'Asia/Kolkata')
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    MAIL_HOST = os.environ.get('MAIL_HOST', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '1025'))
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_TLS = os.environ.get('MAIL_TLS', 'false').lower() == 'true'
    MAIL_FROM = os.environ.get('MAIL_FROM', 'exams@localhost')
    MAX_CONTENT_LENGTH = 1024 * 1024
