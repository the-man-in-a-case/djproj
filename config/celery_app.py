import os
from celery import Celery
from django.conf import settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
app=Celery("config")
app.conf.broker_url=settings.CELERY_BROKER_URL
app.conf.result_backend=settings.CELERY_RESULT_BACKEND
