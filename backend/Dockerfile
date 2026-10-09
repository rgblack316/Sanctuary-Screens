FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt

COPY *.py ./
COPY seed ./seed
RUN mkdir -p /app/data/idle

CMD ["sh", "-c", "exec uvicorn server:app --host ${BACKEND_BIND:-127.0.0.1} --port ${BACKEND_PORT:-8092} --proxy-headers --forwarded-allow-ips=127.0.0.1"]
