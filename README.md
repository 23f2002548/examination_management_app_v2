# Examination Management Portal V2

Flask API, Vue 3 UI, Bootstrap 5, SQLite, JWT authentication, Redis cache and Celery jobs.
Designed strictly following the MAD-2 project specification and mandatory framework requirements.

## Local setup (Windows PowerShell)

Use Python 3.11+ and Node.js 22.12+ (the verified environment uses Python 3.14 and Node 24).

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm ci
npm run build
.\.venv\Scripts\python init_db.py
```

Run a Redis server on localhost:6379. If Redis already runs, use it. Otherwise a WSL installation can run
`redis-server --daemonize yes`, or an installed Docker engine can run
`docker run --name emp-redis -p 127.0.0.1:6379:6379 -d redis:7-alpine`.
The Redis client is pinned to 5.2.1 for compatibility with the local Windows Redis 3.0 server.
These alternatives are setup instructions; no Redis server is bundled in the submission.

```powershell
.\.venv\Scripts\python scripts/run_local.py
```

Open **http://127.0.0.1:5000**. This starts Flask, a Celery worker using the Windows-compatible solo pool,
Celery Beat and a local SMTP inbox. Redis remains an independent service. Stop the launcher with Ctrl+C.
Logs are in `instance/logs`. A frontend build is served directly by Flask, so the demo needs no internet.

Initial Admin: **admin@emp.edu / Admin123!**.
Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and optionally `SECRET_KEY` before the first initialization to override defaults.
The generated secret is persisted in `instance/.secret`. Database and secrets are excluded from the source ZIP.

Optional sample records (clearly marked demo accounts):

```powershell
.\.venv\Scripts\python scripts/seed_demo.py
```

Demo examiner/student: `examiner@demo.local` and `student@demo.local`; password `Demo12345!`.
Self-registration always creates a student. Only Admin creates examiners.

## Separate development processes

```powershell
.\.venv\Scripts\python run.py
npm run dev
.\.venv\Scripts\python -m celery -A worker.celery worker --pool=solo --loglevel=info
.\.venv\Scripts\python -m celery -A worker.celery beat --loglevel=info --schedule instance/celerybeat-schedule
.\.venv\Scripts\python scripts/mail_sink.py
```

Run each command in its own terminal. Use http://127.0.0.1:5173 for Vite development; it proxies /api to Flask.
Do not run two Beat schedulers simultaneously.

## Email and scheduled jobs

The default SMTP destination is **127.0.0.1:1025**, a local inbox that writes MIME email files to `instance/mail`.
Open an .eml file in an email client to inspect its text/HTML. This demonstrates actual SMTP delivery without contacting real students.
For real delivery configure `MAIL_HOST`, `MAIL_PORT`, `MAIL_FROM`, `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_TLS=true` as needed.

Celery Beat schedules reminders daily at **08:00 IST** for future active bookings, and the previous month's HTML report
on the **first day of each month at 07:00 IST**. Report data is scoped to examination slot dates in that month.
To demonstrate immediately with the worker and SMTP inbox running:

```powershell
.\.venv\Scripts\python -m celery -A worker.celery call backend.tasks.send_daily_exam_reminders
.\.venv\Scripts\python -m celery -A worker.celery call backend.tasks.generate_monthly_exam_report
```

Student dashboard exports run as asynchronous Celery tasks. The page polls job status, announces completion,
and offers an authenticated download. Exports retain zero scores and exclude unpublished marks.
If Redis is unavailable, export requests return a clear failure; they do not pretend to run asynchronously.

## Rules and design

- Timeline timestamps are stored in UTC. Forms and slot schedules use Asia/Kolkata (IST).
- Creation and booking require both the administrator-controlled status and the configured period.
- Slot edits/removal stop once booking begins. Cancellation stops at the booking deadline.
- A SQLite partial unique index enforces one non-cancelled booking per student/exam. BEGIN IMMEDIATE serializes
  write operations so simultaneous bookings cannot consume the same last seat.
- A cancelled booking remains in history; the student can book again within the allowed period.
- Criteria weights must total 100%; score = sum(raw / criterion maximum _ weight / 100 _ examination maximum).
  Rubrics are locked once booking begins. Evaluation stores criterion snapshots.
- Only the slot's assigned examiner can evaluate its students, after the examination starts.
  Completion and publication are separate. All student result/history/export paths hide unpublished scores.
- Administrative rescheduling preserves an audit trail and updates both slots' capacities. Evaluated bookings cannot be moved.
- Courses/examinations with history cannot be deleted; use archive. People are deactivated, retaining their history.
- JWTs live in HttpOnly cookies with double-submit CSRF protection. Logout and deactivation invalidate tokens.
- Examination lists, schedules and rubrics use Redis with 120-second expiry and mutation invalidation.
  Role checks run before data access; user-specific responses are not cached.
- Monthly report, reminders and CSV export use a real Redis-backed Celery worker. The local mail sink is a development utility.

## Build and submission

```powershell
npm run build
.\.venv\Scripts\python scripts/package_submission.py
```

The code ZIP has exactly one top-level project folder (`examination_management_23f2002548`) and includes the built frontend in `dist/`.

**Still requires Sajal's action:** record a 5-10 minute video, upload it to Drive with link access,
insert its link in the report source and regenerate the PDF, register/verify Git Tracker and private Git history,
and run the institution's submission validation form before submission.
No video or academic declaration of sole authorship has been fabricated. The report discloses AI assistance.
