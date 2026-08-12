# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the image build spec (repo_scanner.image.build_spec)."""

import os
import subprocess
import tempfile

from repo_scanner.image.build_spec import BuildSpec, build_script, build_spec
from repo_scanner.tools.model import Platform

_LINUX = Platform("linux", "amd64")


def test_script_sets_up_the_base_installs_every_tool_and_is_valid_shell() -> None:
    script = build_script(_LINUX)
    assert "set -eu" in script  # any failure aborts the build
    assert (
        "apt-get install -y --no-install-recommends curl ca-certificates git" in script
    )
    assert "useradd" in script and "reposcan" in script  # unprivileged scan user
    for name in ("uv", "go", "semgrep", "govulncheck", "trufflehog", "cdxgen"):
        assert f"# {name} " in script  # a section header per tool, prerequisites too
    # The aggregation of heredocs, && chains, and per-tool commands must parse.
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "install.sh")
        with open(path, "w") as handle:
            handle.write(script)
        parsed = subprocess.run(["sh", "-n", path], capture_output=True, text=True)
    assert parsed.returncode == 0, parsed.stderr


def test_digest_is_content_addressed() -> None:
    spec = build_spec(_LINUX)
    assert spec.digest == build_spec(_LINUX).digest  # stable for the same inputs
    # Any change to an identity input yields a new digest.
    assert spec.digest != build_spec(Platform("linux", "arm64")).digest  # platform
    assert spec.digest != build_spec(_LINUX, base_image="ubuntu:22.04").digest  # base
    edited = BuildSpec(spec.base_image, spec.install_root, spec.script + "\n# x")
    assert edited.digest != spec.digest  # script
