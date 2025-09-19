from django.urls import re_path
from .consumers import ProgressConsumer, ProjectEventConsumer
websocket_urlpatterns=[
    re_path(r"^ws/data/?$", ProgressConsumer.as_asgi()),
    re_path(r"^ws/project/(?P<pid>[^/]+)/?$", ProjectEventConsumer.as_asgi()),
]
