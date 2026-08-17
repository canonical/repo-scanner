# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Command declaration surface: parameters, commands, groups, and the application.

This is the neutral vocabulary a command declares itself with, independent of the
CLI engine (which imports it, not the other way round).

A command is a class: it declares its parameters as typed class attributes and
implements `run`. On dispatch the engine resolves every in-scope parameter
(CLI > env > config > default) and populates the instance, so `run` reads them as
plain typed attributes:

    class CacheRemove(Action):
        name = "remove"
        help = "Remove one entry by its image reference."
        reference: str = positional(help="Image reference to forget.")

        def run(self) -> int:
            ...                                         # self.reference: str

Flow-down: parameters declared on the command base (the globals) are in scope for
every command and may appear anywhere in the arguments, before or after any
subcommand, at any depth -- so `self.backend` is available in every `run`, and
`reposcan image cache --backend docker remove r1` is accepted. A global is simply a
parameter declared on the base.

All parsing, resolution, and help rendering live in `repo_scanner.clikit`; this
module is only the declaration surface plus the `Cli.run` entry point.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any, ClassVar, Generic, TypeVar

T = TypeVar("T")

# all parameters support resolution from env vars, which must use this prefix
ENV_PREFIX = "REPOSCAN_"


class Param(Generic[T]):
    """One parameter: how it is spelled, converted, and where it may be read from.

    Used as the default of a typed class attribute on a command; the attribute name
    becomes the parameter's identity -- the resolved-value key, the env var stem
    (REPOSCAN_<NAME>), the config-file key, and the label in override logs. Build one
    with `option`/`flag`/`positional`/`remainder` rather than directly.
    """

    def __init__(
        self,
        *,
        flags: tuple[str, ...] = (),
        help: str = "",
        default: Any = None,
        choices: tuple[Any, ...] | None = None,
        convert: Callable[[str], Any] | None = None,
        positional: bool = False,
        remainder: bool = False,
        many: bool = False,
        required: bool = True,
        is_flag: bool = False,
        env: bool = True,
        config: bool = False,
        requires: dict[str, str] | None = None,
    ) -> None:
        self.name = ""  # set by __set_name__ from the class-attribute name
        self.flags = flags
        self.help = help
        self.default = default
        self.choices = choices
        self.convert = convert
        self.positional = positional
        self.remainder = remainder
        self.many = many
        self.required = required
        self.is_flag = is_flag
        self.env = env
        self.config = config
        # A cross-option dependency: other-parameter -> the value it must have for
        # this one to be valid, enforced by `check_requires` only when this is set.
        self.requires = requires

    def __set_name__(self, owner: type, name: str) -> None:
        """Capture attribute name.

        Magic method called once during class definition; captures the class attribute
        name that this Param instance is assigned to.
        """
        self.name = name
        # An option/flag's long spelling is inferred from its attribute name; the
        # `flags` passed to the constructor are only the extra spellings (short forms,
        # aliases). Positionals and remainders have no flags.
        if not (self.positional or self.remainder):
            long = "--" + name.replace("_", "-")
            if long not in self.flags:
                self.flags = (*self.flags, long)

    @property
    def takes_cli_value(self) -> bool:
        """Whether the option consumes a following argument on the command line."""
        return not (self.is_flag or self.positional or self.remainder)

    @property
    def env_var(self) -> str:
        """The environment variable that sets this parameter (REPOSCAN_<NAME>)."""
        return ENV_PREFIX + self.name.upper().replace("-", "_").replace(" ", "_")

    def __repr__(self) -> str:
        return f"Param({self.name!r})"


def _as_flags(extra_flags: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalize `extra_flags` (a single flag, an iterable, or None) to a tuple."""
    if extra_flags is None:
        return ()
    if isinstance(extra_flags, str):
        return (extra_flags,)
    return tuple(extra_flags)


def option(
    extra_flags: str | Iterable[str] | None = None,
    *,
    default: T | None = None,
    choices: tuple[T, ...] | None = None,
    convert: Callable[[str], T] | None = None,
    help: str = "",
    env: bool = True,
    config: bool = False,
    requires: dict[str, str] | None = None,
) -> Any:
    """A value option that consumes a following argument (`--backend docker`).

    The long flag `--<name>` is inferred from the attribute name; `extra_flags` are
    additional spellings (a short form, or aliases), given as a single flag or an
    iterable: `verbosity: str = option("-v", ...)` accepts both `-v` and
    `--verbosity`. `requires` maps another parameter to the value it must have for
    this option to be valid (checked by `check_requires`).
    """
    return Param(
        flags=_as_flags(extra_flags),
        default=default,
        choices=choices,
        convert=convert,
        help=help,
        env=env,
        config=config,
        requires=requires,
    )


def flag(
    extra_flags: str | Iterable[str] | None = None,
    *,
    help: str = "",
    env: bool = True,
    config: bool = False,
    requires: dict[str, str] | None = None,
) -> Any:
    """A boolean switch that takes no value, defaulting False.

    The long flag `--<name>` is inferred from the attribute name; `extra_flags` are
    additional spellings (a short form, or aliases), given as a single flag or an
    iterable. `requires` maps another parameter to the value it must have for this
    flag to be valid (checked by `check_requires`).
    """
    return Param(
        flags=_as_flags(extra_flags),
        default=False,
        is_flag=True,
        help=help,
        env=env,
        config=config,
        requires=requires,
    )


def positional(
    help: str = "",
    default: T | None = None,
    convert: Callable[[str], T] | None = None,
    many: bool = False,
    required: bool = True,
    requires: dict[str, str] | None = None,
) -> Any:
    """A positional argument (command-line only).

    `many=True` collects zero or more values into a list; `required=False` makes a
    single positional optional (falling back to `default`). `requires` maps another
    parameter to the value it must have for this one to be valid.
    """
    return Param(
        positional=True,
        many=many,
        required=required,
        default=default,
        convert=convert,
        help=help,
        env=False,
        requires=requires,
    )


def remainder(help: str = "") -> Any:
    """Everything after `--` (or the trailing positionals), captured verbatim.

    Command-line only; used for `exec`/`invoke` passthrough.
    """
    return Param(remainder=True, default=[], help=help, env=False)


def params_of(cls: type) -> list[Param]:
    """The parameters declared on `cls` and its bases, in declaration order.

    Base classes come first (so the flow-down globals lead), then the class's own
    parameters; a name declared again in a subclass overrides the inherited one.
    """
    found: dict[str, Param] = {}
    for klass in reversed(cls.__mro__):
        for name, value in vars(klass).items():
            if isinstance(value, Param):
                found[name] = value
    return list(found.values())


def check_requires(params: Iterable[Param], values: Mapping[str, Any]) -> str | None:
    """The first unmet cross-option requirement in `params`, or None.

    A parameter's `requires` maps another parameter to the value it must have. It is
    enforced only when the parameter is actually set (its resolved value differs from
    its default), so an unset option imposes no requirement.
    """
    for param in params:
        if not param.requires:
            continue
        if values.get(param.name) == param.default:
            continue  # not set, so its requirements do not apply
        flag = "--" + param.name.replace("_", "-")
        for required_name, required_value in param.requires.items():
            if values.get(required_name) != required_value:
                needs = "--" + required_name.replace("_", "-")
                return f"{flag} requires {needs}={required_value}"
    return None


class Action:
    """A leaf command: typed parameter attributes plus a `run` method.

    Subclass it, set `name`/`help`, declare parameters as typed class attributes
    (`option`/`flag`/`positional`/`remainder`), and implement `run`, which reads
    `self.<name>` as an ordinary typed attribute -- both its own parameters and the
    flow-down globals declared on the base.

    An action is a value-object: construct it directly with parameter values
    (`SecretsScan(mode="filesystem")`, the rest falling back to their defaults),
    and the engine constructs it the same way, from the resolved values. So `run`
    (and any method it calls) can be exercised without the CLI.
    """

    name: ClassVar[str]
    help: ClassVar[str]

    def __init__(self, **values: Any) -> None:
        params = params_of(type(self))
        unknown = set(values) - {param.name for param in params}
        if unknown:
            raise TypeError(f"unexpected arguments: {', '.join(sorted(unknown))}")
        for param in params:
            if param.name in values:
                value = values[param.name]
            elif param.remainder or param.many:
                value = list(
                    param.default or []
                )  # a fresh list, never the shared default
            else:
                value = param.default
            setattr(self, param.name, value)

    def run(self) -> int:
        """Do the work and return a process exit code."""
        raise NotImplementedError


class Group:
    """A node in the tree: a name, help, and its child commands and groups."""

    name: ClassVar[str]
    help: ClassVar[str]
    subcommands: ClassVar[tuple[type[Action | Group], ...]] = ()


class Cli:
    """The application: the command tree, the globals-carrying base, and `run`.

    `base` is the command base class whose parameters are the flow-down globals (in
    scope everywhere); every leaf command subclasses it. `log_level` names the global
    resolved first so logging is configured before the rest resolve.
    """

    def __init__(
        self,
        name: str,
        root: type[Group],
        base: type[Action],
        log_level: str = "verbosity",
    ) -> None:
        self.name = name
        self.root = root
        self.base = base
        self.log_level = log_level

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Parse `argv` (default `sys.argv[1:]`), resolve parameters, and dispatch.

        Returns an exit code: 0 on success; 2 for a usage error (unknown command or
        option, an invalid value, a missing positional, or when a subcommand is
        required); otherwise whatever the selected command's `run` returns. A help
        request (`-h`/`--help`) prints help and returns 0.
        """
        from repo_scanner.clikit.dispatch import dispatch

        return dispatch(self, argv)
