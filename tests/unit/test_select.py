"""Tests for backend selection (repo_scanner.execution.select).

Selection is tested by patching the docker/lxd modules' run_process so their
availability probes return controlled results; local is always available.
"""

from collections.abc import Mapping, Sequence
from contextlib import contextmanager

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


def test_auto_selects_by_precedence() -> None:
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
