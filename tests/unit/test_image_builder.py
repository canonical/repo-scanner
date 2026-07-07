"""Tests for the shared image ensure step (repo_scanner.image.builder)."""

from repo_scanner.image.build_spec import BuildSpec
from repo_scanner.image.builder import ensure_image

_SPEC = BuildSpec("ubuntu:24.04", "/opt/reposcan", "#!/bin/sh\ntrue\n")


class _FakeBuilder:
    """An ImageBuilder that records whether build() ran, without touching a daemon."""

    name = "fake"

    def __init__(self, *, present: bool) -> None:
        self._present = present
        self.built = False

    def reference(self, spec: BuildSpec) -> str:
        return "img:abc"

    def exists(self, reference: str) -> bool:
        return self._present

    def build(self, spec: BuildSpec) -> str:
        self.built = True
        return "img:abc"


def test_ensure_builds_only_when_missing_or_forced() -> None:
    present = _FakeBuilder(present=True)
    assert ensure_image(present, _SPEC) == "img:abc"
    assert not present.built  # reused, build skipped

    missing = _FakeBuilder(present=False)
    assert ensure_image(missing, _SPEC) == "img:abc"
    assert missing.built  # built because absent

    forced = _FakeBuilder(present=True)
    assert ensure_image(forced, _SPEC, force=True) == "img:abc"
    assert forced.built  # forced past the existence check
