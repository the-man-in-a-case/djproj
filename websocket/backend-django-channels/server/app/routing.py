from django.urls import re_path
from .consumers import ProgressConsumer

websocket_urlpatterns = [
    re_path(r"^ws/data/?$", ProgressConsumer.as_asgi()),
]
