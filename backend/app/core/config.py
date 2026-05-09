from typing import Any, List, Optional, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "EduTrack"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # development | staging | production
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    LOGGING_LEVEL: str = "INFO"
    DB_ECHO: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters for security")
        return v

    # Database
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_PORT: str = "5432"
    SQLALCHEMY_DATABASE_URI: Optional[str] = None
    REDIS_URL: Optional[str] = None
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND_URL: Optional[str] = None
    OLLAMA_BASE_URL: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def assemble_runtime_urls(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        values = dict(data)

        if not values.get("SQLALCHEMY_DATABASE_URI"):
            if values.get("DATABASE_URL"):
                values["SQLALCHEMY_DATABASE_URI"] = values["DATABASE_URL"]
            elif all([
                values.get("POSTGRES_USER"),
                values.get("POSTGRES_PASSWORD"),
                values.get("POSTGRES_DB"),
                values.get("POSTGRES_SERVER"),
            ]):
                values["SQLALCHEMY_DATABASE_URI"] = (
                    f"postgresql+asyncpg://{values.get('POSTGRES_USER')}:"
                    f"{values.get('POSTGRES_PASSWORD')}@{values.get('POSTGRES_SERVER')}:"
                    f"{values.get('POSTGRES_PORT', '5432')}/{values.get('POSTGRES_DB')}"
                )
            else:
                raise ValueError(
                    "PostgreSQL configuration is required. Set SQLALCHEMY_DATABASE_URI "
                    "or all POSTGRES_* environment variables."
                )

        redis_url = values.get("REDIS_URL") or "redis://localhost:6379/0"
        values.setdefault("CELERY_BROKER_URL", redis_url)

        if not values.get("CELERY_RESULT_BACKEND_URL"):
            if redis_url.endswith("/0"):
                values["CELERY_RESULT_BACKEND_URL"] = f"{redis_url[:-2]}/1"
            else:
                values["CELERY_RESULT_BACKEND_URL"] = redis_url

        return values

    # External Services
    OPENAI_API_KEY: Optional[str] = None
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    OLLAMA_MODEL: Optional[str] = None
    OLLAMA_FALLBACK_MODELS: Optional[str] = None
    GTK_RUNTIME_BIN: Optional[str] = None
    AI_INSIGHT_QUEUE_WORKERS: int = 1
    AI_INSIGHT_QUEUE_MAX_SIZE: int = 1000
    AI_INSIGHTS_V2_WORKER_CONCURRENCY: int = 4

    # OTP security controls
    OTP_MAX_VERIFY_ATTEMPTS: int = 5
    OTP_LOCK_MINUTES: int = 15
    OTP_REQUEST_COOLDOWN_SECONDS: int = 30
    OTP_MAX_REQUESTS_PER_10_MIN: int = 5
    OTP_MAX_VERIFY_ATTEMPTS_PER_10_MIN: int = 20
    ENABLE_MOCK_SMS_OUTPUT: bool = False

    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        case_sensitive=True, 
        env_file=(".env", "backend/.env", "../.env"),
        env_file_encoding="utf-8"
    )


settings = Settings()
