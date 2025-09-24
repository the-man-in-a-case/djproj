from celery import Celery
from django.conf import settings

celery_event_app = Celery("event-listener", broker=settings.RABBITMQ_URL)
