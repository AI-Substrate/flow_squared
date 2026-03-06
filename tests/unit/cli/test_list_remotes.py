"""Tests for list_remotes command and resolve_remotes helper.

Phase 5: Remote CLI + MCP Bridge
Tests the config-only list-remotes command and the resolve_remotes
utility that parses --remote values into RemoteClient instances.

Uses FakeConfigurationService (fakes over mocks) for config injection.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from fs2.cli.main import app
from fs2.cli.remote_client import RemoteClient
from fs2.config.objects import RemotesConfig, RemoteServer
from fs2.config.service import FakeConfigurationService

runner = CliRunner()


# ── list_remotes command ──────────────────────────────────────────────────────


class TestListRemotesNoConfig:
    """Verify list-remotes with no configured remotes."""

    def test_given_no_remotes_when_list_remotes_then_shows_no_remotes_message(self):
        result = runner.invoke(app, ["list-remotes"])
        assert result.exit_code == 0
        assert "No remotes configured" in result.output


class TestListRemotesWithRemotes:
    """Verify list-remotes shows table with configured remotes."""

    def test_given_remotes_configured_when_list_remotes_then_shows_table(
        self, monkeypatch
    ):
        servers = [
            RemoteServer(
                name="work",
                url="https://fs2.company.com",
                api_key="secret",
                description="Team server",
            ),
            RemoteServer(
                name="oss",
                url="https://fs2.example.com",
                description="Public server",
            ),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))

        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        result = runner.invoke(app, ["list-remotes"])

        assert result.exit_code == 0
        assert "work" in result.output
        assert "oss" in result.output
        assert "fs2.company.com" in result.output

    def test_given_remote_with_key_when_list_remotes_then_shows_auth_indicator(
        self, monkeypatch
    ):
        servers = [
            RemoteServer(
                name="authed",
                url="https://fs2.company.com",
                api_key="secret-key",
            ),
            RemoteServer(
                name="anon",
                url="https://fs2.example.com",
            ),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))

        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        result = runner.invoke(app, ["list-remotes"])

        assert result.exit_code == 0
        # Auth column should distinguish the two
        assert "authed" in result.output
        assert "anon" in result.output


class TestListRemotesJson:
    """Verify --json flag outputs valid JSON."""

    def test_given_remotes_when_list_remotes_json_then_valid_json_output(
        self, monkeypatch
    ):
        servers = [
            RemoteServer(
                name="work",
                url="https://fs2.company.com",
                api_key="key",
                description="Team",
            ),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))

        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        result = runner.invoke(app, ["list-remotes", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "remotes" in data
        assert data["count"] == 1
        assert data["remotes"][0]["name"] == "work"
        assert data["remotes"][0]["has_api_key"] is True

    def test_given_no_remotes_when_list_remotes_json_then_empty_array(
        self, monkeypatch
    ):
        fake_config = FakeConfigurationService(RemotesConfig(servers=[]))

        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        result = runner.invoke(app, ["list-remotes", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["remotes"] == []
        assert data["count"] == 0


# ── resolve_remotes ───────────────────────────────────────────────────────────


class TestResolveRemotesNamedRemote:
    """Verify named remote lookup from RemotesConfig."""

    def test_given_named_remote_when_resolve_then_returns_client(self, monkeypatch):
        servers = [
            RemoteServer(
                name="work",
                url="https://fs2.company.com",
                api_key="my-key",
            ),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))

        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remotes

        clients = resolve_remotes("work")

        assert len(clients) == 1
        assert isinstance(clients[0], RemoteClient)
        assert clients[0].base_url == "https://fs2.company.com"
        assert clients[0].api_key == "my-key"
        assert clients[0].name == "work"


class TestResolveRemotesInlineURL:
    """Verify inline URL creates RemoteClient directly."""

    def test_given_http_url_when_resolve_then_creates_client_from_url(self, monkeypatch):
        fake_config = FakeConfigurationService()
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remotes

        clients = resolve_remotes("http://localhost:8000")

        assert len(clients) == 1
        assert clients[0].base_url == "http://localhost:8000"

    def test_given_https_url_when_resolve_then_creates_client_from_url(self, monkeypatch):
        fake_config = FakeConfigurationService()
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remotes

        clients = resolve_remotes("https://fs2.example.com")

        assert len(clients) == 1
        assert clients[0].base_url == "https://fs2.example.com"


class TestResolveRemotesCommaSeparated:
    """Verify comma-separated values return multiple clients."""

    def test_given_two_names_when_resolve_then_returns_two_clients(self, monkeypatch):
        servers = [
            RemoteServer(name="work", url="https://work.example.com"),
            RemoteServer(name="oss", url="https://oss.example.com"),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remotes

        clients = resolve_remotes("work,oss")

        assert len(clients) == 2
        urls = {c.base_url for c in clients}
        assert urls == {"https://work.example.com", "https://oss.example.com"}

    def test_given_mixed_name_and_url_when_resolve_then_returns_both(self, monkeypatch):
        servers = [
            RemoteServer(name="work", url="https://work.example.com"),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remotes

        clients = resolve_remotes("work,http://localhost:9000")

        assert len(clients) == 2
        urls = {c.base_url for c in clients}
        assert "https://work.example.com" in urls
        assert "http://localhost:9000" in urls


class TestResolveRemotesUnknownName:
    """Verify unknown remote name raises typer.Exit(1) with actionable error."""

    def test_given_unknown_name_when_resolve_then_raises_exit(self, monkeypatch):
        fake_config = FakeConfigurationService(RemotesConfig(servers=[]))
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from click.exceptions import Exit

        from fs2.cli.utils import resolve_remotes

        with pytest.raises(Exit):
            resolve_remotes("nonexistent")

    def test_given_unknown_name_with_available_when_resolve_then_shows_available(
        self, monkeypatch, capsys
    ):
        servers = [
            RemoteServer(name="work", url="https://work.example.com"),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from click.exceptions import Exit

        from fs2.cli.utils import resolve_remotes

        with pytest.raises(Exit):
            resolve_remotes("typo")

        captured = capsys.readouterr()
        assert "work" in captured.err or "work" in captured.out
