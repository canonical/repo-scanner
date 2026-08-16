# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The argument scanner: walk the command tree and collect raw values from argv.

One left-to-right pass. Options in scope are recognized wherever they appear (the
flow-down globals are in scope from the start, so a global may come before or after
any subcommand); non-option tokens select subcommands until a leaf is reached, then
fill its positionals; `--` (or, for an `exec`/`invoke` leaf, the first trailing
token) starts a verbatim remainder. Nothing here reads env or config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from repo_scanner.cli.spec import Command, Group, Param, params_of


@dataclass
class Parsed:
    """The outcome of scanning argv against the tree.

    Exactly one condition will be truthy: `error`, `help`, type(`node`) == `Group`,
    or type(`command`) == Command.
    """

    prog: str
    node: type[Command | Group]
    scope: list[Param]
    raw: dict[str, Any] = field(default_factory=dict)
    command: type[Command] | None = None
    help: bool = False
    error: str | None = None


def parse(
    root: type[Group], base: type[Command], argv: list[str], prog_name: str
) -> Parsed:
    """Scan `argv` against the tree; `base`'s parameters are the flow-down globals."""
    scope: dict[str, Param] = {p.name: p for p in params_of(base)}
    node: type[Command | Group] = root
    prog = [prog_name]
    command: type[Command] | None = None
    raw: dict[str, Any] = {}
    positionals: list[str] = []
    singles: list[Param] = []
    many: Param | None = None
    remainder: Param | None = None
    no_more_options = False

    def result(**kw: Any) -> Parsed:
        return Parsed(
            prog=" ".join(prog), node=command or node, scope=list(scope.values()), **kw
        )

    i, n = 0, len(argv)
    while i < n:
        tok = argv[i]
        if not no_more_options and tok in ("-h", "--help"):
            return result(raw=raw, command=command, help=True)
        if not no_more_options and tok == "--":
            no_more_options = True
            i += 1
            continue
        if not no_more_options and tok.startswith("-") and tok != "-":
            key, _, inline = tok.partition("=")
            param = _find_option(scope, key)
            if param is None:
                if remainder is not None and len(positionals) >= len(singles):
                    raw[remainder.name] = argv[i:]  # an unknown option starts remainder
                    break
                return result(raw=raw, command=command, error=f"unknown option: {key}")
            if not param.takes_cli_value:
                raw[param.name] = True
                i += 1
            elif "=" in tok:
                raw[param.name] = inline
                i += 1
            elif i + 1 < n:
                raw[param.name] = argv[i + 1]
                i += 2
            else:
                return result(
                    raw=raw, command=command, error=f"option {key} requires a value"
                )
            continue

        # a positional token (or any token once options have ended)
        if command is None:
            child = _child(node, tok)
            if child is None:
                return result(raw=raw, error=f"unknown command: {tok}")
            prog.append(tok)
            scope.update({p.name: p for p in params_of(child)})
            if isinstance(child, type) and issubclass(child, Group):
                node = child
            else:
                command = child
                own = params_of(child)
                singles = [p for p in own if p.positional and not p.many]
                many = next((p for p in own if p.positional and p.many), None)
                remainder = next((p for p in own if p.remainder), None)
            i += 1
            continue
        # at a leaf
        if len(positionals) < len(singles) or many is not None:
            positionals.append(tok)
            i += 1
            continue
        if remainder is not None:
            raw[remainder.name] = argv[i:]  # trailing tokens are the verbatim remainder
            break
        return result(raw=raw, command=command, error=f"unexpected argument: {tok}")

    if command is None:
        return result(raw=raw, command=None)  # a subcommand is required
    error = _bind_positionals(raw, positionals, singles, many)
    return result(raw=raw, command=command, error=error)


def _find_option(scope: dict[str, Param], flag: str) -> Param | None:
    for param in scope.values():
        if flag in param.flags:
            return param
    return None


def _child(node: type[Command | Group], name: str) -> type[Command | Group] | None:
    subcommands = getattr(node, "subcommands", ())
    for child in subcommands:
        if child.name == name:
            return child
    return None


def _bind_positionals(
    raw: dict[str, Any], tokens: list[str], singles: list[Param], many: Param | None
) -> str | None:
    """Distribute collected positional tokens to the single params, then the many."""
    index = 0
    for param in singles:
        if index < len(tokens):
            raw[param.name] = tokens[index]
            index += 1
        elif param.required:
            return f"missing argument: {param.name}"
    if many is not None:
        raw[many.name] = tokens[index:]
    elif index < len(tokens):
        return f"unexpected argument: {tokens[index]}"
    return None
