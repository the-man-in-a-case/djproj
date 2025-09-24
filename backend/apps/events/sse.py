import json, time, logging
import redis
from django.conf import settings
from django.http import StreamingHttpResponse
from django.urls import path

logger = logging.getLogger(__name__)

def sse_events_view(request):
    """
    SSE：订阅指定 project 的任务事件，15s 心跳
    GET /api/sse/events?project_id=...
    """
    project_id = request.GET.get("project_id","")
    if not project_id:
        return StreamingHttpResponse(iter(["data: {\"error\":\"missing project_id\"}\n\n"]), content_type="text/event-stream")

    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    channel = f"events:project:{project_id}"
    pubsub.subscribe(channel)

    def event_stream():
        last_ping = time.time()
        try:
            while True:
                m = pubsub.get_message(timeout=1.0)
                if m and m.get("type") == "message":
                    yield f"data: {m['data']}\n\n"
                # heartbeat
                if time.time() - last_ping > 15:
                    yield ": ping\n\n"
                    last_ping = time.time()
        except GeneratorExit:
            pubsub.close()

    resp = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"  # for nginx
    return resp

urlpatterns = [ path("events", sse_events_view) ]
