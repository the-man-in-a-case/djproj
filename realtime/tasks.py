import asyncio, datetime, json
from influxdb_client import InfluxDBClient
from django.conf import settings
async def query_influx_async(progress, window_sec, consumer):
    try:
        loop=asyncio.get_running_loop()
        result=await loop.run_in_executor(None, query_influx, progress, window_sec)
        await consumer.send_json(result)
    except Exception as e:
        await consumer.send_json({"error": f"Influx query failed: {e}"})
def query_influx(progress, window_sec=10):
    client=None
    try:
        client=InfluxDBClient(url=settings.INFLUX_URL, token=settings.INFLUX_TOKEN, org=settings.INFLUX_ORG)
        q=f'from(bucket:"{settings.INFLUX_BUCKET}") |> range(start: -{100-progress}m) |> limit(n:100)'
        tables=client.query_api().query(q)
        data=[]
        for t in tables:
            for r in t.records:
                data.append({"time": r.get_time().isoformat(), "value": r.get_value()})
        return {"progress":progress,"data":data,"window_sec":window_sec}
    except Exception as e:
        return {"progress":progress,"error":str(e),"data":[]}
    finally:
        if client:
            try: client.close()
            except Exception: pass
