import os
from celery import Celery

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://admin:password@rabbitmq:5672//")
app = Celery("worker_app", broker=RABBITMQ_URL)
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_routes = {
    "worker_app.tasks.process_action": {"queue": os.getenv("RABBITMQ_QUEUE","actions")},
}
