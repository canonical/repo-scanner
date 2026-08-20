# Configuration

reposcan reads a small set of settings, each resolvable from four sources.
Persisted settings live in a flat key/value file under `$XDG_CONFIG_HOME`
(default `~/.config/reposcan/`) and are managed with the
[`config`](commands.md#config) commands.

## Resolution order

Each setting resolves from, in order of precedence:

1. command-line options
1. environment variables
1. saved config values
1. built-in defaults

## Config options

The list of options that can be set in persistent configuration is exactly the
the list of global options in [commands](./commands.md)

## Storage locations

reposcan follows the XDG base directory convention:

- Config: `$XDG_CONFIG_HOME/reposcan/` (default `~/.config/reposcan/`).
- Host-installed tools (from `bootstrap`): `$XDG_DATA_HOME/reposcan/` (default
  `~/.local/share/reposcan/`).
- Dependency-resolution scratch copies (local backend-only):
  `$XDG_CACHE_HOME/reposcan/` (default `~/.cache/reposcan/`).
