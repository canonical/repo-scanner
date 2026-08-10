# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for persistent config: the store, the config command, and CLI wiring.

Each test isolates XDG_CONFIG_HOME to a temp dir so it never touches a real
~/.config/reposcan/config.json.
"""

import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout

from repo_scanner import config
from repo_scanner.cli import main
from repo_scanner.commands.config_cmd import get_value, set_value


@contextmanager
def _isolated_config() -> Iterator[None]:
    """Point XDG_CONFIG_HOME at a fresh temp dir for the duration of the block."""
    saved = os.environ.get("XDG_CONFIG_HOME")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["XDG_CONFIG_HOME"] = tmp
        try:
            yield
        finally:
            if saved is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = saved


def test_store_round_trips_and_tolerates_a_missing_or_malformed_file() -> None:
    with _isolated_config():
        assert config.load() == {}  # nothing saved yet
        assert config.save({"backend": "docker"}) is None
        assert config.load() == {"backend": "docker"}  # round trip
    with _isolated_config():
        path = config.config_path()
        path.parent.mkdir(parents=True)
        path.write_text("{ not json")
        assert config.load() == {}  # malformed is ignored, not fatal


def test_set_validates_the_key_and_value_before_persisting() -> None:
    with _isolated_config():
        assert set_value("bogus", "x") == 2  # unknown key
        assert set_value("backend", "podman") == 2  # invalid value
        assert config.load() == {}  # nothing persisted on rejection
        assert set_value("backend", "lxd") == 0  # a valid value is accepted
        assert config.load() == {"backend": "lxd"}


def test_get_prints_a_set_value_and_reports_a_missing_one() -> None:
    with _isolated_config():
        set_value("backend", "docker")
        out = io.StringIO()
        with redirect_stdout(out):
            assert get_value("backend") == 0
        assert out.getvalue().strip() == "docker"
        assert get_value("mode") == 1  # not set


def test_config_set_then_get_round_trips_through_the_cli() -> None:
    with _isolated_config():
        assert main(["config", "set", "backend", "docker"]) == 0
        out = io.StringIO()
        with redirect_stdout(out):
            assert main(["config", "get", "backend"]) == 0
        assert out.getvalue().strip() == "docker"
