# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the parameter spec, in particular flag inference (repo_scanner.cli.spec).

An option/flag's long spelling `--<name>` is inferred from its attribute name; the
flags passed to the constructor are only extra spellings. Positionals and remainders
get no flags.
"""

from repo_scanner.cli.commands.base import Command as Globals
from repo_scanner.cli.spec import flag, option, params_of, positional, remainder


class _Sample:
    plain: str = option()
    short: str = option("-s")
    multi_word: bool = flag()
    explicit_long: str = option("--explicit-long")  # already given: not duplicated
    pos: str = positional()
    rest: list[str] = remainder()


def _flags(cls: type) -> dict[str, tuple[str, ...]]:
    return {p.name: p.flags for p in params_of(cls)}


def test_the_long_flag_is_inferred_and_extra_flags_are_kept() -> None:
    flags = _flags(_Sample)
    assert flags["plain"] == ("--plain",)  # inferred from the name
    assert flags["short"] == ("-s", "--short")  # extra short kept, long inferred
    assert flags["multi_word"] == ("--multi-word",)  # a flag, name kebab-cased
    assert flags["explicit_long"] == ("--explicit-long",)  # not duplicated
    assert flags["pos"] == ()  # positionals get no flags
    assert flags["rest"] == ()  # nor remainders


def test_the_real_globals_infer_their_flags() -> None:
    flags = _flags(Globals)
    assert flags["backend"] == ("--backend",)
    assert flags["verbosity"] == ("-v", "--verbosity")
    assert flags["uid"] == ("--uid",)
    assert flags["image"] == ("--image",)  # config-and-CLI, not config-only
