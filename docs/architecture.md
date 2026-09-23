# Architecture

Orbit is a real-time order management & inventory platform, built as two
services to demonstrate both a Django/DRF modular monolith and a genuine
polyglot microservice extracted from it:

- **`core_api`** (Django 5 + DRF + Channels + Celery) - users, catalog,
  inventory, and orders. Owns the system of record (PostgreSQL).
- **`notification_service`** (FastAPI) - consumes domain events off Kafka
  and pushes them to WebSocket clients. Owns nothing but a short-lived Redis
  cache of recent notifications.

```
                         ┌───────────────────────────────┐
                         │            nginx              │
                         └───────────────┬───────────────┘
                     ┌───────────────────┼───────────────────┐
                     ▼                                       ▼
        ┌─────────────────────────┐          ┌───────────────────────────────┐
        │   core_api (Django)     │          │  notification_service         │
        │  DRF + Channels (WS)    │  Kafka   │  FastAPI                      │
        │  - users / catalog      │ ───────▶ │  - aiokafka consumer          │
        │  - orders / inventory   │  events  │  - native WebSocket endpoint  │
        └─────────┬───────┬───────┘          └───────────────┬───────────────┘
                  │       │                                  │
         ┌────────┘       └────────┐                         │
         ▼                         ▼                         ▼
 ┌───────────────┐        ┌────────────────┐         ┌────────────────┐
 │  PostgreSQL   │        │  Redis          │◀───────▶│  Redis (shared) │
 │  (system of   │        │  cache/broker/  │         │  notif. history │
 │   record)     │        │  channel layer  │         └────────────────┘
 └───────────────┘        └────────┬────────┘
                                    ▼
                          ┌──────────────────┐
                          │  Celery worker /  │
                          │  Celery Beat      │
                          └──────────────────┘
```

## Why a modular monolith *and* a microservice

`core_api` is deliberately organized as a **modular monolith**: `users`,
`catalog`, `inventory`, `orders` are separate Django apps that only talk to
each other through Celery tasks, Django signals, and Kafka events - never by
directly importing each other's models across a service boundary in a way
that would be hard to undo. That's what makes `notification_service` a
believable extraction rather than a toy: it's a domain (turning events into
real-time pushes) that had *no* reason to share a database or a deploy
cycle with the commerce core, so it was built as its own FastAPI service
from day one, communicating only via Kafka.

The trade-off is explicit: everything that touches the order/payment/stock
data model stays in one Postgres-backed service so multi-table transactions
(placing an order = reserve stock + create order + order items, atomically)
don't become a distributed-transaction problem. Anything that is naturally
event-driven and doesn't need transactional consistency with that core data
(notifications, and eventually analytics, search indexing, etc.) is a
candidate to peel off the same way `notification_service` was.

## Request/data flow: placing an order

1. Client calls `POST /api/v1/orders/` with a JWT (or OAuth2) bearer token.
2. `apps.orders.services.place_order` runs inside one DB transaction:
   for each line item it calls `apps.inventory.services.reserve_stock`,
   which takes a `SELECT ... FOR UPDATE` row lock on that product's
   `StockItem` so concurrent checkouts of the same SKU serialize instead of
   racing (see `docs/architecture.md#concurrency--locking` below).
3. On commit, a `post_save` signal fires two Celery tasks: send a
   confirmation email (simulated) and broadcast the new order over the
   customer's Channels WebSocket group (`orders_<user_id>`).
4. `place_order` also publishes an `order.created` event to Kafka
   (`order-events` topic). This is fire-and-forget from core_api's point of
   view - Kafka being briefly unavailable never fails the checkout request.
5. `notification_service`'s `aiokafka` consumer picks up the event, stores
   it in Redis (recent-notification history, capped + TTL'd), and pushes it
   to any FastAPI-native WebSocket client subscribed for that customer.

## Concurrency & locking

Stock reservation (`apps/inventory/services.py`) is the one place in the
codebase where correctness under concurrent writes is load-bearing: two
customers must not both successfully reserve the last unit of a product.
`reserve_stock`/`release_stock`/`commit_stock` each run inside
`@transaction.atomic` and take a pessimistic row lock via
`StockItem.objects.select_for_update()`. Pessimistic locking was chosen over
an optimistic compare-and-swap retry loop because hot SKUs (flash sales,
low-stock items near a restock) are expected to see real contention, where a
lock held for single-digit milliseconds is cheaper than repeatedly retrying
failed writes under load.

## Caching

- Product listings (`GET /api/v1/catalog/products/`) are cached in Redis
  for 60s via `cache_page`, varying on the `Authorization` header so the
  staff-vs-customer queryset difference never leaks between users. This is
  the "handle high-throughput concurrent reads" requirement in practice:
  the read-heavy, infrequently-changing catalog absorbs traffic spikes
  without hitting Postgres on every request.
- `django-redis` backs Django's cache framework generally; Celery uses a
  separate Redis logical DB as its broker/result backend, and Channels uses
  a third as its cross-process pub/sub layer for WebSocket groups.

## Auth

Both **JWT** (`djangorestframework-simplejwt`, short-lived access + rotating
refresh tokens) and **OAuth2** (`django-oauth-toolkit`) are wired in as DRF
authentication classes simultaneously - JWT for first-party clients
(mobile/SPA), OAuth2 for third-party integrations that need scoped,
revocable tokens without sharing user credentials.

## Observability

- Structured JSON logs (`python-json-logger`) tagged with a per-request
  correlation id (`apps.common.middleware.RequestLoggingMiddleware`), shipped
  by Filebeat → Logstash → Elasticsearch (`infra/monitoring/`).
- Sentry for exception + trace capture in both services.
- A sample Grafana dashboard (`infra/monitoring/grafana/`) assuming a
  Prometheus scrape of gunicorn/uvicorn + Celery queue depth, plus
  Elasticsearch-backed panels for error rate and low-stock alerts.

## What's out of scope on purpose

Kafka and Postgres run as single-node deployments in `infra/k8s/` - fine for
a local kind/minikube cluster, explicitly not production-HA. A real
production rollout would point `DATABASE_URL` at a managed Postgres and
`KAFKA_BOOTSTRAP_SERVERS` at a managed Kafka (MSK/Confluent Cloud) or a
properly operated Strimzi cluster instead of the manifests checked in here.
