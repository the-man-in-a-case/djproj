from django.urls import path
from server.app.views import health

urlpatterns = [
    path("health", health),
]
