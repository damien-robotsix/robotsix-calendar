"""Tests for the settings page and standard config HTTP surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from robotsix_config import MASKED_SECRET_SENTINEL, load_config

from robotsix_calendar.api import app
from robotsix_calendar.settings import Settings

BASE_CONFIG: dict[str, Any] = {
    "radicale_url": "https://radicale.example.com",
    "radicale_username": "user",
    "radicale_password": "secret",  # pragma: allowlist secret
    "radicale_default_calendar": "Robotsix",
    "caldav_timeout": 30,
    "caldav_healthcheck_timeout": 5,
    "log_level": "INFO",
    "json_logs": False,
}


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the standard config contract at an isolated temp file."""
    path = tmp_path / "config.json"
    monkeypatch.setenv("ROBOTSIX_CONFIG_FILE", str(path))
    return path


@pytest.fixture
def client() -> TestClient:
    """Build a TestClient for the shared FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def _write_config(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestSettingsPage:
    def test_settings_page_mounts_shared_config_panel(self, client: TestClient) -> None:
        response = client.get("/settings")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "/static/robotsix-ui.css" in response.text
        assert "/static/robotsix-ui-vanilla.js" in response.text
        assert "mountConfigPanel" in response.text


class TestGetConfig:
    def test_returns_stored_config_not_schema_defaults(
        self, client: TestClient, config_path: Path
    ) -> None:
        _write_config(config_path, {"log_level": "DEBUG"})

        response = client.get("/config")

        assert response.status_code == 200
        body = response.json()
        assert body["config"] == {"log_level": "DEBUG"}
        assert body["schema"]["title"] == "Settings"
        assert body["version"] == 0

    def test_masks_secret_values(self, client: TestClient, config_path: Path) -> None:
        _write_config(
            config_path,
            {**BASE_CONFIG, "radicale_password": "hunter2"},  # pragma: allowlist secret
        )

        body = client.get("/config").json()

        assert body["config"]["radicale_password"] == MASKED_SECRET_SENTINEL
        assert body["config"]["radicale_password"] != "hunter2"


class TestPutConfig:
    def test_persists_update_and_survives_reload(
        self, client: TestClient, config_path: Path
    ) -> None:
        _write_config(config_path, BASE_CONFIG)

        response = client.put("/config", json={"log_level": "DEBUG"})

        assert response.status_code == 200
        assert response.json()["config"]["log_level"] == "DEBUG"

        # A fresh process reading the same file sees the update.
        loaded = load_config(Settings, config_path)
        assert loaded.log_level == "DEBUG"

    def test_preserves_secrets_not_resubmitted(
        self, client: TestClient, config_path: Path
    ) -> None:
        _write_config(config_path, {**BASE_CONFIG, "radicale_password": "hunter2"})

        response = client.put("/config", json={"log_level": "WARNING"})

        assert response.status_code == 200
        body = response.json()
        assert body["config"]["radicale_password"] == MASKED_SECRET_SENTINEL
        stored = json.loads(config_path.read_text(encoding="utf-8"))
        assert stored["radicale_password"] == "hunter2"

    def test_invalid_update_returns_422(
        self, client: TestClient, config_path: Path
    ) -> None:
        _write_config(config_path, BASE_CONFIG)

        response = client.put("/config", json={"log_level": "NOT_A_LEVEL"})

        assert response.status_code == 422
        assert "log_level" in response.json()["detail"]


class TestConfigHistory:
    def test_versions_and_rollback(self, client: TestClient, config_path: Path) -> None:
        _write_config(config_path, {**BASE_CONFIG, "log_level": "INFO"})

        assert client.put("/config", json={"log_level": "DEBUG"}).status_code == 200

        versions = client.get("/config/versions").json()["versions"]
        assert len(versions) >= 2
        # Newest first.
        assert versions[0]["version"] > versions[-1]["version"]
        assert "log_level" in versions[0]["changed_keys"]

        rollback = client.post(
            "/config/rollback", json={"version": versions[-1]["version"]}
        )
        assert rollback.status_code == 200
        assert rollback.json()["config"]["log_level"] == "INFO"

        reloaded = load_config(Settings, config_path)
        assert reloaded.log_level == "INFO"

    def test_rollback_unknown_version_returns_422(
        self, client: TestClient, config_path: Path
    ) -> None:
        _write_config(config_path, BASE_CONFIG)

        response = client.post("/config/rollback", json={"version": 999})

        assert response.status_code == 422
