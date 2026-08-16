# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan render` command: convert a saved report between formats."""

from repo_scanner.actions.render import render
from repo_scanner.cli.commands.base import Command
from repo_scanner.cli.spec import flag, option, positional
from repo_scanner.scans.output import DEFAULT_ROW_LIMIT, Format

FORMATS = tuple(f.value for f in Format)


class RenderCommand(Command):
    name = "render"
    help = "Render a saved report (JSON or sqlite) as a table, JSON, or sqlite."

    path: str = positional(
        help="A saved report: SARIF/CycloneDX JSON or a sqlite database."
    )
    output: str | None = option(
        extra_flags="-o", help="Write to FILE instead of stdout (required for sqlite)."
    )
    format: str | None = option("-f", choices=FORMATS, help="Output format.")
    limit: int = option(
        extra_flags="-n",
        default=DEFAULT_ROW_LIMIT,
        convert=int,
        help="Maximum rows shown in the table.",
    )
    wrap: bool = flag(help="Wrap long table cells instead of truncating.")

    def run(self) -> int:
        return render(
            self.path,
            fmt=self.format,
            output_path=self.output,
            limit=self.limit,
            wrap=self.wrap,
        )
