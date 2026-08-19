# Configuration

reposcan reads a small set of settings, each resolvable from four sources.
Persisted settings live in a flat key/value file under `$XDG_CONFIG_HOME`
(default `~/.config/reposcan/`) and are managed with the
[`config`](commands.md#config) commands.

## Resolution order

Each setting resolves from, in order of precedence:

1. the command-line option,
1. the environment variable,
1. the saved config value,
1. the built-in default.

When two sources set the same value differently, reposcan logs which source won.
An environment or config value that fails validation is logged and skipped,
falling through to the next source.

## Keys

- `backend`: the execution backend tools run in. Option `--backend`, env
  `REPOSCAN_BACKEND`, values `auto`/`docker`/`lxd`/`local`, fallback `auto`.
  `auto` selects Docker, then LXD, then local, by availability.
- `verbosity`: the lowest log level written to stderr. Option
  `-v`/`--verbosity`, env `REPOSCAN_VERBOSITY`, values
  `debug`/`info`/`warning`/`error`/`critical`, fallback `info`.
- `uid`: the UID for in-container processes. Option `--uid`, env `REPOSCAN_UID`,
  a positive integer, fallback the built-in scan user. The local backend ignores
  it and runs as the invoking user.
- `image`: the tool image to run. Config-only (no option or environment
  variable), `canonical` (this project's published image) or any OCI reference,
  unset to build the image locally. See
  [use a published image](../how-to/use-a-published-image.md).

## Storage locations

reposcan follows the XDG base directory convention:

- Config: `$XDG_CONFIG_HOME/reposcan/` (default `~/.config/reposcan/`).
- Host-installed tools (from `bootstrap`): `$XDG_DATA_HOME/reposcan/` (default
  `~/.local/share/reposcan/`).
- Dependency-resolution scratch copies (local backend-only):
  `$XDG_CACHE_HOME/reposcan/` (default `~/.cache/reposcan/`).
