# Orbit Commerce Platform

A real-time order management & inventory platform, built to exercise the
full backend stack of a modern Python/Django shop: **Django + DRF** as the
transactional core, a **FastAPI** microservice for real-time notifications,
**PostgreSQL**, **Redis**, **Celery/Celery Beat**, **Kafka**, **Django
Channels + native FastAPI WebSockets**, JWT + OAuth2 auth, and a full
Docker/Kubernetes deployment path with ELK/Grafana/Sentry observability
wired in.

Two services:

| Service | Stack | Responsibility |
|---|---|---|
| [`services/core_api`](services/core_api) | Django 5, DRF, Channels, Celery | Users, catalog, inventory, orders - the system of record |
| [`services/notification_service`](services/notification_service) | FastAPI, aiokafka | Consumes Kafka domain events, pushes real-time WebSocket notifications |

See [`docs/architecture.md`](docs/architecture.md) for the full design
rationale (why two services, how stock-reservation locking works, the
event flow for placing an order) and
[`docs/api-versioning.md`](docs/api-versioning.md) for API design/versioning
conventions.

## Why it's built this way

`core_api` is a **modular monolith** - `users`, `catalog`, `inventory`, and
`orders` are independent Django apps that only communicate through Celery
tasks, Django signals, and Kafka events, never by reaching into each other's
models directly. That boundary is what let `notification_service` be pulled
out as a genuinely separate, differently-stacked (FastAPI, not Django)
microservice communicating purely over Kafka - the same pattern used to
plan which piece of a monolith is safe to extract next in a real system.

## Feature → requirement map

| Requirement | Where |
|---|---|
| Django, DRF, FastAPI | `services/core_api` (Django/DRF), `services/notification_service` (FastAPI) |
| PostgreSQL / MySQL, schema design, query optimization, locking | `apps/inventory/services.py` (`select_for_update` stock reservation), swap `DATABASE_URL` for MySQL - `mysqlclient` is already in `requirements/base.txt` |
| Redis caching | `django-redis` cache backend, cached product listing (`apps/catalog/views.py`) |
| Celery + Celery Beat | `apps/orders/tasks.py` (async email + WS broadcast), daily sales report on a Beat schedule (`seed_beat_schedule` management command) |
| Kafka, cross-service messaging | `apps/common/kafka.py` (producer in core_api) → `app/kafka/consumer.py` (aiokafka consumer in notification_service) |
| WebSockets, Django Channels, FastAPI native WS | `apps/orders/consumers.py` (Channels), `app/routers/ws.py` (FastAPI) |
| Microservices / modular monolith / API design | `docs/architecture.md`, `docs/api-versioning.md` |
| Gunicorn/Uvicorn + Nginx | `services/core_api/Dockerfile` (gunicorn + uvicorn worker), `infra/nginx/nginx.conf` |
| Docker / Kubernetes | `docker-compose.yml`, `infra/k8s/` |
| Swagger/OpenAPI | `drf-spectacular` at `/api/docs/`; FastAPI's built-in OpenAPI at `/docs` |
| ELK / Grafana / Sentry | `infra/monitoring/` (Filebeat, Logstash, sample dashboard), Sentry SDK init in both services |
| JWT + OAuth2 | `djangorestframework-simplejwt` + `django-oauth-toolkit`, both wired as DRF auth classes |
| Unit/integration tests, pre-commit, SonarQube | `services/core_api/tests`, `services/notification_service/tests`, `.pre-commit-config.yaml`, `sonar-project.properties` |
| Git / Agile | `.github/workflows/ci.yml`, conventional-ish commit history |

## Quickstart

```bash
cp .env.example .env
docker compose up --build
```

- Django API: http://localhost:8000/api/docs/ (Swagger) - health at `/health/`
- FastAPI notification service: http://localhost:8001/docs - health at `/health`
- Everything through the reverse proxy: http://localhost/

First-time setup, in another terminal:

```bash
make migrate
docker compose exec core-api python manage.py createsuperuser
docker compose exec core-api python manage.py seed_beat_schedule
```

Try the golden path:

```bash
# Register and grab a JWT
curl -s -X POST localhost:8000/api/v1/users/register/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"StrongPassw0rd!"}' | tee /tmp/auth.json

TOKEN=$(python -c "import json;print(json.load(open('/tmp/auth.json'))['access'])")

# Create a category/product as a superuser via /admin/, then place an order
curl -s -X POST localhost:8000/api/v1/orders/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":"<product-uuid>","quantity":1}]}'
```

Placing the order reserves stock under a row lock, fires a confirmation
email task, publishes a Kafka `order.created` event, and pushes the update
over `ws://localhost:8000/ws/orders/` (Channels) - `notification_service`
picks up the same Kafka event and re-serves it over
`ws://localhost:8001/ws/notifications/<your-user-id>`.

## Tests

```bash
make test
# or, per service:
cd services/core_api && pytest --cov=apps
cd services/notification_service && pytest
```

`core_api` tests cover the stock-reservation concurrency logic
(`tests/test_orders.py`), auth (`tests/test_users.py`), and catalog
filtering/permissions (`tests/test_catalog.py`) with `pytest-django` +
`factory_boy`. `notification_service` tests cover the WebSocket connection
manager and Kafka→recipient routing with `pytest-asyncio`, without needing a
live Kafka/Redis.

## Code quality

```bash
pre-commit install   # black, isort, flake8, bandit, detect-secrets
make lint
```

`sonar-project.properties` is set up for a SonarQube/SonarCloud scan across
both services' source and test/coverage reports (wired into
`.github/workflows/ci.yml`, which also builds both Docker images on every
push).

## Kubernetes

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
cp infra/k8s/secret.example.yaml infra/k8s/secret.yaml   # fill in real values, don't commit
kubectl apply -f infra/k8s/
```

Postgres/Kafka manifests here are single-instance, for a local kind/minikube
cluster - see the note at the end of `docs/architecture.md` on what changes
for a real production cluster.

## Repository layout

```
services/
  core_api/            Django + DRF + Channels + Celery
    config/            settings (base/dev/prod/test), asgi/wsgi, celery app
    apps/
      common/           base models, pagination, permissions, exception envelope,
                         Kafka producer, request-logging middleware, health check
      users/            custom email-based User, JWT/OAuth2-ready auth endpoints
      catalog/          categories/products, filtering, cached listing
      inventory/        stock reservation with row-level locking
      orders/           order placement/pay/cancel, Celery tasks, Channels consumer
    tests/
  notification_service/ FastAPI + aiokafka
    app/
      kafka/            Kafka consumer -> recipient routing
      ws/               native WebSocket connection manager
      models/           Redis-backed notification history
      routers/          health, notification history, websocket endpoint
    tests/
infra/
  k8s/                  Kubernetes manifests
  nginx/                reverse proxy config (HTTP + WebSocket upgrade)
  monitoring/            Filebeat, Logstash, sample Grafana dashboard
docs/
  architecture.md
  api-versioning.md
```
