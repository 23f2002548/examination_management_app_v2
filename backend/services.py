"""Shared validation, serializers and booking operations."""
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from flask import g, current_app
from backend.models import db, Course, Examination, Rubric, Slot, Booking, Evaluation, BookingEvent, utcnow
from backend.common import require, string, number, parse_datetime, local_now, iso, APIError
from backend.cache import cached_data

def get(model, key):
    try:
        value = db.session.get(model, int(key))
    except (ValueError, TypeError):
        raise APIError('Invalid record ID')
    require(value is not None, 'Record not found', 404)
    return value

def course_data(c):
    return dict(id=c.id, course_code=c.course_code, course_name=c.course_name, description=c.description, status=c.status)

def rubric_data(r):
    return dict(id=r.id, examination_id=r.examination_id, criterion_name=r.criterion_name, maximum_marks=r.maximum_marks, weightage=r.weightage, description=r.description)

def exam_data(e):
    result = {key: getattr(e, key) for key in ('id','course_id','examination_name','examination_type','duration','maximum_marks','status','instructions','archived','booking_started')}
    for key in ('slot_creation_start','slot_creation_end','slot_booking_start','slot_booking_end'):
        result[key] = iso(getattr(e, key))
    result.update(course_name=e.course.course_name, course_code=e.course.course_code,
                  course_status=e.course.status, examiner_ids=[x.id for x in e.examiners], slots_count=len(e.slots))
    return result

def slot_data(s):
    return dict(id=s.id, examination_id=s.examination_id, examination_name=s.examination.examination_name,
        course_name=s.examination.course.course_name, examiner_id=s.examiner_id, examiner_name=s.examiner.user.name,
        date=s.date.isoformat(), start_time=s.start_time.strftime('%H:%M'), end_time=s.end_time.strftime('%H:%M'),
        max_student_capacity=s.max_student_capacity, available_seats=s.available_seats, status=s.status,
        meeting_link=s.meeting_link, timezone=current_app.config['APP_TIMEZONE'])

def booking_data(b, student=False):
    e = b.evaluation
    visible = e and (not student or e.published_at)
    return dict(id=b.id, student_id=b.student_id, student_code=b.student.student_id, student_name=b.student.user.name,
        examination_id=b.examination_id, slot_id=b.slot_id, examination_name=b.slot.examination.examination_name,
        course_name=b.slot.examination.course.course_name, examiner_name=b.slot.examiner.user.name,
        examiner_id=b.slot.examiner_id, date=b.slot.date.isoformat(), start_time=b.slot.start_time.strftime('%H:%M'),
        end_time=b.slot.end_time.strftime('%H:%M'), meeting_link=b.slot.meeting_link,
        booking_date=iso(b.booking_date), status=b.status, examination_status=b.slot.examination.status,
        instructions=b.slot.examination.instructions, maximum_marks=b.slot.examination.maximum_marks,
        evaluation=dict(total_marks=e.total_marks, remarks=e.remarks, scores=e.scores, status=e.status,
            evaluation_date=iso(e.evaluation_date), published_at=iso(e.published_at)) if visible else None,
        events=[dict(action=x.action, details=x.details, created_at=iso(x.created_at)) for x in b.events if not student or x.action != 'evaluated'])

def exam_list():
    return cached_data('examinations', lambda: [exam_data(e) for e in Examination.query.order_by(Examination.id.desc()).all()])

def schedule_list():
    return cached_data('schedules', lambda: [slot_data(s) for s in Slot.query.order_by(Slot.date, Slot.start_time).all()])

def rubric_list(exam_id):
    return [r for r in cached_data('rubrics', lambda: [rubric_data(r) for r in Rubric.query.all()]) if r['examination_id'] == exam_id]

def audit(booking, action, **details):
    db.session.add(BookingEvent(booking_id=booking.id, actor_id=g.user.id, action=action, details=details))

def booking_open(exam):
    return (not exam.archived and exam.course.status == 'active' and exam.status == 'booking_open'
        and exam.slot_booking_start <= utcnow() <= exam.slot_booking_end)

def slot_future(slot):
    return datetime.combine(slot.date, slot.start_time) > local_now()

def sync_slot(slot):
    occupied = sum(b.status != 'cancelled' for b in slot.bookings)
    slot.available_seats = slot.max_student_capacity - occupied
    if slot.status == 'cancelled':
        return
    active = [b for b in slot.bookings if b.status != 'cancelled']
    if active and all(b.status == 'completed' for b in active):
        slot.status = 'completed'
    else:
        slot.status = 'full' if slot.available_seats == 0 else 'available'

def validate_exam(data, exam=None):
    course = get(Course, data.get('course_id'))
    require(course.status == 'active' or (exam and exam.course_id == course.id), 'Choose an active course')
    result = dict(course_id=course.id, examination_name=string(data,'examination_name',100),
        examination_type=string(data,'examination_type',30), duration=number(data,'duration',1,True),
        maximum_marks=number(data,'maximum_marks',1), instructions=string(data,'instructions',5000,False))
    require(result['examination_type'] in ('Viva','Practical','Project Demo','Assessment'), 'Invalid examination type')
    require(result['duration'] <= 1440, 'Duration cannot exceed a day')
    for key in ('slot_creation_start','slot_creation_end','slot_booking_start','slot_booking_end'):
        result[key] = parse_datetime(data.get(key))
    require(result['slot_creation_start'] < result['slot_creation_end'] <= result['slot_booking_start'] < result['slot_booking_end'],
        'Timelines must be ordered: creation start < creation end <= booking start < booking end')
    if exam and exam.slots:
        require(result['course_id'] == exam.course_id, 'Cannot change course after slots exist')
        require(result['duration'] == exam.duration, 'Cannot change duration after slots exist')
        for slot in exam.slots:
            require(parse_datetime(f'{slot.date}T{slot.start_time}') > result['slot_booking_end'],
                'Booking must close before every examination slot')
    if exam and Booking.query.filter_by(examination_id=exam.id).first():
        require(result['maximum_marks'] == exam.maximum_marks, 'Cannot change maximum marks after bookings exist')
        require(result['slot_creation_start'] == exam.slot_creation_start and result['slot_creation_end'] == exam.slot_creation_end
            and result['slot_booking_start'] == exam.slot_booking_start, 'Cannot rewrite past periods after bookings exist')
    return result

def validate_rubric_total(exam):
    require(exam.rubrics and abs(sum(r.weightage for r in exam.rubrics)-100) < 0.001,
        'Add rubric criteria with weights totaling 100% before opening booking')

def validate_slot(data, exam, examiner_id, old=None):
    try:
        day = date.fromisoformat(data.get('date',''))
        start = time.fromisoformat(data.get('start_time',''))
        end = time.fromisoformat(data.get('end_time',''))
    except (ValueError, TypeError):
        raise APIError('Invalid slot date or time')
    require(start.tzinfo is None and end.tzinfo is None, 'Enter slot times in local IST without an offset')
    require(start < end, 'End time must be after start time')
    require(datetime.combine(day,start) > local_now(), 'Slot must be in the future')
    require(parse_datetime(f'{day}T{start}') > exam.slot_booking_end, 'Slot must begin after booking closes')
    minutes = (datetime.combine(day,end)-datetime.combine(day,start)).total_seconds()/60
    require(minutes >= exam.duration, 'Slot is shorter than the examination duration')
    capacity = number(data, 'max_student_capacity', 1, True)
    link = string(data,'meeting_link',500,False)
    require(not link or link.startswith(('https://','http://')), 'Meeting link must use http or https')
    overlaps = Slot.query.filter(Slot.examiner_id == examiner_id, Slot.date == day, Slot.status != 'cancelled',
        Slot.start_time < end, Slot.end_time > start).all()
    require(all(old and s.id == old.id for s in overlaps), 'Examiner already has an overlapping slot', 409)
    return dict(date=day,start_time=start,end_time=end,max_student_capacity=capacity,meeting_link=link)

def slot_editable(exam):
    require(not exam.archived and not exam.booking_started and utcnow() < exam.slot_booking_start,
        'Slots cannot be edited or removed after booking begins')

def search_rows(rows, query, fields):
    q = query.strip().lower()
    return [r for r in rows if not q or any(q in str(r.get(f,'')).lower() for f in fields)]

def report_data(start=None, end=None):
    bookings = Booking.query.all()
    if start and end:
        bookings = [b for b in bookings if start <= b.slot.date < end]
    completed = [b for b in bookings if b.status == 'completed']
    evaluated = [b for b in bookings if b.evaluation]
    workload = {}
    for b in completed:
        examiner_id = b.slot.examiner_id
        entry = workload.setdefault(examiner_id, dict(examiner_id=examiner_id, name=b.slot.examiner.user.name, completed_bookings=0))
        entry['completed_bookings'] += 1
    return dict(examinations_conducted=len({b.examination_id for b in completed}),
        students_evaluated=len({b.student_id for b in evaluated}), completed_bookings=len(completed),
        pending_evaluations=sum(b.status == 'booked' and not b.evaluation for b in bookings),
        most_active_examiners=sorted(workload.values(), key=lambda x: x['completed_bookings'], reverse=True))
