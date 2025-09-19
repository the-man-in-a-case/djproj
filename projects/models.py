import uuid
from django.db import models
class Project(models.Model):
    STATUS_CHOICES=[("CREATED","CREATED"),("APPLYING","APPLYING"),("DISPATCHED","DISPATCHED"),("RUNNING","RUNNING"),("SUCCEEDED","SUCCEEDED"),("FAILED","FAILED")]
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name=models.CharField(max_length=128)
    user=models.CharField(max_length=128)
    industry=models.JSONField(default=list, blank=True)  # list of ints
    params=models.JSONField(default=dict, blank=True)
    containers=models.JSONField(default=list, blank=True)
    namespace=models.CharField(max_length=64, default="default")
    queue_name=models.CharField(max_length=128, default="celery")
    max_workers=models.IntegerField(default=10)
    scale_threshold=models.IntegerField(default=1)
    status=models.CharField(max_length=16, choices=STATUS_CHOICES, default="CREATED")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self): return f"{self.name}({self.id})"
class WorkerRun(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project=models.ForeignKey(Project, on_delete=models.CASCADE, related_name="runs")
    target=models.JSONField(default=dict)
    celery_task_id=models.CharField(max_length=100, blank=True, null=True)
    status=models.CharField(max_length=16, default="QUEUED")  # QUEUED, STARTED, SUCCESS, ERROR
    message=models.TextField(blank=True, null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta: indexes=[models.Index(fields=["project","status"])]
