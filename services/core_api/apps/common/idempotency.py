"""Idempotency-key support for unsafe (POST) endpoints.

A client that places an order and never receives the response (timeout,
dropped connection) can't tell whether the order was created or not, and a
naive retry would create a second order and reserve stock twice. Callers
that care can send an ``Idempotency-Key`` header; a repeated request with
the same key + user returns the original response instead of re-running the
handler.

Built on Django's cache framework rather than a raw Redis client so it works
against whatever `CACHES["default"]` is configured (LocMemCache in tests,
django-redis in dev/prod) without a second code path. ``cache.add`` gives us
the atomic "set if absent" needed to close the race between two identical
requests arriving at the same instant.
"""

from django.core.cache import cache

_LOCK_TTL_SECONDS = 60  # generous upper bound on how long one request may take
_RESULT_TTL_SECONDS = 60 * 60 * 24  # replay window for a completed response


def _cache_key(scope: str, user_id, idempotency_key: str) -> str:
    return f"idempotency:{scope}:{user_id}:{idempotency_key}"


def begin(scope: str, user_id, idempotency_key: str):
    """Call before running the handler. Returns a tuple:

    - ("proceed", None): no prior attempt with this key; caller should run
      the handler and then call `complete()`.
    - ("in_progress", None): another request with this key is currently
      being handled (or crashed without completing) - caller should
      respond 409 without doing any work.
    - ("replay", cached): a previous attempt already finished - caller
      should return `cached` (a dict with "status_code" and "body")
      instead of re-running the handler.
    """
    key = _cache_key(scope, user_id, idempotency_key)
    existing = cache.get(key)
    if existing is not None:
        if existing.get("state") == "done":
            return "replay", existing["result"]
        return "in_progress", None

    if cache.add(key, {"state": "in_progress"}, timeout=_LOCK_TTL_SECONDS):
        return "proceed", None
    # Lost the race between the get() above and this add() - treat exactly
    # like finding it already in progress.
    return "in_progress", None


def complete(scope: str, user_id, idempotency_key: str, status_code: int, body: dict) -> None:
    cache.set(
        _cache_key(scope, user_id, idempotency_key),
        {"state": "done", "result": {"status_code": status_code, "body": body}},
        timeout=_RESULT_TTL_SECONDS,
    )


def abandon(scope: str, user_id, idempotency_key: str) -> None:
    """Call if the handler failed to run at all (e.g. validation error) so
    the client can safely retry with the same key immediately."""
    cache.delete(_cache_key(scope, user_id, idempotency_key))
