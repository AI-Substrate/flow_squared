"""Tests for CLIContext.remote and resolve_remote_client integration.

Phase 5: Remote CLI + MCP Bridge
Tests the integration between CLIContext.remote field and the
resolve_remote_client utility. Also validates RemotesConfig
registration and RemoteServer validation rules.

Uses FakeConfigurationService and real objects (fakes over mocks).
"""

from __future__ import annotations

import click
import pytest

from fs2.cli.main import CLIContext
from fs2.cli.remote_client import MultiRemoteClient, RemoteClient
from fs2.config.objects import YAML_CONFIG_TYPES, RemotesConfig, RemoteServer
from fs2.config.service import FakeConfigurationService


def _make_typer_ctx(cli_context: CLIContext | None = None) -> click.Context:
    """Create a click.Context suitable for resolve_remote_client."""
    ctx = click.Context(click.Command("test"))
    ctx.obj = cli_context
    return ctx


# ── CLIContext.remote field ───────────────────────────────────────────────────


class TestCLIContextRemoteField:
    """Verify CLIContext dataclass accepts the remote field."""

    def test_given_no_remote_when_create_then_remote_is_none(self):
        ctx = CLIContext()
        assert ctx.remote is None

    def test_given_remote_name_when_create_then_remote_set(self):
        ctx = CLIContext(remote="work")
        assert ctx.remote == "work"

    def test_given_remote_url_when_create_then_remote_set(self):
        ctx = CLIContext(remote="http://localhost:8000")
        assert ctx.remote == "http://localhost:8000"

    def test_given_comma_separated_when_create_then_remote_set(self):
        ctx = CLIContext(remote="work,oss")
        assert ctx.remote == "work,oss"


# ── resolve_remote_client ────────────────────────────────────────────────────


class TestResolveRemoteClientNone:
    """Verify resolve_remote_client returns None when no remote configured."""

    def test_given_no_remote_when_resolve_then_returns_none(self):
        from fs2.cli.utils import resolve_remote_client

        ctx = _make_typer_ctx(CLIContext(remote=None))
        result = resolve_remote_client(ctx)

        assert result is None

    def test_given_no_obj_when_resolve_then_returns_none(self):
        from fs2.cli.utils import resolve_remote_client

        ctx = _make_typer_ctx(None)
        result = resolve_remote_client(ctx)

        assert result is None


class TestResolveRemoteClientSingle:
    """Verify single remote → RemoteClient."""

    def test_given_single_named_remote_when_resolve_then_returns_remote_client(
        self, monkeypatch
    ):
        servers = [
            RemoteServer(name="work", url="https://fs2.company.com", api_key="key"),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remote_client

        ctx = _make_typer_ctx(CLIContext(remote="work"))
        result = resolve_remote_client(ctx)

        assert isinstance(result, RemoteClient)
        assert result.base_url == "https://fs2.company.com"
        assert result.name == "work"

    def test_given_inline_url_when_resolve_then_returns_remote_client(
        self, monkeypatch
    ):
        fake_config = FakeConfigurationService()
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remote_client

        ctx = _make_typer_ctx(CLIContext(remote="http://localhost:8000"))
        result = resolve_remote_client(ctx)

        assert isinstance(result, RemoteClient)
        assert result.base_url == "http://localhost:8000"


class TestResolveRemoteClientMulti:
    """Verify comma-separated remote → MultiRemoteClient."""

    def test_given_comma_remote_when_resolve_then_returns_multi_remote_client(
        self, monkeypatch
    ):
        servers = [
            RemoteServer(name="work", url="https://work.example.com"),
            RemoteServer(name="oss", url="https://oss.example.com"),
        ]
        fake_config = FakeConfigurationService(RemotesConfig(servers=servers))
        monkeypatch.setattr(
            "fs2.config.service.FS2ConfigurationService",
            lambda: fake_config,
        )

        from fs2.cli.utils import resolve_remote_client

        ctx = _make_typer_ctx(CLIContext(remote="work,oss"))
        result = resolve_remote_client(ctx)

        assert isinstance(result, MultiRemoteClient)
        assert len(result.clients) == 2


# ── RemotesConfig registration ────────────────────────────────────────────────


class TestRemotesConfigRegistration:
    """Verify RemotesConfig is registered in YAML_CONFIG_TYPES."""

    def test_given_yaml_config_types_when_check_then_remotes_config_present(self):
        assert RemotesConfig in YAML_CONFIG_TYPES

    def test_given_remotes_config_when_check_path_then_correct(self):
        assert RemotesConfig.__config_path__ == "remotes"


# ── RemoteServer validation ──────────────────────────────────────────────────


class TestRemoteServerURLValidation:
    """Verify URL validation rules on RemoteServer."""

    def test_given_http_url_when_create_then_accepted(self):
        server = RemoteServer(name="test", url="http://localhost:8000")
        assert server.url == "http://localhost:8000"

    def test_given_https_url_when_create_then_accepted(self):
        server = RemoteServer(name="test", url="https://fs2.example.com")
        assert server.url == "https://fs2.example.com"

    def test_given_trailing_slash_when_create_then_stripped(self):
        server = RemoteServer(name="test", url="https://fs2.example.com/")
        assert server.url == "https://fs2.example.com"

    def test_given_no_scheme_when_create_then_rejected(self):
        with pytest.raises(ValueError, match="http://"):
            RemoteServer(name="test", url="fs2.example.com")

    def test_given_ftp_scheme_when_create_then_rejected(self):
        with pytest.raises(ValueError, match="http://"):
            RemoteServer(name="test", url="ftp://fs2.example.com")


class TestRemoteServerNameValidation:
    """Verify name validation rules on RemoteServer."""

    def test_given_empty_name_when_create_then_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            RemoteServer(name="", url="https://fs2.example.com")

    def test_given_whitespace_name_when_create_then_rejected(self):
        with pytest.raises(ValueError, match="empty"):
            RemoteServer(name="   ", url="https://fs2.example.com")

    def test_given_valid_name_when_create_then_accepted(self):
        server = RemoteServer(name="work", url="https://fs2.example.com")
        assert server.name == "work"
