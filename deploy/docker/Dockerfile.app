FROM python:3.10-alpine
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# 配置国内pip镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

COPY deploy/docker/requirements.app.txt requirements.txt
RUN pip install -r requirements.txt
COPY backend /app/backend
COPY frontend /app/static
WORKDIR /app/backend
EXPOSE 8000
# CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "project.asgi:application"]
CMD ["sleep", "infinity"]
