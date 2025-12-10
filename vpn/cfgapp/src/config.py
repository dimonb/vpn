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

    # Network compaction settings
    enable_compaction: bool = Field(default=True)
    compact_target_max: int = Field(default=200)
    compact_min_prefix_v4: int = Field(default=11)
    compact_min_prefix_v6: int = Field(default=32)

    # Server configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Proxy configuration
    proxy_config: str = Field(default="")
    obfs_password: str = Field(default="")
    hysteria2_port: int = Field(default=47012)
    hysteria2_v2_port: int = Field(default=47013)
    vless_port: int = Field(default=8443)
    https_port: int = Field(default=443)
    reality_private_key: str = Field(default="")
    reality_public_key: str = Field(default="")
    reality_short_id: str = Field(default="c047f3e99c90ff71")
    base_url: str = Field(default="")

    # Logging
    log_level: str = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, env_prefix="", extra="ignore"
    )


# Global settings instance
settings = Settings()


