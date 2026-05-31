import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    azure_openai_api_key: str = Field(default="")
    azure_openai_endpoint: str = Field(default="")
    azure_openai_api_version: str = Field(default="2025-04-14")
    azure_openai_deployment: str = Field(default="")

    github_webhook_secret: str = Field(default="")
    github_token: str | None = Field(default=None)

    database_url: str = Field(default="sqlite+aiosqlite:///./norn.db")
    ruff_executable: str = Field(default="ruff")
    norn_app_base_url: str = Field(default="http://localhost:5173")

    log_level: str = Field(default="INFO")
    payload_size_limit_bytes: int = Field(default=1_048_576)

    norn_orchestration_mode: Literal["fixed", "group_chat"] = Field(default="group_chat")
    norn_group_chat_max_iterations: int = Field(default=7, ge=3, le=12)

    # ログイン: ユーザーは DB（users テーブル）のみ。
    norn_auth_secret: str = Field(default="")
    norn_auth_token_ttl_hours: int = Field(default=168, ge=1, le=24 * 30)

    # カンマ区切り。SWA 等の別オリジン UI から API を呼ぶときに設定。
    norn_cors_origins: str = Field(default="")

    @property
    def auth_jwt_secret(self) -> str:
        explicit = self.norn_auth_secret.strip()
        if explicit:
            return explicit
        cached = getattr(self, "_runtime_jwt_secret", None)
        if cached is None:
            cached = secrets.token_urlsafe(32)
            object.__setattr__(self, "_runtime_jwt_secret", cached)
        return cached

    @property
    def llm_configured(self) -> bool:
        return bool(self.azure_openai_api_key.strip() and self.azure_openai_endpoint.strip())

    @property
    def azure_openai_deployment_name(self) -> str:
        return self.azure_openai_deployment or "gpt-4.1-mini"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.norn_cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
