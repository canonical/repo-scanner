"""Tests for backend selection (repo_scanner.execution.select).

Availability is controlled by patching the docker/lxd modules' run_process (local
is always available); precedence is exercised by patching the environment and
config.load. select_context resolves the backend and picks a context in one step.
"""

import os
from collections.abc import Mapping, Sequence
from contextlib import contextmanager

import repo_scanner.config as config
import repo_scanner.execution.docker as docker
import repo_scanner.execution.lxd as lxd
from repo_scanner.execution.context import ExecResult, Failure
from repo_scanner.execution.select import select_context


def _probe(result: ExecResult | Failure):
    def fake(
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> ExecResult | Failure:
        return result

    return fake


@contextmanager
def _availability(*, lxd_ok: bool, docker_ok: bool):
    ok = ExecResult(0, "", "")
    saved_lxd, saved_docker = lxd.run_process, docker.run_process
    lxd.run_process = _probe(ok if lxd_ok else Failure(reason="no lxc"))
    docker.run_process = _probe(ok if docker_ok else Failure(reason="no docker"))
    try:
        yield
    finally:
        lxd.run_process, docker.run_process = saved_lxd, saved_docker


@contextmanager
def _env(name: str, value: str | None):
    saved = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = saved


@contextmanager
def _saved_config(settings: dict[str, str]):
    saved = config.load
    config.load = lambda: settings
    try:
        yield
    finally:
        config.load = saved


def test_auto_selects_the_first_available_in_precedence_order() -> None:
    with _availability(lxd_ok=True, docker_ok=True):
        chosen = select_context("auto")
    assert not isinstance(chosen, Failure) and chosen.name == "lxd"

    with _availability(lxd_ok=False, docker_ok=True):
        chosen = select_context("auto")
    assert not isinstance(chosen, Failure) and chosen.name == "docker"


def test_explicit_unavailable_backend_is_a_failure_with_reason() -> None:
    with _availability(lxd_ok=False, docker_ok=False):
        result = select_context("docker")
    assert isinstance(result, Failure)
    assert "docker" in result.reason


def test_unknown_backend_is_a_failure() -> None:
    assert isinstance(select_context("bogus"), Failure)


def test_explicit_request_wins_over_env_and_config() -> None:
    with _env("REPOSCAN_BACKEND", "docker"), _saved_config({"backend": "lxd"}):
        chosen = select_context("local")
    assert not isinstance(chosen, Failure) and chosen.name == "local"


def test_env_backend_used_when_nothing_requested() -> None:
    with _availability(lxd_ok=True, docker_ok=True), _env("REPOSCAN_BACKEND", "docker"):
        chosen = select_context(None)
    assert not isinstance(chosen, Failure) and chosen.name == "docker"


def test_config_backend_used_when_no_request_or_env() -> None:
    with (
        _availability(lxd_ok=True, docker_ok=True),
        _env("REPOSCAN_BACKEND", None),
        _saved_config({"backend": "docker"}),
    ):
        chosen = select_context(None)
    assert not isinstance(chosen, Failure) and chosen.name == "docker"


def test_falls_back_to_auto_when_nothing_is_set() -> None:
    with (
        _availability(lxd_ok=False, docker_ok=False),
        _env("REPOSCAN_BACKEND", None),
        _saved_config({}),
    ):
        chosen = select_context(None)
    assert not isinstance(chosen, Failure) and chosen.name == "local"
