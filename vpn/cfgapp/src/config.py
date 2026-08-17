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
    xray_mldsa65seed: str = Field(default="")
    xray_privatekey: str = Field(default="")
    xray_publickey: str = Field(default="")
    xray_verify: str = Field(default="")
    base_url: str = Field(default="")

    # RULE-SET / NETSET list cache (see listcache.py). The directory is a docker
    # volume, so the cache survives the deploy's --force-recreate; a fresh copy
    # is only fetched once a day, and a copy up to a month old still beats
    # failing the request when the upstream is down.
    list_cache_dir: str = Field(default="/cache/lists")
    list_cache_fresh_seconds: int = Field(default=24 * 60 * 60)
    list_cache_max_age_seconds: int = Field(default=30 * 24 * 60 * 60)

    # Lists we publish ourselves are edited by hand (the per-site routing
    # workflow) and must reach clients in minutes, not a day. They still get the
    # full max_age fallback — only the "do not even ask" window is short.
    # config_host / api_host are added to this set automatically.
    list_cache_own_hosts: str = Field(default="s.dimonb.com")
    list_cache_own_fresh_seconds: int = Field(default=60)

    # Logging
    log_level: str = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, env_prefix="", extra="ignore"
    )


# Global settings instance
settings = Settings()
