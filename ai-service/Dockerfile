FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
    PYTHONPATH=/app

WORKDIR /app

COPY ai-service/requirements.production.txt /tmp/requirements.production.txt
RUN pip install --no-cache-dir -r /tmp/requirements.production.txt
# PyPI's Linux torch build pulls CUDA libraries. This server is CPU-only, so
# install the official CPU wheel after its ordinary dependencies are present.
RUN pip install --no-cache-dir --no-deps --index-url https://download.pytorch.org/whl/cpu torch==2.11.0+cpu

COPY ai-service /app

EXPOSE 8090
CMD ["python", "-m", "uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090"]
