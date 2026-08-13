# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Test the render round-trip of json --> sqlite --> json.

Unlike the synthetic round-trip in the unit tests, these exercise `render`
against the real, full-size tool outputs under `fixtures/`: a SARIF document
(`sast.json`) and a CycloneDX SBOM (`sbom.json`). Rendering each to a sqlite
database and back to JSON must reproduce the original document byte-for-byte in
structure, proving the normalized database faithfully reconstructs real reports.

Excluded from the default unit run (`testpaths = ["tests/unit"]`); run with:

    tox run -f integration      (across the py310/py312/py314 matrix)
    OR
    pytest tests/integration -s --log-cli-level=INFO
"""

import io
import json
import os
import tempfile
from contextlib import redirect_stdout

from repo_scanner.commands.render_cmd import run_render

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _render(input_path: str, **kwargs) -> str:
    """Run `render` on `input_path`, returning what it wrote to stdout."""
    out = io.StringIO()
    with redirect_stdout(out):
        assert run_render(input_path, **kwargs) == 0
    return out.getvalue()


def _round_trips(fixture: str) -> None:
    """Assert `fixture` survives json --> sqlite --> json unchanged."""
    source = os.path.join(_FIXTURES, fixture)
    with open(source) as handle:
        original = json.load(handle)

    with tempfile.TemporaryDirectory() as directory:
        database = os.path.join(directory, "report.db")
        assert run_render(source, fmt="sqlite", output_path=database) == 0

        # sqlite input rendered back to JSON reconstructs the original document.
        rendered = _render(database, fmt="json")
        assert json.loads(rendered) == original

        # The same database also renders as a human table (a distinct code path).
        assert "\n" in _render(database, fmt="table")


def test_sarif_report_round_trips_through_sqlite() -> None:
    _round_trips("sast.json")


def test_cyclonedx_report_round_trips_through_sqlite() -> None:
    _round_trips("sbom.json")
