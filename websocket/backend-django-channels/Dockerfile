FROM python:3.10-alpine

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV DJANGO_SETTINGS_MODULE=server.settings
EXPOSE 8000
# 使用 daphne 运行 ASGI
# CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "server.asgi:application"]
CMD ["tail", "-f", "/dev/null"]
