# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Parameter-parsing utilities."""

import argparse
import sys
from collections.abc import Mapping
from typing import Any

from repo_scanner.cli.options import Option


def add_option(parser: argparse.ArgumentParser, opt: Option) -> None:
    """Register one `Option` on `parser` (the data-driven parser)."""
    if opt.positional:
        kwargs: dict[str, Any] = {"help": opt.help}
        if opt.remainder:
            kwargs["nargs"] = argparse.REMAINDER
        elif opt.nargs is not None:
            kwargs["nargs"] = opt.nargs
        parser.add_argument(opt.flags[0], **kwargs)
    else:
        kwargs = {"default": opt.default, "help": opt.help, "dest": opt.dest}
        if opt.choices is not None:
            kwargs["choices"] = opt.choices
        if opt.type is not None:
            kwargs["type"] = opt.type
        if opt.metavar is not None:
            kwargs["metavar"] = opt.metavar
        if opt.store_true:
            kwargs["action"] = "store_true"
            kwargs.pop("default", None)
        parser.add_argument(*opt.flags, **kwargs)


def command_argv(argv: list[str]) -> list[str]:
    """Retrieve passthrough args, dropping a leading '--' separator if present."""
    return argv[1:] if argv and argv[0] == "--" else argv


def print_help(
    prog: str,
    options: tuple[Option, ...],
    subcommands: dict[str, str],
    *,
    description: str | None = None,
    to_stderr: bool = False,
) -> None:
    """Print argparse-rendered help for one level, built just in time.

    Constructs a parser carrying `options` plus a subparsers action listing
    `subcommands` (name -> one-line help), then defers to argparse's `print_help`
    for formatting (column alignment, wrapping, the options section). Built only
    when help is requested; the normal parse/dispatch path is untouched.

    Args:
        prog: The accumulated command path (e.g. "reposcan image cache").
        options: The cumulative option specs recognized at this level.
        subcommands: The immediate children, as name -> one-line help text.
        description: An optional prog description shown above usage.
        to_stderr: When True, write to stderr (missing-subcommand); else stdout.
    """
    parser = argparse.ArgumentParser(prog=prog, description=description)
    for opt in options:
        add_option(parser, opt)
    sub = parser.add_subparsers(dest="command")
    for name, help_text in subcommands.items():
        sub.add_parser(name, help=help_text, add_help=False)
    parser.print_help(sys.stderr if to_stderr else sys.stdout)


def unknown_command(prog: str, name: str, known: Mapping[str, object]) -> int:
    """Print a usage error for an unrecognized subcommand; return exit code 2."""
    print(
        f"{prog}: unknown command {name!r} (choose from {', '.join(known)})",
        file=sys.stderr,
    )
    return 2
