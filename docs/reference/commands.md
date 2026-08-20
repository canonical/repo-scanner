# Commands

The CLI is `reposcan`, invoked as:

```
reposcan <command> [options]
```

A command's own options follow the command. Global options may appear anywhere
on the command line.

## Global options

These resolve from CLI parameters, then the environment variable, then the saved
config, then the default (see [configuration](configuration.md)).

- `-v, --verbosity <level>`: lowest log level written to stderr, one of `debug`,
  `info`, `warning`, `error`, `critical`. Env `REPOSCAN_VERBOSITY`, config
  `verbosity`, fallback `info`.
- `--backend <name>`: where tools run, one of `auto`, `docker`, `lxd`, `local`.
  Env `REPOSCAN_BACKEND`, config `backend`, fallback `auto`.
- `--uid <UID>`: UID for in-container processes (ignored by the local backend).
  Env `REPOSCAN_UID`, config `uid`, fallback the built-in scan user.

## scan

`reposcan scan <type> <path>` runs one scan against a repository directory and
maps the outcome to an exit code. Types are `secrets`, `sast`, `iac`,
`workflow`, `sca`, and `sbom`; see the [scans reference](scans.md) for each
scan's tools, artifact, and options. Common options:

- `-o, --output <FILE>`: write the report to a file instead of stdout (required
  for `--format sqlite`; refuses to overwrite an existing file).
- `-f, --format <fmt>`: `table` (default, stdout), `json`, or `sqlite`.
- `-n, --limit <N>`: maximum table rows shown (default 20).
- `--wrap <N>`: maximum lines a long table cell may wrap across (default 4; `1`
  keeps each cell to a single clipped line).
- `--allow-code-execution`: for `sbom` and `sca` only, let dependency resolution
  build source packages, which runs untrusted code (off by default). See
  [SBOM generation](../explanation/sbom-generation.md).

Exit codes: `0` ran with no findings, `3` findings, `1` scan or tool error, `2`
usage error. The `sbom` inventory always exits `0` when it runs.

## render

`reposcan render <path>` converts a saved report between formats without
re-running a scan. The input is a SARIF or CycloneDX JSON file, or a reposcan
sqlite database (detected by content). Options: `-o/--output`, `-f/--format`,
`-n/--limit`, and `--wrap`, as for `scan`. Runs locally with no backend.

## exec

`reposcan exec -- <command>` runs an arbitrary command in the selected execution
context, including any installed scanning tool. Separate the command from
reposcan's own options with `--`. Option: `--timeout <SECONDS>` kills the command
after that long.

```
reposcan exec -- trivy --version
reposcan exec -- semgrep -h
```

The scanning tools are symlinked onto `/usr/local/bin` in the tool image, so they
are on `PATH` and can be run by name. Use `reposcan tools` to list them.

## tools

`reposcan tools` lists the scanning tools and whether each is installed in the
selected backend.

## bootstrap

`reposcan bootstrap [tools...]` installs tools onto the host (or into the
backend when `--backend` is given). With no tool names it installs all of them.
A host install is confirmed interactively first unless `--confirm` is passed.
The container backends do not need this; they build or pull the tool image.

## image

- `reposcan image build [--backend <name>]`: build (or rebuild) the tool image
  and print its reference. Reuses an existing image when nothing changed.
- `reposcan image cache list`: list the recorded built and pulled images.
- `reposcan image cache remove <reference>`: remove one record.
- `reposcan image cache clear`: remove all records.

See [use a published image](../how-to/use-a-published-image.md).

## config

Persist and inspect settings (see [configuration](configuration.md)).

- `reposcan config set <key> <value>`
- `reposcan config get [key]`: one value, or all when no key is given.
- `reposcan config unset <key>`
- `reposcan config keys`: list the supported keys.
- `reposcan config options <key>`: list a key's allowed values.
