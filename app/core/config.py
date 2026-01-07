"""
Configuration settings for the dashboard application.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 30
    DB_MAX_OVERFLOW: int = 50
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True
    DB_ECHO: bool = False
    DB_ECHO_POOL: bool = False

    # Application
    APP_NAME: str = "Dashboard API"
    DEBUG: bool = False
    VERSION: str = "1.0.0"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "structured"  # Options: structured, json

    # Cache
    CACHE_TTL_DASHBOARD: int = 10
    CACHE_TTL_LIST: int = 30
    CACHE_TTL_DEFAULT: int = 300
    CACHE_BACKEND: str = "memory"
    CACHE_NAMESPACE: str = "dashboard_api"
    CACHE_ENDPOINT: str = "redis://localhost:6379"
    CACHE_TIMEOUT: int = 5

    # N8N Configuration
    N8N_API_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlYjZmN2I4MC0xOTQ1LTQzNjEtODQ0MS0xYTkzMzAxNDA5MmEiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzY1Mjc3NjI1LCJleHAiOjE3Njc4NDg0MDB9.b5GNKkLuYSw-gz09EfJF9Tvlkd_usC3CvIrCBady18Q"
    N8N_BASE_URL: str = "http://172.191.171.71:5678/api/v1"
    N8N_TIMEOUT: float = 30.0

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Validate database URL uses asyncpg driver."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use asyncpg driver: postgresql+asyncpg://..."
            )
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v

    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format is valid."""
        valid_formats = ["structured", "json"]
        v = v.lower()
        if v not in valid_formats:
            raise ValueError(f"LOG_FORMAT must be one of {valid_formats}")
        return v

    @field_validator("DB_POOL_SIZE")
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        """Validate pool size is reasonable."""
        if v < 5 or v > 100:
            raise ValueError("DB_POOL_SIZE must be between 5 and 100")
        return v

    @field_validator("DB_MAX_OVERFLOW")
    @classmethod
    def validate_max_overflow(cls, v: int) -> int:
        """Validate max overflow is reasonable."""
        if v < 10 or v > 200:
            raise ValueError("DB_MAX_OVERFLOW must be between 10 and 200")
        return v

    @field_validator("CACHE_TTL_DEFAULT")
    @classmethod
    def validate_cache_ttl_default(cls, v: int) -> int:
        """Validate default cache TTL is reasonable."""
        if v < 10 or v > 86400:  # 1 second to 24 hours
            raise ValueError("CACHE_TTL_DEFAULT must be between 10 and 86400")
        return v

    @field_validator("CACHE_BACKEND")
    @classmethod
    def validate_cache_backend(cls, v: str) -> str:
        """Validate cache backend is supported."""
        valid_backends = ["memory", "redis", "memcached"]
        v = v.lower()
        if v not in valid_backends:
            raise ValueError(f"CACHE_BACKEND must be one of {valid_backends}")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
