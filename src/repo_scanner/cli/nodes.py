# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Command tree node types and their shared dispatch.

A `Command` (leaf) declares its options and implements `run`; its `dispatch`
(template method, in the ABC) parses parameters and calls `run`. A `CommandGroup`
declares its options and a `subcommands` registry; its `dispatch` parses the
level's options, matches the next token to a subcommand, and descends.
`Context` holds already-parsed parameters and option specs, and does the parsing.

One group, `scan`, dynamically generates its `Command`s and therefore writes
its own `Step`-compliant class.
"""

import argparse
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from repo_scanner.cli.options import Option, Values
from repo_scanner.cli.parsing import add_option, print_help, unknown_command


@dataclass
class Context:
    """Parsed option values, option specs, and prog path accumulated down the tree.

    Mutated in place as dispatch descends. A level calls `parse` to parse its own
    options out of its argv, fold the resolved values in, extend the option specs
    (so they flow to children), and append its name to the prog path.

    Attributes:
        values: Option values resolved so far, keyed by parameter name.
        specs: Accumulated option specs appended at each level.
        prog: The accumulated command path (e.g. "reposcan image cache").
    """

    values: Values
    specs: tuple[Option, ...]
    prog: str = "reposcan"

    def parse(
        self,
        name: str,
        options: tuple[Option, ...],
        argv: list[str],
        *,
        leaf: bool = False,
    ) -> list[str]:
        """Update self.prog, .specs, and .values given new `options` and `argv`.

        A group (`leaf=False`) parses leniently (`parse_known_args`) so the
        subcommand word and any `--` passthrough stay in the returned argv remainder.
        A leaf (`leaf=True`) parses strictly so all of argv is consumed.

        Args:
            name: This level's subcommand name (appended to `prog`).
            options: The option specs declared at this level.
            argv: The args for this level.
            leaf: True for a leaf (strict parse, with help); False for a group
                (lenient parse, leftover returned for descent).

        Returns:
            The leftover non-option tokens (unused for a leaf).
        """
        cumulative = (*self.specs, *options)
        parser = argparse.ArgumentParser(
            prog=f"{self.prog} {name}" if leaf else None,
            add_help=leaf,
        )
        for opt in cumulative:
            add_option(parser, opt)
        seeded = argparse.Namespace(**self.values)
        if leaf:
            namespace = parser.parse_args(argv, namespace=seeded)
            remaining: list[str] = []
        else:
            namespace, remaining = parser.parse_known_args(argv, namespace=seeded)
        self.values = vars(namespace)
        self.specs = cumulative
        if name:
            self.prog = f"{self.prog} {name}"
        return remaining


@runtime_checkable
class Step(Protocol):
    """Any node in the command tree.

    Attributes:
        name: The subcommand word this node is selected by.
        help: The one-line help shown in the parent's subcommand list.
        options: The option spec declared at this level (flows down to children).
    """

    name: str
    help: str
    options: tuple[Option, ...]

    def dispatch(self, argv: list[str], ctx: Context) -> int: ...


class CommandGroup:
    """A group of subcommands: options + a subcommands registry + shared dispatch.

    Subclasses set `name`/`help`/`options`/`subcommands` as class attributes.
    `subcommands` maps each subcommand word to the child *class* (a `Step`);
    `dispatch` parses this level's options, matches the next token, instantiates
    the selected child class, and descends.
    """

    name: str
    help: str
    options: tuple[Option, ...] = ()
    subcommands: dict[str, type[Step]] = {}

    def dispatch(self, argv: list[str], ctx: Context) -> int:
        """Parse this level's options, then descend into the selected subcommand."""
        remaining = ctx.parse(self.name, self.options, argv)
        prog = ctx.prog
        cumulative = ctx.specs
        if not remaining:
            print_help(
                prog,
                cumulative,
                {n: s.help for n, s in self.subcommands.items()},
                description=self.help,
                to_stderr=True,
            )
            return 2  # a subcommand is required
        if remaining[0] in ("-h", "--help"):
            print_help(
                prog,
                cumulative,
                {n: s.help for n, s in self.subcommands.items()},
                description=self.help,
            )
            return 0
        subcmd_cls = self.subcommands.get(remaining[0])
        if subcmd_cls is None:
            return unknown_command(prog, remaining[0], self.subcommands)
        return subcmd_cls().dispatch(remaining[1:], ctx)


class Command(ABC):
    """A leaf: declare `options` and implement `run`; `dispatch` is shared.

    The template-method `dispatch` does the cumulative strict parse (ancestor
    specs flowed down via `ctx` plus this leaf's own options) and calls `run` with
    the resolved values. Subclasses set `name`/`help`/`options` and implement
    `run`; they do not override `dispatch`.
    """

    name: str
    help: str
    options: tuple[Option, ...] = ()

    def dispatch(self, argv: list[str], ctx: Context) -> int:
        ctx.parse(self.name, self.options, argv, leaf=True)
        return self.run(ctx.values)

    @abstractmethod
    def run(self, values: Values) -> int:
        """Execute the parsed leaf command and return a process exit code."""
