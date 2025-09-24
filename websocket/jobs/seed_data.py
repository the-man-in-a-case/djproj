import os
import time
import random
import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision

url = os.getenv("INFLUX_URL")
token = os.getenv("INFLUX_TOKEN")
org = os.getenv("INFLUX_ORG")
bucket = os.getenv("INFLUX_BUCKET")

if not all([url, token, org, bucket]):
    print("错误: 缺少必要的环境变量")
    print(f"INFLUX_URL: {url}")
    print(f"INFLUX_TOKEN: {'已设置' if token else '未设置'}")
    print(f"INFLUX_ORG: {org}")
    print(f"INFLUX_BUCKET: {bucket}")
    exit(1)

print(f"连接到InfluxDB: {url}")
print(f"组织: {org}, Bucket: {bucket}")

try:
    client = InfluxDBClient(url=url, token=token, org=org)
    write_api = client.write_api()
    
    now = datetime.datetime.utcnow()
    print("开始写入测试数据...")
    
    # 写入一小时的数据点
    for i in range(3600):
        point = Point("demo") \
            .field("value", random.randint(0, 100)) \
            .time(now - datetime.timedelta(seconds=3600 - i), WritePrecision.S)
        write_api.write(bucket, org, point)
        
        # 每100个点显示一次进度
        if i % 100 == 0:
            print(f"已写入 {i}/3600 个数据点")
        
        time.sleep(0.01)  # 模拟写入速率
    
    print("数据写入完成!")
    
except Exception as e:
    print(f"写入数据时发生错误: {str(e)}")
finally:
    client.close()
