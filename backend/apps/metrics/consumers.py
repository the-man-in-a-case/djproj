# backend/apps/metrics/consumers.py
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings
from .influx_queries import (
    query_all_measurements_for_task_by_percentage,
)

logger = logging.getLogger(__name__)

class MetricsConsumer(AsyncWebsocketConsumer):
    """
    WebSocket: /ws/metrics/<project_id>/<action_id>/
    - 分组：metrics:<project_id>:<action_id>
    - 收到消息：{"percentage": 50.0, "measurement": "*", "window": 0, "start": "-30d", "limit": 0}
    - 查询该 task（task_id=project.action）下的 measurement（或全部）在该 percentage 对应的 step 范围内的数据
    """

    async def connect(self):
        self.project_id = self.scope["url_route"]["kwargs"]["project_id"]
        self.action_id = self.scope["url_route"]["kwargs"]["action_id"]
        self.task_id = f"{self.project_id}.{self.action_id}"
        self.group_name = f"metrics:{self.project_id}:{self.action_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"[WS] connected group={self.group_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"[WS] disconnected group={self.group_name} code={close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            payload = json.loads(text_data or "{}")
        except Exception as e:
            await self.send(json.dumps({"error": f"invalid json: {e}"}))
            return

        # 读取查询参数
        percentage = float(payload.get("percentage", 50.0))
        measurement = payload.get("measurement", "*")  # 容器名；"*" 表示全部
        window = int(payload.get("window", 0))
        start = payload.get("start", "-30d")
        limit = int(payload.get("limit", 0))

        # 执行查询（同步 I/O 走线程池）
        from asyncio import get_running_loop
        loop = get_running_loop()
        try:
            selected_steps, data_by_m = await loop.run_in_executor(
                None,
                query_all_measurements_for_task_by_percentage,
                settings.INFLUX_BUCKET,
                self.task_id,
                measurement,
                percentage,
                window,
                start,
                limit,
            )
        except Exception as e:
            await self.send(json.dumps({"error": f"influx query failed: {e}"}))
            return

        # 组装返回
        resp = {
            "project_id": self.project_id,
            "action_id": self.action_id,
            "task_id": self.task_id,
            "percentage": percentage,
            "selected_steps": selected_steps,
            "measurements": data_by_m,   # { measurement: [rows...] }
        }
        # 发给当前连接（如需广播，也可改为 group_send）
        await self.send(json.dumps(resp))

    # 若未来需要服务端广播，可用这个 handler
    async def metrics_push(self, event):
        await self.send(event["text"])
