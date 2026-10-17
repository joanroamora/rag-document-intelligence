# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN python -m pip install --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    ENVIRONMENT=prod

RUN groupadd --gid 10001 appgroup && \
    useradd --uid 10001 --gid appgroup --shell /sbin/nologin --create-home appuser

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

USER appuser

EXPOSE 8080

CMD ["sh", "-c", "uvicorn rag_platform.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
