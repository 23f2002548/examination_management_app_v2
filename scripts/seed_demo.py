"""Optional demo data in the selected SQLite database. Never overwrites existing courses."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from datetime import datetime,timedelta
from backend import create_app
from backend.models import db, User, Student, Examiner, Course, Examination, Rubric, Slot, Booking, Evaluation, utcnow
from backend.common import local_now
from backend.routes.auth import create_user

def seed():
    app=create_app()
    with app.app_context():
        if Course.query.filter_by(course_code='DEMO101').first():
            print('Demo course already exists; no data changed.'); return
        examiner=create_user(dict(email='examiner@demo.local',password='Demo12345!',name='Demo Examiner',department='Computer Science'),'examiner')
        student=create_user(dict(email='student@demo.local',password='Demo12345!',name='Demo Student',student_id='DEMO001'),'student')
        db.session.flush()
        course=Course(course_code='DEMO101',course_name='Application Development',description='Optional demo course')
        db.session.add(course); db.session.flush()
        now=utcnow(); day=local_now().date()
        for name,status in [('Project viva','booking_open'),('Practical assessment','slot_creation'),('Completed assessment','completed')]:
            e=Examination(course_id=course.id,examination_name=name,examination_type='Viva',duration=30,maximum_marks=100,
                slot_creation_start=now-timedelta(days=2),slot_creation_end=now-timedelta(days=1),
                slot_booking_start=now-timedelta(hours=1),slot_booking_end=now+timedelta(days=1),
                status=status,booking_started=status!='slot_creation',instructions='Bring your student ID and be ready to explain your code.')
            e.examiners=[examiner.examiner]
            if status=='slot_creation':
                e.slot_creation_end=now+timedelta(days=1); e.slot_booking_start=now+timedelta(days=2); e.slot_booking_end=now+timedelta(days=3)
            if status=='completed':
                e.slot_creation_start=now-timedelta(days=8); e.slot_creation_end=now-timedelta(days=7)
                e.slot_booking_start=now-timedelta(days=6); e.slot_booking_end=now-timedelta(days=5)
            db.session.add(e); db.session.flush()
            rubric=Rubric(examination_id=e.id,criterion_name='Understanding and explanation',maximum_marks=20,weightage=100,description='Explain the implementation and answer questions.')
            db.session.add(rubric); db.session.flush()
            if status=='slot_creation': continue
            s=Slot(examination_id=e.id,examiner_id=examiner.examiner.id,date=day+(timedelta(days=2) if status=='booking_open' else -timedelta(days=2)),
                start_time=datetime.strptime('10:00','%H:%M').time(),end_time=datetime.strptime('10:30','%H:%M').time(),
                max_student_capacity=3,available_seats=2,status='available' if status=='booking_open' else 'completed')
            db.session.add(s); db.session.flush()
            b=Booking(student_id=student.student.id,examination_id=e.id,slot_id=s.id,status='booked' if status=='booking_open' else 'completed')
            db.session.add(b); db.session.flush()
            if status=='completed':
                db.session.add(Evaluation(booking_id=b.id,examiner_id=examiner.examiner.id,total_marks=85,remarks='Clear explanation and strong understanding.',
                    scores=[dict(rubric_id=rubric.id,criterion_name=rubric.criterion_name,maximum_marks=20,weightage=100,marks=17)],
                    status='completed',published_at=now))
        db.session.commit()
        from backend.cache import invalidate
        invalidate()
        print('Demo accounts: examiner@demo.local and student@demo.local; password: Demo12345!')

if __name__=='__main__': seed()
