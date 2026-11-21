from flask import Blueprint, jsonify, request
from backend.models import db, Course, Examination, Rubric, Slot, User, Examiner, Student, Booking, Evaluation, utcnow
from backend.routes.auth import roles, create_user, user_data
from backend.common import payload, require, string, number
from backend.services import *

admin_bp = Blueprint('admin', __name__)

@admin_bp.get('/dashboard')
@roles('admin')
def dashboard():
    return jsonify(stats={f'total_{name}': model.query.count() for name,model in
        [('courses',Course),('examinations',Examination),('students',Student),('examiners',Examiner),('slots',Slot),('bookings',Booking)]})

@admin_bp.route('/courses', methods=['GET','POST'])
@roles('admin')
def courses():
    if request.method == 'GET':
        return jsonify([course_data(c) for c in Course.query.all()])
    d=payload()
    c=Course(course_code=string(d,'course_code',50),course_name=string(d,'course_name',100),description=string(d,'description',3000,False))
    db.session.add(c); db.session.commit()
    return jsonify(course_data(c)),201

@admin_bp.route('/courses/<int:key>', methods=['PUT','DELETE'])
@roles('admin')
def course_detail(key):
    c=get(Course,key)
    if request.method == 'DELETE':
        require(not c.examinations, 'Course has examination history; archive it instead',409)
        db.session.delete(c)
    else:
        d=payload()
        c.course_code=string(d,'course_code',50); c.course_name=string(d,'course_name',100)
        c.description=string(d,'description',3000,False)
        require(d.get('status','active') in ('active','archived'),'Invalid course status')
        c.status=d.get('status','active')
    db.session.commit()
    return jsonify(message='Course saved')

@admin_bp.route('/examinations', methods=['GET','POST'])
@roles('admin')
def examinations():
    if request.method == 'GET':
        return jsonify(search_rows(exam_list(),request.args.get('q',''),['examination_name','course_name','examination_type']))
    d=payload()
    e=Examination(**validate_exam(d))
    e.examiners=assigned_examiners(d.get('examiner_ids',[]))
    db.session.add(e); db.session.commit()
    return jsonify(exam_data(e)),201

def assigned_examiners(ids):
    require(isinstance(ids,list),'examiner_ids must be a list')
    require(all(isinstance(i,(str,int)) and str(i).isdigit() and int(i)>0 for i in ids),'Invalid examiner IDs')
    result=[get(Examiner,i) for i in set(map(int,ids))]
    require(all(e.user.active for e in result),'Choose active examiners')
    return result

@admin_bp.route('/examinations/<int:key>', methods=['GET','PUT','DELETE'])
@roles('admin')
def examination_detail(key):
    e=get(Examination,key)
    if request.method == 'GET':
        return jsonify(**exam_data(e), rubrics=rubric_list(e.id))
    if request.method == 'DELETE':
        require(not e.slots,'Examination has slots/history; archive it instead',409)
        for r in e.rubrics: db.session.delete(r)
        db.session.delete(e)
    else:
        d=payload()
        require(e.status != 'completed','Completed examinations are read-only')
        values=validate_exam(d,e)
        examiners=assigned_examiners(d.get('examiner_ids',[]))
        require(all(s.examiner_id in [x.id for x in examiners] for s in e.slots if s.status != 'cancelled'),
            'Reassign existing slots before removing an examiner')
        for k,v in values.items(): setattr(e,k,v)
        e.examiners=examiners
    db.session.commit()
    return jsonify(message='Examination saved')

@admin_bp.post('/examinations/<int:key>/status')
@roles('admin')
def exam_status(key):
    e=get(Examination,key); status=payload().get('status')
    require(status in ('draft','slot_creation','booking_open','closed','completed','archived'),'Invalid status')
    if status == 'archived':
        require(not Booking.query.filter_by(examination_id=e.id,status='booked').first(),'Finish or reschedule outstanding bookings before archiving')
        e.archived=True; e.status='closed' if e.status != 'completed' else e.status
    else:
        require(not e.archived,'Archived examination is read-only')
        if status == 'slot_creation':
            require(not e.booking_started and utcnow() < e.slot_booking_start,'Booking has already begun')
        if status == 'booking_open':
            validate_rubric_total(e)
            e.booking_started=True
        if status == 'draft':
            require(not e.booking_started,'Cannot revert to draft after booking began')
        if status == 'completed':
            require(not Booking.query.filter_by(examination_id=e.id,status='booked').first(),'Complete all active bookings first')
        e.status=status
    db.session.commit()
    return jsonify(message='Examination status updated')

@admin_bp.route('/examinations/<int:key>/rubrics', methods=['GET','POST'])
@roles('admin')
def rubrics(key):
    e=get(Examination,key)
    if request.method == 'GET': return jsonify(rubric_list(key))
    require(not e.booking_started and not Booking.query.filter_by(examination_id=key).first(),'Rubric is locked after booking begins')
    r=Rubric(examination_id=key,**rubric_values(payload()))
    db.session.add(r); db.session.commit()
    return jsonify(rubric_data(r)),201

def rubric_values(d):
    weight=number(d,'weightage',0.01)
    require(weight <= 100,'Weight cannot exceed 100%')
    return dict(criterion_name=string(d,'criterion_name',100),maximum_marks=number(d,'maximum_marks',0.01),
        weightage=weight,description=string(d,'description',2000,False))

@admin_bp.route('/rubrics/<int:key>',methods=['PUT','DELETE'])
@roles('admin')
def rubric_detail(key):
    r=get(Rubric,key); e=r.examination
    require(not e.booking_started and not Booking.query.filter_by(examination_id=e.id).first(),'Rubric is locked after booking begins')
    if request.method == 'DELETE': db.session.delete(r)
    else:
        for k,v in rubric_values(payload()).items(): setattr(r,k,v)
    db.session.commit()
    return jsonify(message='Rubric saved')

def people_data(profile):
    data=user_data(profile.user)
    data.update(id=profile.id,user_id=profile.user_id,contact_details=profile.contact_details)
    if isinstance(profile,Examiner): data['department']=profile.department
    else: data['student_id']=profile.student_id
    return data

@admin_bp.route('/<any(students,examiners):kind>',methods=['GET','POST'])
@roles('admin')
def people(kind):
    model=Student if kind=='students' else Examiner
    if request.method == 'GET':
        return jsonify(search_rows([people_data(p) for p in model.query.all()],request.args.get('q',''),['name','email','student_id','department']))
    user=create_user(payload(),'student' if kind=='students' else 'examiner')
    db.session.commit()
    return jsonify(user=user_data(user)),201

@admin_bp.route('/<any(students,examiners):kind>/<int:key>',methods=['PUT','DELETE'])
@roles('admin')
def person(kind,key):
    p=get(Student if kind=='students' else Examiner,key); u=p.user
    if request.method == 'DELETE':
        u.active=False; u.token_version+=1
    else:
        d=payload(); u.name=string(d,'name',100)
        email=string(d,'email',120).lower()
        require('@' in email and '.' in email.rsplit('@',1)[-1],'Invalid email')
        u.email=email
        p.contact_details=string(d,'contact_details',200,False)
        if kind=='examiners': p.department=string(d,'department',100)
        else: p.student_id=string(d,'student_id',50)
        require(isinstance(d.get('active',True),bool),'active must be true or false')
        if u.active != d.get('active',True): u.token_version+=1
        u.active=d.get('active',True)
        if d.get('password'):
            require(len(string(d,'password',128))>=8,'Password needs at least 8 characters')
            u.set_password(d['password']); u.token_version+=1
    db.session.commit()
    return jsonify(message='Account saved; history retained')

@admin_bp.get('/slots')
@roles('admin')
def slots():
    return jsonify(schedule_list())

@admin_bp.get('/bookings')
@roles('admin')
def bookings():
    return jsonify(search_rows([booking_data(b) for b in Booking.query.order_by(Booking.id.desc()).all()],
        request.args.get('q',''),['id','student_name','student_code','examination_name','examiner_name','status']))

@admin_bp.post('/reschedule')
@roles('admin')
def reschedule():
    d=payload(); b=get(Booking,d.get('booking_id')); target=get(Slot,d.get('new_slot_id')); old=b.slot
    require(b.status=='booked' and not b.evaluation,'Only unevaluated active bookings can be rescheduled')
    require(old.id != target.id and old.examination_id == target.examination_id,'Choose another slot in the same examination')
    require(target.status=='available' and target.available_seats>0 and slot_future(target),'Target slot is unavailable',409)
    require(target.examiner.user.active,'Target examiner is inactive')
    reason=string(d,'reason',1000)
    b.slot=target; db.session.flush()
    db.session.expire(old,['bookings']); db.session.expire(target,['bookings'])
    sync_slot(old); sync_slot(target)
    audit(b,'rescheduled',old_slot_id=old.id,new_slot_id=target.id,reason=reason)
    db.session.commit()
    return jsonify(message='Booking rescheduled')

@admin_bp.post('/slots/<int:key>/reschedule')
@roles('admin')
def reschedule_slot(key):
    s=get(Slot,key); d=payload()
    require(all(not b.evaluation for b in s.bookings),'Cannot change an evaluated slot')
    values=validate_slot(d,s.examination,s.examiner_id,s)
    require(values['max_student_capacity']>=sum(b.status!='cancelled' for b in s.bookings),'Capacity below booked count')
    old=slot_data(s); reason=string(d,'reason',1000)
    for k,v in values.items(): setattr(s,k,v)
    for b in s.bookings:
        if b.status!='cancelled': audit(b,'slot_rescheduled',old=old,new=slot_data(s),reason=reason)
    sync_slot(s); db.session.commit()
    return jsonify(message='Slot rescheduled')

@admin_bp.post('/reassign-examiner')
@roles('admin')
def reassign():
    d=payload(); s=get(Slot,d.get('slot_id')); examiner=get(Examiner,d.get('examiner_id'))
    require(examiner.user.active,'Examiner is inactive')
    require(all(not b.evaluation for b in s.bookings),'Cannot reassign an evaluated slot')
    require(s.status not in ('cancelled','completed'),'Slot is not active')
    require(examiner.id != s.examiner_id,'Select a different examiner')
    reason=string(d,'reason',1000)
    validate_slot(slot_data(s),s.examination,examiner.id,s)
    old=s.examiner_id; s.examiner_id=examiner.id
    if examiner not in s.examination.examiners: s.examination.examiners.append(examiner)
    for b in s.bookings:
        audit(b,'examiner_reassigned',old_examiner_id=old,new_examiner_id=examiner.id,reason=reason)
    db.session.commit()
    return jsonify(message='Examiner reassigned')

@admin_bp.post('/examinations/<int:key>/publish')
@roles('admin')
def publish(key):
    get(Examination,key)
    rows=Booking.query.filter_by(examination_id=key,status='completed').all()
    ready=[b for b in rows if b.evaluation and not b.evaluation.published_at]
    require(ready,'No completed, unpublished evaluations')
    for b in ready:
        b.evaluation.published_at=utcnow()
        audit(b,'results_published')
    db.session.commit()
    return jsonify(message=f'Published {len(ready)} results')

@admin_bp.get('/reports')
@roles('admin')
def reports():
    return jsonify(report_data())
