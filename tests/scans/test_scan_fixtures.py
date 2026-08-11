# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Scan tests: run scans against fixtures and enforce coverage.

Fixtures live one-per-scan under tests/scans/fixtures/, each exposing SCAN,
plant, and verify as data. This file holds only the logic: it loads those
fixtures, runs each scan against its planted content in the built tool image, and
enforces that every scan in src/repo_scanner/scans has a fixture.

The real-tool test skips when docker is unavailable; the coverage guard always
runs. The first run builds the tool image, so it can take several minutes.
"""

import importlib
import importlib.util
import logging
import pkgutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

import pytest

import repo_scanner.scans as scans_pkg
from repo_scanner.backends import DockerBackend, start_session
from repo_scanner.execution.process import Failure
from repo_scanner.scans.model import Artifact, Scan, run_scan
from repo_scanner.scans.registry import SCANS

logger = logging.getLogger(__name__)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


class _FixtureModule(Protocol):
    """The contract every fixture file under fixtures/ provides."""

    SCAN: Scan
    plant: Callable[[Path], None]
    verify: Callable[[Artifact], None]


def _load_fixtures() -> dict[str, _FixtureModule]:
    """Load each fixture file under fixtures/, keyed by its scan's name."""
    fixtures: dict[str, _FixtureModule] = {}
    for path in sorted(_FIXTURES_DIR.glob("*.py")):
        spec = importlib.util.spec_from_file_location(
            f"_scan_fixture_{path.stem}", path
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fixture = cast(_FixtureModule, module)
        fixtures[fixture.SCAN.name] = fixture
    return fixtures


def _discover_scan_names() -> set[str]:
    """Every concrete Scan implementation defined under src/repo_scanner/scans."""
    names: set[str] = set()
    for info in pkgutil.iter_modules(scans_pkg.__path__):
        module = importlib.import_module(f"{scans_pkg.__name__}.{info.name}")
        for obj in vars(module).values():
            # A scan class defined in this module (not imported, not an instance);
            # isinstance against the runtime-checkable Scan matches the class object.
            defined_here = isinstance(obj, type) and obj.__module__ == module.__name__
            if defined_here and isinstance(obj, Scan):
                names.add(obj.name)
    return names


def test_every_scan_has_a_fixture() -> None:
    scans = _discover_scan_names()
    assert scans, "no scan types were discovered under src/repo_scanner/scans"
    fixtures = set(_load_fixtures())
    missing = scans - fixtures
    assert not missing, f"scan types with no fixture: {sorted(missing)}"
    orphan = fixtures - scans
    assert not orphan, f"fixtures for unknown scans: {sorted(orphan)}"
    assert set(SCANS) == scans, "SCANS registry is out of sync with the scan modules"


def _run_fixture(name: str, fixture: _FixtureModule) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory)
        fixture.plant(repo)
        logger.info("[docker] scanning the %s fixture", name)
        with start_session(
            "docker", tool_image=True, mount_source=str(repo)
        ) as session:
            assert session.ok, f"session failed for {name} (exit {session.exit_code})"
            assert session.target is not None
            artifact = run_scan(
                fixture.SCAN, session.context, session.target, session.tool_root
            )
            assert not isinstance(artifact, Failure), f"{name}: {artifact}"
            fixture.verify(artifact)


def test_docker_scan_fixtures_report_findings() -> None:
    availability = DockerBackend().availability()
    if not availability.ok:
        pytest.skip(f"docker unavailable: {availability.reason}")
    for name, fixture in sorted(_load_fixtures().items()):
        _run_fixture(name, fixture)
