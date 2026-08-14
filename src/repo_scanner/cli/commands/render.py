# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan render` subcommand: convert a saved report between formats."""

from repo_scanner.cli.nodes import Command
from repo_scanner.cli.options import REPORT_FORMAT_OPTIONS, Option, Values
from repo_scanner.commands import render_cmd


class RenderCommand(Command):
    name = "render"
    help = "Render a saved report (JSON or sqlite) as a table, JSON, or sqlite."
    options = (
        Option(
            ("path",),
            "path",
            positional=True,
            help="Path to a saved report: SARIF/CycloneDX JSON or a sqlite database.",
        ),
        Option(
            ("-o", "--output"),
            "output",
            default=None,
            metavar="FILE",
            help="Write to FILE instead of stdout (required for --format sqlite).",
        ),
        *REPORT_FORMAT_OPTIONS,
    )

    def run(self, values: Values) -> int:
        """Render a saved report between formats; no backend needed."""
        return render_cmd.run_render(
            values["path"],
            fmt=values["format"],
            output_path=values["output"],
            limit=values["limit"],
            wrap=values["wrap"],
        )
