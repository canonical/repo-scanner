# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""The `reposcan config` subcommand: get or set persistent configuration."""

from repo_scanner.cli.nodes import Command, CommandGroup
from repo_scanner.cli.options import Option, Values
from repo_scanner.commands import config_cmd


class ConfigSetCommand(Command):
    name = "set"
    help = "Set a config value."
    options = (
        Option(("key",), "key", positional=True),
        Option(("value",), "value", positional=True),
    )

    def run(self, values: Values) -> int:
        return config_cmd.set_value(values["key"], values["value"])


class ConfigGetCommand(Command):
    name = "get"
    help = "Get a config value, or all values when no key is given."
    options = (Option(("key",), "key", positional=True, nargs="?", default=None),)

    def run(self, values: Values) -> int:
        return config_cmd.get_value(values["key"])


class ConfigUnsetCommand(Command):
    name = "unset"
    help = "Remove a config value."
    options = (Option(("key",), "key", positional=True),)

    def run(self, values: Values) -> int:
        return config_cmd.unset_value(values["key"])


class ConfigKeysCommand(Command):
    name = "keys"
    help = "List all supported config keys."
    options = ()

    def run(self, values: Values) -> int:
        return config_cmd.list_keys()


class ConfigOptionsCommand(Command):
    name = "options"
    help = "List the supported values for a config key."
    options = (Option(("key",), "key", positional=True),)

    def run(self, values: Values) -> int:
        return config_cmd.list_options(values["key"])


class ConfigGroup(CommandGroup):
    name = "config"
    help = "Get or set persistent configuration."
    options = ()
    subcommands = {
        "set": ConfigSetCommand,
        "get": ConfigGetCommand,
        "unset": ConfigUnsetCommand,
        "keys": ConfigKeysCommand,
        "options": ConfigOptionsCommand,
    }
