from os import name
from django.db import models
import uuid

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, db_index=True)
    industry = models.JSONField(default=list)  # list[str]
    industry_version = models.CharField(max_length=64)
    describe = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self): return f"{self.name}({self.id})"

class Action(models.Model):
    id = models.BigAutoField(primary_key=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="actions")
    action_id = models.CharField(max_length=120)
    action_name = models.CharField(max_length=120)
    # 将原本的target_list字段注释掉，改为通过外键关系关联Target模型
    # target_list = models.JSONField(default=list)  # list[dict]
    status = models.CharField(max_length=16, default="queued", db_index=True)  # queued|running|success|failed
    describe = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project","action_id"], name="uniq_project_action"),
        ]

    def __str__(self): return f"{self.project_id}:{self.action_id}:{self.status}"


class Target(models.Model):
    id = models.BigAutoField(primary_key=True)
    # 恢复Action与Target之间的外键关系
    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="target_list")
    node_id = models.CharField(max_length=120)
    node_name = models.CharField(max_length=120)
    industry = models.CharField(max_length=64)
    parameter = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)