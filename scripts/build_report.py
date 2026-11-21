"""Generate the five-page submission report. Update VIDEO_URL after recording."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Table,TableStyle
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.graphics.shapes import Drawing,Rect,String,Line,Polygon
from html import escape

ROOT=Path(__file__).resolve().parent.parent
VIDEO_URL='PENDING - Sajal has not recorded the presentation video yet.'
OUT=ROOT/'output'/'pdf'/'project_report.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodySmall',fontName='Helvetica',fontSize=9.2,leading=13.2,spaceAfter=7))
styles.add(ParagraphStyle(name='ReportTitle',fontName='Helvetica-Bold',fontSize=23,leading=28,alignment=TA_CENTER,textColor=colors.black,spaceAfter=8))
styles.add(ParagraphStyle(name='ReportSubtitle',fontName='Helvetica-Bold',fontSize=17,leading=21,alignment=TA_CENTER,textColor=colors.black,spaceAfter=24))
styles.add(ParagraphStyle(name='SectionTitle',fontName='Helvetica-Bold',fontSize=15,leading=19,textColor=colors.black,spaceBefore=7,spaceAfter=10))
story=[]
def p(text): story.append(Paragraph(text,styles['BodySmall']))
def title(text): story.append(Paragraph(text,styles['SectionTitle']))
def table(rows,widths):
    cells=[[Paragraph(escape(str(c)),styles['BodySmall']) for c in row] for row in rows]
    t=Table(cells,colWidths=widths,hAlign='LEFT',repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eeeeee')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LINEBELOW',(0,0),(-1,0),0.8,colors.black),('LINEBELOW',(0,1),(-1,-1),0.3,colors.HexColor('#cccccc')),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
    story.append(t)
def page(): story.append(PageBreak())

story.append(Paragraph('App Development Project Report',styles['ReportTitle']))
story.append(Paragraph('Examination Management Portal - V2',styles['ReportSubtitle']))
title('1. Student Details')
p('<b>Name:</b> Sajal<br/><b>Roll Number:</b> 23f2002548<br/><b>Course:</b> Modern Application Development II, September 2026')
title('2. Project Details')
p('<b>Project Title:</b> Examination Management Portal - V2')
p('<b>Problem Statement:</b> Educational institutions need an efficient system for administrators, examiners and students to coordinate courses, examination schedules, examiner availability, slot booking, rubric-based evaluation and result publication.')
p('<b>Approach:</b> The application separates a Vue user interface, Flask JSON API, SQLite data model, Redis cache and Celery workers. Server-side validation enforces role ownership, examination timelines, slot capacity, one active booking per examination and controlled result publication. Historical activity is retained through archived records, evaluation snapshots and booking events.')
title('3. AI/LLM Declaration')
p('OpenAI Codex was used to inspect the supplied project documents, audit the initial code, complete substantial backend and frontend functionality, add validation and tests, debug local execution, and prepare documentation and this report. The assistance included implementation of business logic and interface code; it was not limited to proofreading or formatting.')
p('I will review the complete implementation and be prepared to explain and modify it during the viva. This declaration should be updated before submission if any additional AI tools or external sources are used.')
page()

title('4. Technologies and Frameworks Used')
table([['Technology / Library','Purpose'],
['Flask 3.1.3','Core backend framework for the JSON API and built frontend serving.'],
['Vue 3 and Vue Router 4','Role-based single-page user interface and navigation.'],
['Bootstrap 5','Responsive layout, forms, tables and visual styling.'],
['SQLite and SQLAlchemy','Programmatically created relational database and ORM.'],
['Flask-JWT-Extended','JWT authentication in HttpOnly cookies with CSRF protection.'],
['Redis and Flask-Caching','Caching examination lists, schedules and rubrics with expiry.'],
['Celery and Celery Beat','Asynchronous CSV export, daily reminders and monthly reports.'],
['Vite','Frontend build and development server.'],
['Werkzeug','Secure password hashing and verification.']],[145,355])
story.append(Spacer(1,16))
title('Application Flow')
p('<b>Browser -> Vue forms -> Flask JSON API -> authorization and validation -> SQLAlchemy / SQLite.</b> Frequently read examination, schedule and rubric data use Redis with a 120-second expiry and invalidation after changes.')
p('<b>CSV export:</b> Student dashboard -> owned export job -> Celery queue -> worker generates CSV -> browser polls job status -> completion alert -> authenticated download. Unpublished marks are excluded.')
p('<b>Scheduled jobs:</b> Celery Beat runs examination reminders daily at 08:00 IST and emails the previous calendar month\'s HTML report on the first day of each month at 07:00 IST.')
title('Local Demonstration')
p('After installing dependencies and building the frontend, start Redis and run <b>python scripts/run_local.py</b>. The launcher starts Flask, a Celery worker, Celery Beat and a local SMTP inbox. Open <b>http://127.0.0.1:5000</b>. Detailed setup and demo steps are provided in README.md and docs/DEMO.md.')
page()

title('5. Database Schema / ER Diagram')
p('Each arrow points from the referenced parent to the referencing child (1 to many, unless marked 1:1). The association table models examiner assignments. JSON criterion snapshots preserve the rubric used for each evaluation.')
d=Drawing(500,495)
nodes={
 'users':(185,430,['id PK, email UNIQUE','password_hash, role, active']),
 'examiners':(10,330,['id PK, user_id FK UNIQUE','department, contact_details']),
 'courses':(185,330,['id PK, course_code UNIQUE','name, description, status']),
 'students':(360,330,['id PK, user_id FK UNIQUE','student_id UNIQUE, contact']),
 'examination_examiners':(10,220,['examination_id PK/FK','examiner_id PK/FK']),
 'examinations':(185,220,['id PK, course_id FK','timelines, status, max marks']),
 'export_jobs':(360,220,['id PK, student_id FK','status, CSV, timestamps']),
 'rubrics':(10,110,['id PK, examination_id FK','criterion, max marks, weight']),
 'slots':(185,110,['id PK, examination_id FK','examiner_id FK, time, seats']),
 'bookings':(360,110,['id PK, student_id FK','examination_id FK, slot_id FK']),
 'evaluations':(185,0,['id PK, booking_id FK UNIQUE','examiner_id FK, scores JSON']),
 'booking_events':(360,0,['id PK, booking_id FK','actor_id FK -> users, details'])}
def edge(a,b,label='',route=None):
    ax,ay,_=nodes[a]; bx,by,_=nodes[b]
    if ay==by:
        start=(ax+130,ay+30) if ax<bx else (ax,ay+30)
        end=(bx,by+30) if ax<bx else (bx+130,by+30)
    else: start=(ax+65,ay); end=(bx+65,by+60)
    points=[start]+(route or [])+[end]
    for (x1,y1),(x2,y2) in zip(points,points[1:]): d.add(Line(x1,y1,x2,y2,strokeColor=colors.HexColor('#7088a5'),strokeWidth=0.8))
    x,y=end; px,py=points[-2]
    import math
    angle=math.atan2(y-py,x-px)
    d.add(Polygon([x,y,x-5*math.cos(angle-0.5),y-5*math.sin(angle-0.5),x-5*math.cos(angle+0.5),y-5*math.sin(angle+0.5)],fillColor=colors.HexColor('#7088a5'),strokeColor=None))
    if label: d.add(String((start[0]+end[0])/2+3,(start[1]+end[1])/2+3,label,fontSize=7,fillColor=colors.HexColor('#16365d')))
edge('users','examiners','1:1'); edge('users','students','1:1'); edge('courses','examinations')
edge('examiners','examination_examiners'); edge('examinations','examination_examiners')
edge('students','export_jobs'); edge('examinations','rubrics'); edge('examinations','slots')
edge('slots','bookings'); edge('bookings','evaluations','1:1'); edge('bookings','booking_events')
edge('examinations','bookings',route=[(335,195),(335,180),(425,180)])
edge('students','bookings',route=[(495,315),(495,180)])
edge('examiners','slots',route=[(155,310),(155,185),(250,185)])
edge('examiners','evaluations',route=[(0,315),(0,80),(175,80),(175,65),(250,65)])
edge('users','booking_events',route=[(500,415),(500,70),(425,70)])
for name,(x,y,fields) in nodes.items():
    d.add(Rect(x,y,130,60,fillColor=colors.HexColor('#f7f9fc'),strokeColor=colors.HexColor('#a8b8cc'),strokeWidth=0.7))
    d.add(Rect(x,y+41,130,19,fillColor=colors.HexColor('#16365d'),strokeColor=None))
    d.add(String(x+5,y+47,name,fontName='Helvetica-Bold',fontSize=7.7,fillColor=colors.white))
    for i,line in enumerate(fields): d.add(String(x+5,y+27-i*12,line,fontSize=7))
story.append(d)
story.append(Spacer(1,8))
p('Database constraints: one Admin via a partial unique index; one non-cancelled booking per student/examination; unique evaluation per booking; positive capacity and bounded available seats; foreign keys enabled. All tables and association rows are created programmatically.')
page()

title('6. API Resource Endpoints')
table([['Endpoint group','Methods and purpose'],
['/api/register, /login, /me, /logout','POST register/login/logout; GET current authenticated user. Registration fixes role to student.'],
['/api/admin/courses[/{id}]','GET list, POST create, PUT update, DELETE unreferenced course.'],
['/api/admin/examinations[/{id}]','GET list/detail, POST create, PUT update, DELETE unreferenced exam. Subresources /status and /publish use POST.'],
['/api/admin/examinations/{id}/rubrics; /rubrics/{id}','GET/POST exam rubric; PUT/DELETE criterion. Weights must total 100% before booking opens.'],
['/api/admin/students; /examiners [/{id}]','GET/POST lists/accounts; PUT edit; DELETE deactivates while retaining history.'],
['/api/admin/slots; /bookings; /reports; /dashboard','GET all slots, searchable bookings, statistics and dashboard counts.'],
['/api/admin/reschedule; /reassign-examiner; /slots/{id}/reschedule','POST exceptional booking/slot movements or examiner change, with reason and audit trail.'],
['/api/examiner/dashboard; /examinations; /slots; /bookings','GET assigned exams, owned slots and booked students. POST slots; PUT/DELETE /slots/{id}. GET /examinations/{id}/rubrics.'],
['/api/examiner/evaluate/{booking}; /complete-examination','POST criterion scores/remarks; POST completion for owned booking.'],
['/api/student/dashboard; /examinations; /slots; /bookings; /history; /results; /profile','GET student data; POST booking; POST /bookings/{id}/cancel; PUT profile.'],
['/api/student/exports[/{id}]; /exports/{id}/download','POST asynchronous export; GET job list/status; authenticated GET CSV download.']],[210,290])
story.append(Spacer(1,10))
p('All role endpoints verify JWT authentication and database role/active state. Read requests are scoped by student or assigned examiner. Changes take SQLite BEGIN IMMEDIATE before reading availability so conflicting requests serialize; database constraints provide another layer of protection.')
p('Times are validated in chronological order. Booking requires an open status and current timestamp inside the booking interval. Cancellation cannot be repeated or occur after its deadline. Rescheduling validates same-examination membership, destination capacity and future timing, updating old/new seat counts in one transaction.')
page()

title('7. Architecture and Features')
p('<b>Architecture Overview:</b><br/>- <b>app.py</b> - Flask entry point and application factory<br/>- <b>backend/models.py</b> - SQLAlchemy tables and constraints<br/>- <b>backend/admin.py, examiner.py, student.py</b> - role-specific API blueprints<br/>- <b>backend/tasks.py</b> - Celery exports, reminders and monthly reports<br/>- <b>frontend/</b> - Vue views, router and reusable form components')
p('<b>Implemented Features:</b><br/>- Student self-registration, login and profile management<br/>- Course, examination, examiner, rubric and timeline administration<br/>- Examiner assignment and time-slot management<br/>- Capacity-safe booking, cancellation and duplicate prevention<br/>- Rubric-based evaluation, remarks, completion and controlled publication<br/>- Exceptional booking rescheduling and examiner reassignment with audit history<br/>- Search, filters, dashboards and responsive Bootstrap interface<br/>- Redis caching, scheduled email jobs and asynchronous CSV export')
title('Verification')
p('Eighteen isolated behavioral tests pass, including concurrent last-seat booking, deadlines, role isolation, weighted scoring, result privacy and report filtering. Production build, desktop/mobile browser workflows, real Redis cache expiry, Celery queue execution and local SMTP output were also verified. Full evidence is recorded in docs/VERIFICATION.md.')
title('8. Video Presentation')
p('<b>Drive Link:</b> '+escape(VIDEO_URL))
p('<i>Before submission, record a 5-10 minute presentation, upload it with anyone-with-link view access, replace VIDEO_URL in scripts/build_report.py and regenerate this PDF.</i>')
title('References')
p('Project statement: appdev2_project_statement_sep26.pdf (23 pages). Project and viva instructions: appdev2_project_document_sep26.pdf (10 pages). Sample structure: App Dev Project Report (Example/Demo). The sample\'s demonstration content and post-report submission instructions were not copied into this report.')

def footer(canvas,doc):
    canvas.setStrokeColor(colors.HexColor('#aaaaaa')); canvas.line(48,43,547,43)
    canvas.setFont('Helvetica',8); canvas.setFillColor(colors.HexColor('#555555'))
    canvas.drawString(48,30,'Sajal | 23f2002548 | Examination Management Portal V2')
    canvas.drawRightString(547,30,str(doc.page))
doc=SimpleDocTemplate(str(OUT),pagesize=(595,842),rightMargin=47,leftMargin=48,topMargin=45,bottomMargin=55,title='Examination Management Portal V2 - Sajal',author='Sajal')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
