"""SQLite models; historic bookings and evaluations are retained."""
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()
role_admin, role_examiner, role_student = 'admin', 'examiner', 'student'

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    token_version = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    examiner = db.relationship('Examiner', backref='user', uselist=False)
    student = db.relationship('Student', backref='user', uselist=False)
    __table_args__ = (db.CheckConstraint("role IN ('admin','examiner','student')"),
        db.Index('one_admin', 'role', unique=True, sqlite_where=text("role = 'admin'")))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Examiner(db.Model):
    __tablename__ = 'examiners'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    department = db.Column(db.String(100), default='')
    contact_details = db.Column(db.String(200), default='')
    slots = db.relationship('Slot', backref='examiner')

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    contact_details = db.Column(db.String(200), default='')
    bookings = db.relationship('Booking', backref='student')

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(50), unique=True, nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='active', nullable=False)
    examinations = db.relationship('Examination', backref='course')

assignments = db.Table('examination_examiners',
    db.Column('examination_id', db.Integer, db.ForeignKey('examinations.id'), primary_key=True),
    db.Column('examiner_id', db.Integer, db.ForeignKey('examiners.id'), primary_key=True))

class Examination(db.Model):
    __tablename__ = 'examinations'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    examination_name = db.Column(db.String(100), nullable=False)
    examination_type = db.Column(db.String(30), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    maximum_marks = db.Column(db.Float, nullable=False)
    slot_creation_start = db.Column(db.DateTime, nullable=False)
    slot_creation_end = db.Column(db.DateTime, nullable=False)
    slot_booking_start = db.Column(db.DateTime, nullable=False)
    slot_booking_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='draft', nullable=False)
    instructions = db.Column(db.Text, default='')
    booking_started = db.Column(db.Boolean, default=False, nullable=False)
    archived = db.Column(db.Boolean, default=False, nullable=False)
    examiners = db.relationship('Examiner', secondary=assignments, backref='examinations')
    rubrics = db.relationship('Rubric', backref='examination', order_by='Rubric.id')
    slots = db.relationship('Slot', backref='examination')

class Rubric(db.Model):
    __tablename__ = 'rubrics'
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id'), nullable=False)
    criterion_name = db.Column(db.String(100), nullable=False)
    maximum_marks = db.Column(db.Float, nullable=False)
    weightage = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, default='')

class Slot(db.Model):
    __tablename__ = 'slots'
    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id'), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('examiners.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_student_capacity = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='available', nullable=False)
    meeting_link = db.Column(db.String(500), default='')
    bookings = db.relationship('Booking', backref='slot')
    __table_args__ = (db.CheckConstraint('max_student_capacity > 0'),
        db.CheckConstraint('available_seats >= 0 AND available_seats <= max_student_capacity'))

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    examination_id = db.Column(db.Integer, db.ForeignKey('examinations.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('slots.id'), nullable=False)
    booking_date = db.Column(db.DateTime, default=utcnow, nullable=False)
    status = db.Column(db.String(20), default='booked', nullable=False)
    evaluation = db.relationship('Evaluation', backref='booking', uselist=False)
    events = db.relationship('BookingEvent', backref='booking', order_by='BookingEvent.id')
    __table_args__ = (db.Index('one_active_booking_per_exam', 'student_id', 'examination_id',
        unique=True, sqlite_where=text("status != 'cancelled'")),)

class Evaluation(db.Model):
    __tablename__ = 'evaluations'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), unique=True, nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey('examiners.id'), nullable=False)
    total_marks = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text, default='')
    scores = db.Column(db.JSON, nullable=False)
    evaluation_date = db.Column(db.DateTime, default=utcnow, nullable=False)
    status = db.Column(db.String(20), default='submitted', nullable=False)
    published_at = db.Column(db.DateTime)

class BookingEvent(db.Model):
    __tablename__ = 'booking_events'
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    details = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

class ExportJob(db.Model):
    __tablename__ = 'export_jobs'
    id = db.Column(db.String(36), primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    status = db.Column(db.String(20), default='queued', nullable=False)
    csv_content = db.Column(db.Text)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    completed_at = db.Column(db.DateTime)
