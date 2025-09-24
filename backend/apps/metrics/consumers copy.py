import json, asyncio, logging, random, datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings

try:
    from influxdb_client import InfluxDBClient
except Exception:
    InfluxDBClient = None

logger = logging.getLogger(__name__)

class MetricsConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def receive(self, text_data=None, bytes_data=None):
        """
        前端首帧：{"project_id": "...", "action_id": "...", "percentage": 50.0}
        根据 percentage 推导查询窗口并返回数据；若 Influx 不可用，返回 mock。
        """
        try:
            payload = json.loads(text_data or "{}")
            pct = float(payload.get("percentage", 50.0))
            # 时间窗口：过去 (0~100) 分钟的区间末端靠近当前
            now = datetime.datetime.utcnow()
            start = now - datetime.timedelta(minutes=max(1, int(100 - pct)))
            data = await asyncio.get_event_loop().run_in_executor(None, query_influx, start, now)
        except Exception as e:
            data = {"error": str(e), "points": []}
        await self.send(json.dumps(data))

def query_influx(start: datetime.datetime, end: datetime.datetime):
    # Influx 可用性判断
    if InfluxDBClient is None:
        return _mock_points(start, end, reason="no-client")
    try:
        client = InfluxDBClient(url=settings.INFLUX_URL, token=settings.INFLUX_TOKEN, org=settings.INFLUX_ORG)
        q = f'from(bucket:"{settings.INFLUX_BUCKET}") |> range(start: {start.isoformat()}Z, stop: {end.isoformat()}Z) |> limit(n:50)'
        tables = client.query_api().query(q)
        points = []
        for table in tables:
            for rec in table.records:
                points.append({"t": rec.get_time().isoformat(), "v": rec.get_value()})
        if not points:
            return _mock_points(start, end, reason="empty")
        return {"points": points}
    except Exception as e:
        return _mock_points(start, end, reason=f"err:{e}")
    finally:
        try:
            client.close()
        except Exception:
            pass

def _mock_points(start, end, reason="mock"):
    # 生成简单折线
    total = 30
    points = []
    span = (end - start).total_seconds()
    for i in range(total):
        ts = start.timestamp() + span * (i/(total-1))
        points.append({"t": datetime.datetime.utcfromtimestamp(ts).isoformat()+"Z", "v": round(50+10*random.uniform(-1,1),2)})
    return {"points": points, "mock": reason}
