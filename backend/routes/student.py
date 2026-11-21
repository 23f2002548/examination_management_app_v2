from uuid import uuid4
from flask import Blueprint, jsonify, request, g, current_app, Response
from backend.models import db, Examination, Slot, Booking, ExportJob, utcnow
from backend.routes.auth import roles, user_data
from backend.common import payload, require, string, iso, local_now
from backend.services import *

student_bp=Blueprint('student',__name__)

def visible_exams():
    rows=exam_list()
    return [e for e in rows if not e['archived'] and e['course_status']=='active' and e['status']!='draft']

def student_bookings():
    return Booking.query.filter_by(student_id=g.user.student.id).order_by(Booking.id.desc()).all()

def available_slots():
    open_ids={e.id for e in Examination.query.all() if booking_open(e)}
    return [s for s in schedule_list() if s['examination_id'] in open_ids and s['status']=='available'
        and s['available_seats']>0 and datetime.fromisoformat(s['date']+'T'+s['start_time'])>local_now()
        and get(Slot,s['id']).examiner.user.active]

@student_bp.get('/dashboard')
@roles('student')
def dashboard():
    rows=student_bookings()
    return jsonify(available_examinations=visible_exams(),available_slots=available_slots(),
        upcoming_examinations=[booking_data(b,True) for b in rows if b.status=='booked' and slot_future(b.slot)],
        booked_slots=[booking_data(b,True) for b in rows if b.status=='booked'],
        published_results=[booking_data(b,True) for b in rows if b.evaluation and b.evaluation.published_at])

@student_bp.get('/examinations')
@roles('student')
def examinations():
    rows=search_rows(visible_exams(),request.args.get('q',''),['examination_name','course_name','course_code'])
    for field in ('examination_type','course_id','status'):
        if request.args.get(field): rows=[r for r in rows if str(r[field])==request.args[field]]
    return jsonify(rows)

@student_bp.get('/slots')
@roles('student')
def slots():
    rows=available_slots()
    if request.args.get('examination_id'): rows=[r for r in rows if str(r['examination_id'])==request.args['examination_id']]
    if request.args.get('date_from'): rows=[r for r in rows if r['date']>=request.args['date_from']]
    if request.args.get('date_to'): rows=[r for r in rows if r['date']<=request.args['date_to']]
    return jsonify(rows)

@student_bp.route('/bookings',methods=['GET','POST'])
@roles('student')
def bookings():
    if request.method=='GET': return jsonify([booking_data(b,True) for b in student_bookings()])
    s=get(Slot,payload().get('slot_id')); e=s.examination
    require(booking_open(e),'Student booking period is closed')
    require(s.examiner.user.active and slot_future(s) and s.status=='available' and s.available_seats>0,'Slot is unavailable or full',409)
    require(not Booking.query.filter(Booking.student_id==g.user.student.id,Booking.examination_id==e.id,Booking.status!='cancelled').first(),
        'You already have an active or completed booking for this examination',409)
    b=Booking(student_id=g.user.student.id,examination_id=e.id,slot_id=s.id)
    db.session.add(b); db.session.flush()
    db.session.expire(s,['bookings']); sync_slot(s)
    e.booking_started=True; audit(b,'booked',slot_id=s.id)
    db.session.commit()
    return jsonify(message='Slot booked successfully',booking_id=b.id),201

@student_bp.post('/bookings/<int:key>/cancel')
@roles('student')
def cancel(key):
    b=get(Booking,key)
    require(b.student_id==g.user.student.id,'This booking belongs to another student',403)
    require(b.status=='booked' and not b.evaluation,'Booking cannot be cancelled',409)
    require(utcnow()<b.slot.examination.slot_booking_end and slot_future(b.slot),'Cancellation deadline has passed')
    b.status='cancelled'; sync_slot(b.slot); audit(b,'cancelled')
    db.session.commit()
    return jsonify(message='Booking cancelled')

@student_bp.get('/history')
@roles('student')
def history():
    return jsonify([booking_data(b,True) for b in student_bookings()])

@student_bp.get('/results')
@roles('student')
def results():
    return jsonify([booking_data(b,True) for b in student_bookings() if b.evaluation and b.evaluation.published_at])

@student_bp.route('/profile',methods=['GET','PUT'])
@roles('student')
def profile():
    u=g.user; p=u.student
    if request.method=='PUT':
        d=payload(); u.name=string(d,'name',100)
        email=string(d,'email',120).lower()
        require('@' in email and '.' in email.rsplit('@',1)[-1],'Invalid email')
        u.email=email; p.contact_details=string(d,'contact_details',200,False)
        db.session.commit()
    return jsonify(**user_data(u),student_id=p.student_id,contact_details=p.contact_details)

@student_bp.post('/exports')
@roles('student')
def export():
    job=ExportJob(id=str(uuid4()),student_id=g.user.student.id)
    db.session.add(job); db.session.commit()
    from backend.tasks import export_exam_history_csv
    try:
        export_exam_history_csv.apply_async(args=[job.id],task_id=job.id)
    except Exception:
        current_app.logger.exception('Could not enqueue CSV export')
        job.status='failed'; job.error='History export is temporarily unavailable. Please try again later.'
        db.session.commit()
        return jsonify(error=job.error),503
    return jsonify(id=job.id,status=job.status),202

@student_bp.get('/exports')
@roles('student')
def exports():
    return jsonify([dict(id=j.id,status=j.status,error=j.error,created_at=iso(j.created_at)) for j in
        ExportJob.query.filter_by(student_id=g.user.student.id).order_by(ExportJob.created_at.desc()).limit(20)])

@student_bp.get('/exports/<key>')
@roles('student')
def export_status(key):
    j=db.session.get(ExportJob,key)
    require(j and j.student_id==g.user.student.id,'Export not found',404)
    return jsonify(id=j.id,status=j.status,error=j.error)

@student_bp.get('/exports/<key>/download')
@roles('student')
def download(key):
    j=db.session.get(ExportJob,key)
    require(j and j.student_id==g.user.student.id,'Export not found',404)
    require(j.status=='completed','Export is not ready',409)
    return Response(j.csv_content,mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=examination-history.csv'})
