"""Tests for persistent config: the store, the config command, and CLI wiring.

Each test isolates XDG_CONFIG_HOME to a temp dir so it never touches a real
~/.config/reposcan/config.json.
"""

import io
import os
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path

from repo_scanner import config
from repo_scanner.cli import main
from repo_scanner.commands.config_cmd import get_value, set_value


@contextmanager
def _isolated_config():
    """Point XDG_CONFIG_HOME at a fresh temp dir for the duration of the block."""
    saved = os.environ.get("XDG_CONFIG_HOME")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_CONFIG_HOME"] = tmp
        try:
            yield Path(tmp)
        finally:
            if saved is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = saved


def test_config_path_is_under_xdg_config_home() -> None:
    with _isolated_config() as tmp:
        assert config.config_path() == tmp / "reposcan" / "config.json"


def test_load_is_empty_when_no_file_exists() -> None:
    with _isolated_config():
        assert config.load() == {}


def test_save_then_load_round_trips() -> None:
    with _isolated_config():
        assert config.save({"backend": "docker"}) is None
        assert config.load() == {"backend": "docker"}


def test_malformed_config_is_ignored() -> None:
    with _isolated_config():
        path = config.config_path()
        path.parent.mkdir(parents=True)
        path.write_text("{ not json")
        assert config.load() == {}


def test_set_rejects_unknown_key_and_invalid_value() -> None:
    with _isolated_config():
        assert set_value("bogus", "x") == 2
        assert set_value("backend", "podman") == 2
        assert config.load() == {}  # nothing persisted


def test_set_persists_a_valid_value() -> None:
    with _isolated_config():
        assert set_value("backend", "lxd") == 0
        assert config.load() == {"backend": "lxd"}


def test_get_prints_a_set_value_and_reports_a_missing_one() -> None:
    with _isolated_config():
        set_value("backend", "docker")
        out = io.StringIO()
        with redirect_stdout(out):
            assert get_value("backend") == 0
        assert out.getvalue().strip() == "docker"
        assert get_value("mode") == 1  # not set


def test_config_set_then_get_via_cli() -> None:
    with _isolated_config():
        assert main(["config", "set", "backend", "docker"]) == 0
        out = io.StringIO()
        with redirect_stdout(out):
            assert main(["config", "get", "backend"]) == 0
        assert out.getvalue().strip() == "docker"
