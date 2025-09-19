#!/usr/bin/env python
import os
import json
import redis
from time import sleep

# 获取Redis配置 - 与项目中使用的配置保持一致
REDIS_URL = os.getenv("WORKER_RESULT_REDIS", "redis://redis.djproj.svc.cluster.local:6379/2")

# 定义要搜索的键前缀
PROJECT_KEY_PREFIXES = ["project:", "celery-task-meta-"]


def connect_to_redis():
    """连接到Redis服务器并返回连接对象"""
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()  # 测试连接
        print(f"✅ 成功连接到Redis: {REDIS_URL}")
        return r
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        exit(1)


def scan_redis_keys(r, pattern="*"):
    """扫描Redis中的键，支持模式匹配"""
    keys = []
    cursor = 0
    while True:
        cursor, partial_keys = r.scan(cursor, pattern=pattern, count=100)
        keys.extend(partial_keys)
        if cursor == 0:
            break
    return keys


def print_key_value(r, key):
    """打印指定键的值，并尝试解析JSON格式"""
    try:
        # 获取键的类型
        key_type = r.type(key)
        
        if key_type == "string":
            value = r.get(key)
            print(f"🔑 键: {key} (字符串)")
            try:
                # 尝试解析为JSON
                json_value = json.loads(value)
                print(f"📝 值: {json.dumps(json_value, indent=2, ensure_ascii=False)}")
            except (json.JSONDecodeError, TypeError):
                print(f"📝 值: {value}")
                
        elif key_type == "hash":
            value = r.hgetall(key)
            print(f"🔑 键: {key} (哈希)")
            # 尝试解析每个哈希字段的值
            for field, field_value in value.items():
                try:
                    json_value = json.loads(field_value)
                    print(f"  ├─ {field}: {json.dumps(json_value, indent=2, ensure_ascii=False)}")
                except (json.JSONDecodeError, TypeError):
                    print(f"  ├─ {field}: {field_value}")
            print("  └─ (哈希结束)")
            
        elif key_type == "list":
            value = r.lrange(key, 0, -1)
            print(f"🔑 键: {key} (列表，长度: {len(value)})")
            for i, item in enumerate(value):
                try:
                    json_value = json.loads(item)
                    print(f"  ├─ [{i}]: {json.dumps(json_value, indent=2, ensure_ascii=False)}")
                except (json.JSONDecodeError, TypeError):
                    print(f"  ├─ [{i}]: {item}")
            print("  └─ (列表结束)")
            
        elif key_type == "set":
            value = r.smembers(key)
            print(f"🔑 键: {key} (集合，大小: {len(value)})")
            for i, item in enumerate(value):
                print(f"  ├─ [{i}]: {item}")
            print("  └─ (集合结束)")
            
        elif key_type == "zset":
            value = r.zrange(key, 0, -1, withscores=True)
            print(f"🔑 键: {key} (有序集合，大小: {len(value)})")
            for i, (item, score) in enumerate(value):
                print(f"  ├─ [{i}]: {item} (分数: {score})")
            print("  └─ (有序集合结束)")
            
        else:
            print(f"🔑 键: {key} (未知类型: {key_type})")
            
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 获取键 {key} 的值时出错: {e}")


def print_all_messages():
    """打印Redis中所有相关的消息"""
    r = connect_to_redis()
    
    # 扫描所有键
    all_keys = []
    for prefix in PROJECT_KEY_PREFIXES:
        pattern = f"{prefix}*"
        keys = scan_redis_keys(r, pattern)
        all_keys.extend(keys)
        print(f"🔍 找到 {len(keys)} 个匹配 '{pattern}' 的键")
    
    # 去重
    all_keys = list(set(all_keys))
    print(f"📊 总共找到 {len(all_keys)} 个唯一键")
    
    if not all_keys:
        print("⚠️ 没有找到任何键")
        return
    
    # 按键名排序
    all_keys.sort()
    
    print("\n🚀 开始打印键和值...\n")
    
    # 打印每个键的值
    for key in all_keys:
        print_key_value(r, key)
    
    print(f"✅ 所有 {len(all_keys)} 个键已打印完毕")


def monitor_mode():
    """监控模式 - 实时监听并打印新消息"""
    r = connect_to_redis()
    
    # 创建一个新的发布/订阅对象
    ps = r.pubsub(ignore_subscribe_messages=True)
    
    # 订阅所有项目频道
    ps.psubscribe("project:*:worker_events")
    print("✅ 已订阅所有项目事件频道")
    
    try:
        for message in ps.listen():
            if message:
                print("\n📨 收到新消息:")
                print(f"  频道: {message['channel']}")
                try:
                    data = json.loads(message['data'])
                    print(f"  数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                except (json.JSONDecodeError, TypeError):
                    print(f"  数据: {message['data']}")
                print("=" * 60)
    except KeyboardInterrupt:
        print("\n🛑 监控已停止")
    finally:
        ps.close()


if __name__ == "__main__":
    print("📱 Redis消息查看器")
    print("1. 打印所有现有消息")
    print("2. 进入监控模式(实时监听新消息)")
    
    choice = input("请选择操作 (1/2): ")
    
    if choice == "1":
        print_all_messages()
    elif choice == "2":
        monitor_mode()
    else:
        print("❌ 无效选择，退出")