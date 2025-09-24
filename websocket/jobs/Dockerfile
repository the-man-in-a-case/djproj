FROM python:3.10-alpine

# 设置工作目录
WORKDIR /app

# 复制Python脚本到容器中
COPY seed_data.py /app/

# 安装必要的Python包
RUN pip install --no-cache-dir influxdb-client

# 设置容器启动时执行的命令
CMD ["python", "/app/seed_data.py"]