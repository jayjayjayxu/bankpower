FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
    PYTHONPATH=/app

WORKDIR /app

COPY ai-service/requirements.production.txt /tmp/requirements.production.txt
RUN pip install --no-cache-dir -r /tmp/requirements.production.txt

COPY ai-service /app

EXPOSE 8090
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
