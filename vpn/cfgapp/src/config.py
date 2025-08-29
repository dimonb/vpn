"""Configuration settings for the CFG application."""


from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API configuration
    config_host: str = Field(default="", env="CONFIG_HOST")
    api_host: str = Field(default="", env="API_HOST")

    # Authentication
    salt: str = Field(default="", env="SALT")

    # IP aggregation settings
    ipv4_block_prefix: int = Field(default=18, env="IPV4_BLOCK_PREFIX")
    ipv6_block_prefix: int = Field(default=32, env="IPV6_BLOCK_PREFIX")

    # Server configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
