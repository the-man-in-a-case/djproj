from django.contrib import admin
from .models import Project, WorkerRun
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display=("name","user","industry","namespace","status","queue_name","max_workers","created_at")
    search_fields=("name","id","user","namespace")
@admin.register(WorkerRun)
class WorkerRunAdmin(admin.ModelAdmin):
    list_display=("id","project","status","created_at","updated_at")
    search_fields=("id","project__name","celery_task_id")
