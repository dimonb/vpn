"""Configuration settings for the CFG application."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API configuration
    config_host: str = Field(default="")
    api_host: str = Field(default="")

    # Authentication
    salt: str = Field(default="")

    # IP aggregation settings
    ipv4_block_prefix: int = Field(default=18)
    ipv6_block_prefix: int = Field(default=32)

    # Server configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Proxy configuration
    proxy_config: str = Field(default="")
    obfs_password: str = Field(default="")

    # Logging
    log_level: str = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        env_prefix="",
        extra="ignore"
    )


# Global settings instance
settings = Settings()
