import json, asyncio, urllib.parse
from redis import asyncio as aioredis
from channels.generic.websocket import AsyncWebsocketConsumer
from .tasks import query_influx_async
REDIS_URL="redis://redis.djproj.svc.cluster.local:6379"
class ProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.redis=aioredis.from_url(REDIS_URL, decode_responses=True)
    async def disconnect(self, code):
        try: await self.redis.close()
        except Exception: pass
    async def receive(self, text_data):
        data=json.loads(text_data)
        progress=data.get("progress"); window_sec=data.get("window_sec",10)
        if progress is None:
            await self.send_json({"error":"missing progress"}); return
        asyncio.create_task(query_influx_async(progress, window_sec, self))
    async def send_json(self, payload):
        await self.send(json.dumps(payload))
class ProjectEventConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        pid=None
        parts=self.scope.get("path","/").rstrip("/").split("/")
        if len(parts)>=3 and parts[-2]=="project": pid=parts[-1]
        if not pid:
            qs=self.scope.get("query_string", b"").decode()
            params=dict(urllib.parse.parse_qsl(qs)); pid=params.get("pid")
        if not pid: await self.close(); return
        self.group=f"project-{pid}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
    async def disconnect(self, code):
        try: await self.channel_layer.group_discard(self.group, self.channel_name)
        except Exception: pass
    async def notify(self, event):
        await self.send(json.dumps(event))
