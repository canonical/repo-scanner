"""Tests for the LXD image builder (repo_scanner.image.lxd).

lxc is not invoked: run_process is patched with a fake that records the argv; its
response is a callable so a specific step can be made to fail.
"""

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager

import repo_scanner.image.lxd as lxd
from repo_scanner.execution.process import ExecResult, Failure
from repo_scanner.image.build_spec import BuildSpec

_SPEC = BuildSpec("ubuntu:24.04", "/opt/reposcan", "#!/bin/sh\ntrue\n")
_BUILDER = lxd.LxdImageBuilder()
_OK = ExecResult(0, "", "")


@contextmanager
def _patched(respond: Callable[[list[str]], ExecResult | Failure]):
    calls: list[list[str]] = []

    def fake(
        command: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float | None = None,
        check: bool = False,
        stream: bool = False,
    ) -> ExecResult | Failure:
        calls.append(list(command))
        return respond(list(command))

    # ensure_project shells out to lxc through a different module, so stub it to a
    # no-op here; its own behavior is covered in test_lxd_context.
    saved_run, saved_ensure = lxd.run_process, lxd.ensure_project
    lxd.run_process = fake
    lxd.ensure_project = lambda: None
    try:
        yield calls
    finally:
        lxd.run_process = saved_run
        lxd.ensure_project = saved_ensure


# Every lxc command is pinned to reposcan's own project, not `default`.
_LXC = ["lxc", "--project", "reposcan"]


def test_build_launches_provisions_publishes_and_cleans_up() -> None:
    with _patched(lambda argv: _OK) as calls:
        alias = _BUILDER.build(_SPEC)
    assert alias == f"reposcan-{_SPEC.short_digest}"
    assert isinstance(alias, str) and ":" not in alias  # LXD aliases cannot use a colon
    assert calls[0][:4] == [*_LXC, "launch"]
    assert calls[-2][:4] == [*_LXC, "publish"] and "--alias" in calls[-2]
    assert alias in calls[-2]
    assert calls[-1][:4] == [*_LXC, "delete"]  # build container removed last


def test_build_deletes_the_builder_even_when_a_step_fails() -> None:
    # Fail the "run the install script" exec step; the builder must still be deleted.
    def respond(argv: list[str]) -> ExecResult | Failure:
        if "sh" in argv and "/root/install.sh" in argv:
            return Failure(reason="install failed")
        return _OK

    with _patched(respond) as calls:
        result = _BUILDER.build(_SPEC)
    assert isinstance(result, Failure) and result.reason == "install failed"
    assert calls[-1][:4] == [*_LXC, "delete"]


def test_build_aborts_early_when_the_container_has_no_network() -> None:
    # The outbound-connectivity probe fails; the build must stop before running the
    # install script (no multi-minute doomed download) and still delete the builder.
    def respond(argv: list[str]) -> ExecResult | Failure:
        if any("/dev/tcp" in arg for arg in argv):  # the connectivity probe
            return ExecResult(1, "", "Network is unreachable")
        return _OK

    with _patched(respond) as calls:
        result = _BUILDER.build(_SPEC)
    assert isinstance(result, Failure) and "network" in result.reason.lower()
    assert not any("/root/install.sh" in argv for argv in calls)  # install never ran
    assert calls[-1][:4] == [*_LXC, "delete"]  # builder still cleaned up


def test_identity_parses_the_fingerprint_or_none_when_absent() -> None:
    info = ExecResult(0, "Architecture: x86_64\nFingerprint: deadbeef\n", "")
    with _patched(lambda argv: info) as calls:
        assert _BUILDER.identity("reposcan-x") == "deadbeef"
    assert calls[0][:5] == [*_LXC, "image", "info"]
    with _patched(lambda argv: ExecResult(1, "", "not found")):
        assert _BUILDER.identity("reposcan-x") is None
