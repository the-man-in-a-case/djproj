from django.urls import path
from . import views
urlpatterns=[
    path("projects/", views.create_project, name="create_project"),
    path("targets/", views.submit_target, name="submit_target"),
    path("projects/<uuid:pid>/status/", views.project_status, name="project_status"),
]
