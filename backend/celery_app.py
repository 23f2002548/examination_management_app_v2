from celery import Celery, Task
from celery.schedules import crontab

def make_celery(app):
    class FlaskTask(Task):
        def __call__(self,*args,**kwargs):
            with app.app_context():
                return self.run(*args,**kwargs)
    celery=Celery(app.import_name,task_cls=FlaskTask)
    celery.conf.update(broker_url=app.config['CELERY_BROKER_URL'],result_backend=app.config['CELERY_RESULT_BACKEND'],
        task_serializer='json',result_serializer='json',accept_content=['json'],
        timezone=app.config['APP_TIMEZONE'],enable_utc=True,broker_connection_retry_on_startup=True,
        broker_transport_options={'socket_connect_timeout':3,'socket_timeout':3},
        task_publish_retry=False,imports=['backend.tasks'],task_default_queue='emp',
        beat_schedule={
            'daily-examination-reminders':{'task':'backend.tasks.send_daily_exam_reminders','schedule':crontab(hour=8,minute=0)},
            'monthly-examination-report':{'task':'backend.tasks.generate_monthly_exam_report','schedule':crontab(day_of_month=1,hour=7,minute=0)}
        })
    celery.set_default()
    app.extensions['celery']=celery
    return celery
