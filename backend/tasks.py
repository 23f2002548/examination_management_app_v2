"""Real Celery jobs. Email uses configurable SMTP (local demo server by default)."""
import csv
import io
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from html import escape
from celery import shared_task
from flask import current_app
from backend.models import db, Booking, User, ExportJob, utcnow
from backend.services import report_data
from backend.common import local_now

def send_mail(recipient,subject,body,html=None):
    msg=EmailMessage()
    msg['From']=current_app.config['MAIL_FROM']; msg['To']=recipient; msg['Subject']=subject
    msg.set_content(body)
    if html: msg.add_alternative(html,subtype='html')
    with smtplib.SMTP(current_app.config['MAIL_HOST'],current_app.config['MAIL_PORT'],timeout=15) as smtp:
        if current_app.config['MAIL_TLS']: smtp.starttls()
        if current_app.config['MAIL_USERNAME']:
            smtp.login(current_app.config['MAIL_USERNAME'],current_app.config['MAIL_PASSWORD'])
        smtp.send_message(msg)

@shared_task(name='backend.tasks.send_daily_exam_reminders')
def send_daily_exam_reminders():
    now=local_now(); sent=0
    for b in Booking.query.filter_by(status='booked').all():
        s=b.slot
        if datetime.combine(s.date,s.start_time)<=now or not b.student.user.active: continue
        e=s.examination
        body=(f'Examination: {e.examination_name}\nDate: {s.date}\nTime: {s.start_time} - {s.end_time} '
            f'({current_app.config["APP_TIMEZONE"]})\nExaminer: {s.examiner.user.name}\n'
            f'Instructions: {e.instructions or "Please arrive on time with your student ID."}\nMeeting: {s.meeting_link or "See examination instructions"}')
        send_mail(b.student.user.email,'Examination reminder: '+e.examination_name,body)
        sent+=1
    return {'sent':sent}

@shared_task(name='backend.tasks.generate_monthly_exam_report')
def generate_monthly_exam_report():
    end=local_now().date().replace(day=1); start=(end-timedelta(days=1)).replace(day=1)
    stats=report_data(start,end)
    rows=''.join(f'<tr><th>{escape(k.replace("_"," ").title())}</th><td>{v}</td></tr>'
        for k,v in stats.items() if k!='most_active_examiners')
    workload=''.join(f'<li>{escape(x["name"])}: {x["completed_bookings"]} completed bookings</li>' for x in stats['most_active_examiners'])
    html=f'<html><body><h1>Monthly examination report</h1><p>{start:%B %Y}</p><table>{rows}</table><h2>Most active examiners</h2><ul>{workload or "<li>No completed bookings</li>"}</ul></body></html>'
    admin=User.query.filter_by(role='admin').one()
    send_mail(admin.email,f'Monthly examination report - {start:%B %Y}',str(stats),html)
    return stats

def csv_safe(value):
    # Prevent spreadsheet formula execution in exported user-provided text.
    value='' if value is None else str(value)
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value

@shared_task(name='backend.tasks.export_exam_history_csv')
def export_exam_history_csv(job_id):
    job=db.session.get(ExportJob,job_id)
    if not job: return {'error':'Job not found'}
    if job.status=='completed': return {'id':job.id,'status':'completed'}
    try:
        job.status='running'; db.session.commit()
        output=io.StringIO(newline=''); writer=csv.writer(output)
        writer.writerow(['Student ID','Examination Name','Course','Examination Date','Examiner','Marks Obtained','Booking Status'])
        for b in Booking.query.filter_by(student_id=job.student_id).order_by(Booking.id).all():
            e=b.evaluation; s=b.slot
            writer.writerow([csv_safe(v) for v in [b.student.student_id,s.examination.examination_name,
                s.examination.course.course_name,s.date,s.examiner.user.name,
                e.total_marks if e and e.published_at else '',b.status]])
        job.csv_content=output.getvalue(); job.status='completed'; job.completed_at=utcnow()
        db.session.commit()
        return {'id':job.id,'status':'completed'}
    except Exception:
        db.session.rollback()
        job=db.session.get(ExportJob,job_id); job.status='failed'; job.error='Export failed. Please retry.'
        db.session.commit()
        raise
