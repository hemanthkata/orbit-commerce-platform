FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev default-libmysqlclient-dev pkg-config curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/ requirements/
# dev.txt (includes prod deps + test/lint tooling) is the default so
# `docker compose up` and `make test` work out of the box; the CI image
# build passes --build-arg REQUIREMENTS_FILE=requirements/prod.txt.
ARG REQUIREMENTS_FILE=requirements/dev.txt
RUN pip install --no-cache-dir -r ${REQUIREMENTS_FILE}

COPY . .

RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD curl -f http://localhost:8000/health/ || exit 1

# gunicorn supervises worker processes; each worker runs uvicorn's ASGI
# event loop so both plain HTTP and the Channels WebSocket endpoints
# (/ws/orders/) are served from the same process model.
CMD ["gunicorn", "config.asgi:application", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "4"]
