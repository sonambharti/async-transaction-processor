from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    processing_delay_seconds: float = 30
    lease_seconds: float = 60
    poll_interval_seconds: float = 1
    worker_concurrency: int = 200
    db_command_timeout_seconds: float = 0.4
    worker_db_timeout_seconds: float = 5
    api_pool_size: int = 10
    worker_pool_size: int = 3
    max_body_bytes: int = 16_384
    cors_origins: str = ""

    @model_validator(mode="after")
    def lease_outlasts_delay(self) -> Self:
        if self.lease_seconds <= self.processing_delay_seconds:
            raise ValueError("LEASE_SECONDS must be longer than PROCESSING_DELAY_SECONDS")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
