"""Tests for config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config import Config, load_config


def test_load_config_success(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    data = {
        "vault_path": "~/vault",
        "x_handle": "@testuser",
        "firecrawl_url": "http://localhost:3002",
        "keywords": ["AI", "tech"],
        "max_tweets_per_source": 20,
        "cron_interval": "*/30 * * * *",
    }
    with open(config_path, "w") as f:
        yaml.dump(data, f)

    config = load_config(str(config_path))

    assert config.x_handle == "testuser"
    assert config.vault_path == str(Path("~/vault").expanduser())
    assert config.firecrawl_url == "http://localhost:3002"
    assert config.keywords == ["AI", "tech"]
    assert config.max_tweets_per_source == 20
    assert config.cron_interval == "*/30 * * * *"


def test_load_config_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path/config.yaml")


def test_load_config_missing_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "partial.yaml"
    with open(config_path, "w") as f:
        yaml.dump({"x_handle": "testuser"}, f)

    with pytest.raises(ValueError, match="Missing required config fields"):
        load_config(str(config_path))


def test_vault_path_expansion() -> None:
    config = Config(
        vault_path="~/my_vault",
        x_handle="user",
        firecrawl_url="http://localhost:3002",
        keywords=["tech"],
        max_tweets_per_source=10,
        cron_interval="0 * * * *",
    )
    assert config.vault_path == str(Path("~/my_vault").expanduser())
    assert "~" not in config.vault_path


def test_x_handle_strips_at() -> None:
    config = Config(
        vault_path="/tmp/vault",
        x_handle="@realuser",
        firecrawl_url="http://localhost:3002",
        keywords=["tech"],
        max_tweets_per_source=10,
        cron_interval="0 * * * *",
    )
    assert config.x_handle == "realuser"


def test_max_tweets_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_tweets_per_source must be >= 1"):
        Config(
            vault_path="/tmp/vault",
            x_handle="user",
            firecrawl_url="http://localhost:3002",
            keywords=["tech"],
            max_tweets_per_source=0,
            cron_interval="0 * * * *",
        )
