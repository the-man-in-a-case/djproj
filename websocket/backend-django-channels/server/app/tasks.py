import asyncio
import datetime
import logging
from influxdb_client import InfluxDBClient

from django.conf import settings

# 配置日志
logger = logging.getLogger(__name__)

async def query_influx_async(progress, window_sec, consumer):
    """
    异步执行 InfluxDB 查询，然后推送结果
    """
    logger.info(f"[Backend] 启动异步 InfluxDB 查询任务: progress={progress}, window_sec={window_sec}, channel_name={consumer.channel_name}")
    try:
        loop = asyncio.get_running_loop()
        logger.debug(f"[Backend] 获取当前事件循环: progress={progress}, loop_id={id(loop)}")
        
        result = await loop.run_in_executor(None, query_influx, progress, window_sec)
        logger.info(f"[Backend] InfluxDB 查询完成: progress={progress}, 结果包含数据点数量={len(result.get('data', []))}")
        
        await consumer.send_query_result(result)
    except Exception as e:
        logger.error(f"[Backend] 异步查询 InfluxDB 失败: progress={progress}, 错误={str(e)}")
        # 尝试发送错误消息给前端
        try:
            await consumer.send(json.dumps({
                "error": f"查询 InfluxDB 失败: {str(e)}"
            }))
        except Exception as send_error:
            logger.error(f"[Backend] 发送错误消息给前端失败: progress={progress}, 错误={str(send_error)}")

def query_influx(progress, window_sec=10):
    """
    同步查询 InfluxDB (在线程池中运行)
    """
    logger.info(f"[Backend-Influx] 开始同步查询 InfluxDB: progress={progress}, window_sec={window_sec}")
    client = None
    try:
        # 创建 InfluxDB 客户端连接
        logger.debug(f"[Backend-Influx] 创建 InfluxDB 客户端: url={settings.INFLUX_URL}, org={settings.INFLUX_ORG}")
        client = InfluxDBClient(url=settings.INFLUX_URL, token=settings.INFLUX_TOKEN, org=settings.INFLUX_ORG)
        query_api = client.query_api()
        logger.info(f"[Backend-Influx] InfluxDB 客户端已创建并获取查询 API")

        # 根据进度条换算时间戳
        now = datetime.datetime.utcnow()
        start = now - datetime.timedelta(minutes=100 - progress)
        logger.debug(f"[Backend-Influx] 计算查询时间范围: start={start.isoformat()}, end={now.isoformat()}")
        
        # 构建查询语句，包含窗口参数
        query = f'from(bucket:"{settings.INFLUX_BUCKET}") '\
                f'|> range(start: {start.isoformat()}Z) '\
                f'|> limit(n:100)'
        logger.info(f"[Backend-Influx] 执行 InfluxDB 查询: {query}")
        
        # 执行查询
        tables = query_api.query(query)
        logger.info(f"[Backend-Influx] 查询返回表数量: {len(list(tables))}")
        
        # 处理查询结果
        data = []
        for table in tables:
            for record in table.records:
                point_data = {"time": record.get_time().isoformat(), "value": record.get_value()}
                data.append(point_data)
        
        logger.info(f"[Backend-Influx] 查询处理完成: 共处理 {len(data)} 个数据点")
        
        # 构造返回结果
        result = {"progress": progress, "data": data, "window_sec": window_sec}
        logger.debug(f"[Backend-Influx] 准备返回查询结果: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"[Backend-Influx] 查询 InfluxDB 时发生异常: {str(e)}")
        # 返回错误信息
        return {"progress": progress, "error": str(e), "data": []}
    finally:
        # 确保关闭客户端连接
        if client:
            try:
                client.close()
                logger.info(f"[Backend-Influx] InfluxDB 客户端已关闭")
            except Exception as close_error:
                logger.error(f"[Backend-Influx] 关闭 InfluxDB 客户端失败: {str(close_error)}")
