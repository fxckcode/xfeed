"""Configuration loading and validation for xfeed."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class Config(BaseModel):
    """Application configuration loaded from a YAML file."""

    vault_path: str
    x_handle: str
    firecrawl_url: str
    keywords: list[str]
    max_tweets_per_source: int
    cron_interval: str

    @field_validator("vault_path")
    @classmethod
    def expand_vault_path(cls, v: str) -> str:
        return str(Path(v).expanduser())

    @field_validator("x_handle")
    @classmethod
    def strip_at_symbol(cls, v: str) -> str:
        return v.lstrip("@")

    @field_validator("max_tweets_per_source")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_tweets_per_source must be >= 1")
        return v


REQUIRED_FIELDS = {"vault_path", "x_handle", "firecrawl_url", "keywords"}


def load_config(path: str) -> Config:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML config file.

    Returns:
        A validated Config instance.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        ValueError: If required fields are missing.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        data: dict = yaml.safe_load(f) or {}

    missing = REQUIRED_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"Missing required config fields: {sorted(missing)}")

    return Config(**data)
