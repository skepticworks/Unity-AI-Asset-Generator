ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BIND_HOST=0.0.0.0 \
    MODEL_STORAGE_DIRECTORY=/data/models \
    OUTPUT_DIRECTORY=/data/generated

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install .

RUN useradd --create-home --uid 10001 appuser && mkdir -p /data/models /data/generated \
    && chown -R appuser:appuser /app /data
USER appuser

VOLUME ["/data/models", "/data/generated"]
EXPOSE 8000
CMD ["unity-ai-assets"]
