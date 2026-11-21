from flask import Blueprint, jsonify, request, g
from backend.models import db, Examination, Slot, Booking, Evaluation, utcnow
from backend.routes.auth import roles
from backend.common import payload, require, string, number
from backend.services import *

examiner_bp=Blueprint('examiner',__name__)

def owned_slot(key):
    s=get(Slot,key)
    require(s.examiner_id==g.user.examiner.id,'This slot belongs to another examiner',403)
    return s

@examiner_bp.get('/dashboard')
@roles('examiner')
def dashboard():
    profile=g.user.examiner
    bookings=Booking.query.join(Slot).filter(Slot.examiner_id==profile.id).all()
    return jsonify(stats=dict(assigned_examinations=len(profile.examinations),created_slots=len(profile.slots),
        booked_students=sum(b.status!='cancelled' for b in bookings),
        pending_evaluations=sum(b.status=='booked' and not b.evaluation for b in bookings)),
        pending_evaluations=[booking_data(b) for b in bookings if b.status=='booked'])

@examiner_bp.get('/examinations')
@roles('examiner')
def examinations():
    return jsonify([e for e in exam_list() if g.user.examiner.id in e['examiner_ids']])

@examiner_bp.get('/examinations/<int:key>/rubrics')
@roles('examiner')
def rubrics(key):
    e=get(Examination,key)
    require(g.user.examiner in e.examiners,'Examination not assigned',403)
    return jsonify(rubric_list(key))

@examiner_bp.route('/slots',methods=['GET','POST'])
@roles('examiner')
def slots():
    if request.method=='GET':
        return jsonify([s for s in schedule_list() if s['examiner_id']==g.user.examiner.id])
    d=payload(); exam=get(Examination,d.get('examination_id'))
    require(g.user.examiner in exam.examiners,'Examination not assigned',403)
    require(not exam.archived and exam.course.status=='active' and exam.status=='slot_creation'
        and exam.slot_creation_start<=utcnow()<=exam.slot_creation_end,'Slot creation period is closed')
    values=validate_slot(d,exam,g.user.examiner.id)
    s=Slot(examination_id=exam.id,examiner_id=g.user.examiner.id,available_seats=values['max_student_capacity'],**values)
    db.session.add(s); db.session.commit()
    return jsonify(slot_data(s)),201

@examiner_bp.route('/slots/<int:key>',methods=['PUT','DELETE'])
@roles('examiner')
def slot_detail(key):
    s=owned_slot(key); slot_editable(s.examination)
    if request.method=='DELETE':
        require(not s.bookings,'Slot has booking history and cannot be removed',409)
        db.session.delete(s)
    else:
        values=validate_slot(payload(),s.examination,s.examiner_id,s)
        for k,v in values.items(): setattr(s,k,v)
        sync_slot(s)
    db.session.commit()
    return jsonify(message='Slot saved')

@examiner_bp.get('/bookings')
@roles('examiner')
def bookings():
    rows=Booking.query.join(Slot).filter(Slot.examiner_id==g.user.examiner.id).all()
    return jsonify([booking_data(b) for b in rows])

@examiner_bp.post('/evaluate/<int:key>')
@roles('examiner')
def evaluate(key):
    b=get(Booking,key); owned_slot(b.slot_id)
    require(b.status=='booked' and not b.evaluation,'Booking is cancelled, completed, or already evaluated',409)
    require(not slot_future(b.slot),'Cannot evaluate before the examination begins')
    exam=b.slot.examination; validate_rubric_total(exam)
    d=payload(); scores=d.get('scores')
    require(isinstance(scores,list) and len(scores)==len(exam.rubrics),'Supply one score for every rubric criterion')
    by_id={}
    for score in scores:
        require(isinstance(score,dict),'Invalid criterion score')
        key=number(score,'rubric_id',1,True)
        require(key not in by_id,'Duplicate rubric criterion')
        by_id[key]=number(score,'marks',0)
    require(set(by_id)=={r.id for r in exam.rubrics},'Rubric criteria do not match this examination')
    snapshot=[]; total=0
    for r in exam.rubrics:
        mark=by_id[r.id]
        require(mark<=r.maximum_marks,f'Marks exceed maximum for {r.criterion_name}')
        total+=mark/r.maximum_marks*r.weightage/100*exam.maximum_marks
        snapshot.append(dict(rubric_id=r.id,criterion_name=r.criterion_name,maximum_marks=r.maximum_marks,weightage=r.weightage,marks=mark))
    e=Evaluation(booking_id=b.id,examiner_id=g.user.examiner.id,total_marks=round(total,2),scores=snapshot,remarks=string(d,'remarks',5000,False))
    db.session.add(e); audit(b,'evaluated',total_marks=e.total_marks)
    db.session.commit()
    return jsonify(message='Evaluation submitted. Mark the booking completed next.'),201

@examiner_bp.post('/complete-examination')
@roles('examiner')
def complete():
    b=get(Booking,payload().get('booking_id')); s=owned_slot(b.slot_id)
    require(b.status=='booked' and b.evaluation,'Submit an evaluation for this active booking first')
    b.status='completed'; b.evaluation.status='completed'
    sync_slot(s); audit(b,'completed')
    all_bookings=Booking.query.filter_by(examination_id=b.examination_id).all()
    if all(x.status in ('completed','cancelled') for x in all_bookings) and utcnow()>s.examination.slot_booking_end:
        s.examination.status='completed'
    db.session.commit()
    return jsonify(message='Booking completed; results await Admin publication')
