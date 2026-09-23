from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NOTIF_", env_file=".env", extra="ignore")

    service_name: str = "notification-service"
    http_port: int = 8001

    redis_url: str = "redis://localhost:6379/3"
    notification_ttl_seconds: int = 60 * 60 * 24 * 7  # keep a week of history per user

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topics: str = "order-events,inventory-events"
    kafka_consumer_group: str = "notification-service"

    sentry_dsn: str = ""

    @property
    def kafka_topic_list(self) -> list[str]:
        return [t.strip() for t in self.kafka_topics.split(",") if t.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
