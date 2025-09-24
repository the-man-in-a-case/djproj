from django.urls import path
from .views import create_project, dispatch_action

urlpatterns = [
    path("projects/", create_project),
    path("actions/", dispatch_action),
]
