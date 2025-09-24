import json
import asyncio
import logging
from redis import asyncio as aioredis
from channels.generic.websocket import AsyncWebsocketConsumer
from .tasks import query_influx_async

# 配置日志
logger = logging.getLogger(__name__)

REDIS_URL = "redis://redis:6379"


class ProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.info(f"[Backend] 客户端尝试连接 WebSocket: channel_name={self.channel_name}")
        await self.accept()
        logger.info(f"[Backend] WebSocket 连接已接受: channel_name={self.channel_name}")
        
        # redis 连接池（推荐设置 decode_responses=True，否则读到的是 bytes）
        try:
            self.redis = aioredis.from_url(
                REDIS_URL, decode_responses=True
            )
            logger.info(f"[Backend] Redis 连接已建立: channel_name={self.channel_name}")
        except Exception as e:
            logger.error(f"[Backend] Redis 连接失败: {str(e)}, channel_name={self.channel_name}")
            await self.send(json.dumps({"error": f"Redis 连接失败: {str(e)}"}))

    async def disconnect(self, close_code):
        logger.info(f"[Backend] WebSocket 连接已断开: channel_name={self.channel_name}, close_code={close_code}")
        if hasattr(self, 'redis') and self.redis:
            try:
                await self.redis.close()
                logger.info(f"[Backend] Redis 连接已关闭: channel_name={self.channel_name}")
            except Exception as e:
                logger.error(f"[Backend] Redis 关闭失败: {str(e)}, channel_name={self.channel_name}")

    async def receive(self, text_data):
        """
        前端发来的进度百分比，如 {"progress": 40}
        """
        logger.info(f"[Backend] 收到前端消息: channel_name={self.channel_name}, 数据长度={len(text_data)}字节")
        try:
            data = json.loads(text_data)
            logger.debug(f"[Backend] 解析前端数据: channel_name={self.channel_name}, 数据={data}")
            
            progress = data.get("progress")
            window_sec = data.get("window_sec", 10)  # 获取窗口时间参数
            
            if progress is None:
                logger.warning(f"[Backend] 无效的进度数据: channel_name={self.channel_name}, progress=None")
                await self.send(json.dumps({"error": "invalid progress"}))
                return
            
            logger.info(f"[Backend] 处理进度数据: channel_name={self.channel_name}, progress={progress}, window_sec={window_sec}")
            
            # key 用客户端 IP + port 可能会重复，建议用 channel_name 保证唯一
            session_key = f"progress:{self.channel_name}"
            await self.redis.set(session_key, progress)
            logger.info(f"[Backend] 进度数据已保存到 Redis: key={session_key}, value={progress}")
            
            # 异步查询 Influx
            logger.info(f"[Backend] 开始异步查询 InfluxDB: channel_name={self.channel_name}, progress={progress}")
            asyncio.create_task(query_influx_async(progress, window_sec, self))
            
        except json.JSONDecodeError as e:
            logger.error(f"[Backend] 消息解析失败: channel_name={self.channel_name}, 错误={str(e)}")
            await self.send(json.dumps({"error": f"消息格式错误: {str(e)}"}))
        except Exception as e:
            logger.error(f"[Backend] 处理消息时发生异常: channel_name={self.channel_name}, 错误={str(e)}")
            await self.send(json.dumps({"error": f"处理失败: {str(e)}"}))

    async def send_query_result(self, result):
        """被 task 调用，推送结果到前端"""
        try:
            logger.info(f"[Backend] 准备发送 InfluxDB 查询结果到前端: channel_name={self.channel_name}, 结果长度={len(str(result))}字节")
            await self.send(json.dumps(result))
            logger.info(f"[Backend] 查询结果已发送到前端: channel_name={self.channel_name}")
        except Exception as e:
            logger.error(f"[Backend] 发送结果到前端失败: channel_name={self.channel_name}, 错误={str(e)}")
