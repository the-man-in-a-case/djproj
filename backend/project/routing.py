from django.urls import re_path
from apps.metrics.consumers import MetricsConsumer

# websocket_urlpatterns = [
#     re_path(r'^ws/metrics/?$', MetricsConsumer.as_asgi()),
# ]
websocket_urlpatterns = [
    # 以 project_id + action_id 分组
    re_path(r'^ws/metrics/(?P<project_id>[^/]+)/(?P<action_id>[^/]+)/?$', MetricsConsumer.as_asgi()),
]