# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for backend selection (repo_scanner.backends).

Availability is controlled by patching backends.run_process (the liveness probe);
local is always available. Precedence is exercised by patching the environment and
config.load.
"""

import os
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

import repo_scanner.backends as backends
import repo_scanner.config as config
from repo_scanner.backends import (
    Backend,
    DockerBackend,
    LocalBackend,
    LxdBackend,
    select_backend,
    start_session,
    tool_context,
)
from repo_scanner.execution.docker import DockerContext
from repo_scanner.execution.local import LocalContext
from repo_scanner.execution.lxd import LxdContext
from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.image.remote import CANONICAL_REF
from repo_scanner.paths import tools_root


@contextmanager
def _availability(*, lxd_ok: bool, docker_ok: bool) -> Iterator[None]:
    ok = ExecResult(0, "", "")

    def fake(
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        check: bool = False,
    ) -> ExecResult | Failure:
        if command[0] == "lxc":
            return ok if lxd_ok else Failure(reason="no lxc")
        if command[0] == "docker":
            return ok if docker_ok else Failure(reason="no docker")
        return ok

    saved = backends.run_process
    backends.run_process = fake
    try:
        yield
    finally:
        backends.run_process = saved


@contextmanager
def _env(name: str, value: str | None) -> Iterator[None]:
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
def _saved_config(settings: dict[str, str]) -> Iterator[None]:
    saved = config.load
    config.load = lambda: settings
    try:
        yield
    finally:
        config.load = saved


def _backend(requested: str | None) -> Backend:
    chosen = select_backend(requested)
    assert not isinstance(chosen, Failure), chosen
    return chosen


def test_auto_selects_the_first_available_in_precedence_order() -> None:
    with _availability(lxd_ok=True, docker_ok=True):
        assert _backend("auto").name == "lxd"
    with _availability(lxd_ok=False, docker_ok=True):
        assert _backend("auto").name == "docker"
    with _availability(lxd_ok=False, docker_ok=False):
        assert _backend("auto").name == "local"  # always available, the last resort


def test_selection_precedence_request_over_env_over_config_over_auto() -> None:
    # An explicit request wins over env and config.
    with _env("REPOSCAN_BACKEND", "docker"), _saved_config({"backend": "lxd"}):
        assert _backend("local").name == "local"
    # No request: env wins over config.
    with (
        _availability(lxd_ok=True, docker_ok=True),
        _env("REPOSCAN_BACKEND", "docker"),
        _saved_config({"backend": "lxd"}),
    ):
        assert _backend(None).name == "docker"
    # No request or env: saved config is used.
    with (
        _availability(lxd_ok=True, docker_ok=True),
        _env("REPOSCAN_BACKEND", None),
        _saved_config({"backend": "lxd"}),
    ):
        assert _backend(None).name == "lxd"
    # Nothing set: auto (here, with no daemons, falling through to local).
    with (
        _availability(lxd_ok=False, docker_ok=False),
        _env("REPOSCAN_BACKEND", None),
        _saved_config({}),
    ):
        assert _backend(None).name == "local"


def test_invalid_selections_are_failures() -> None:
    assert isinstance(select_backend("bogus"), Failure)  # unknown name
    with _availability(lxd_ok=False, docker_ok=False):
        failure = select_backend("docker")  # explicit but unavailable
    assert isinstance(failure, Failure) and "docker" in failure.reason


def test_only_container_backends_provide_an_image_builder() -> None:
    with _availability(lxd_ok=True, docker_ok=True):
        assert _backend("lxd").image_builder() is not None
        assert _backend("docker").image_builder() is not None
    assert _backend("local").image_builder() is None  # local installs onto the host


def test_tool_context_local_on_host_container_in_the_verified_image() -> None:
    # Local: tools are on the host, no image is built.
    assert isinstance(tool_context(LocalBackend()), LocalContext)

    # Container: the tool image (here stubbed via ensure_image) is run; a build
    # failure surfaces as a Failure.
    def ensure_ok(builder: object, spec: object, *, force: bool = False) -> str:
        return "reposcan:tools"

    def ensure_fail(builder: object, spec: object, *, force: bool = False) -> Failure:
        return Failure(reason="build failed")

    saved = backends.ensure_image
    try:
        backends.ensure_image = ensure_ok
        ctx = tool_context(DockerBackend())
        assert isinstance(ctx, DockerContext) and ctx._image == "reposcan:tools"
        backends.ensure_image = ensure_fail
        assert isinstance(tool_context(DockerBackend()), Failure)
    finally:
        backends.ensure_image = saved


def test_tool_context_uses_a_configured_remote_image_when_the_backend_can() -> None:
    def remote_ok(puller: object, ref: str) -> str:
        return f"pulled:{ref}"

    def remote_fail(puller: object, ref: str) -> Failure:
        return Failure(reason="pull failed")

    def build_ok(builder: object, spec: object, *, force: bool = False) -> str:
        return "reposcan:tools"

    saved_pulled = backends.ensure_pulled
    saved_build = backends.ensure_image
    try:
        with _saved_config({"image": "canonical"}):
            # Docker resolves the shorthand, pulls it, and runs the pulled image.
            backends.ensure_pulled = remote_ok
            ctx = tool_context(DockerBackend())
            assert isinstance(ctx, DockerContext)
            assert ctx._image == f"pulled:{CANONICAL_REF}"
            # A pull failure surfaces as a Failure.
            backends.ensure_pulled = remote_fail
            assert isinstance(tool_context(DockerBackend()), Failure)
            # LXD cannot use a remote image yet, so it ignores the config and builds.
            backends.ensure_image = build_ok
            lxd_ctx = tool_context(LxdBackend())
            assert isinstance(lxd_ctx, LxdContext)
            assert lxd_ctx._image == "reposcan:tools"
    finally:
        backends.ensure_pulled = saved_pulled
        backends.ensure_image = saved_build


def test_start_session_runs_on_the_started_context_or_reports_a_bad_backend() -> None:
    # Local is always available and needs no image, so the session runs on the host.
    with start_session("local", tool_image=True) as session:
        assert session.ok and session.exit_code == 0
        assert isinstance(session.context, LocalContext)
        assert session.tool_root == str(tools_root())
    # An unusable backend yields a not-ok session carrying the exit code.
    with start_session("bogus", tool_image=True) as session:
        assert not session.ok and session.exit_code == 2
