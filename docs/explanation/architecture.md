# Architecture

reposcan is a scan orchestrator, not a scanner. It drives a fixed set of pinned,
third-party tools, runs them in an isolated environment against a repository,
and merges their output into one report. This document describes the pieces and
why they are shaped the way they are.

## Threat model

The repository under scan is untrusted: it may contain hostile code, and merely
scanning it must not let that code run with any privilege it should not have.
Two design rules follow from this and recur below. The repository is mounted
read-only, and the tools run as an unprivileged user. The tools parse what is
committed rather than building or installing the repository, so scanning a
repository does not execute it.

## Execution contexts and backends

An execution context is a place reposcan can run commands, exposing a small
lifecycle: start, run, stop. There are three: a local context on the host,
Docker, and LXD. A backend decides whether its context is available and
constructs it; backend selection prefers LXD, then Docker, then local (see
[choose a backend](../how-to/choose-a-backend.md)).

The container backends bind-mount the target repository read-only at
`/scan/<name>`, keeping the repository's own directory name so tool output reads
naturally, and run each tool as an unprivileged user (UID 10000) via `setpriv`.
The local backend runs the tools as the invoking user with no isolation, which
is why it is discouraged for untrusted repositories.

## The tool image

Every pinned tool is installed into one image, so a container scan starts from a
single, reproducible environment. The image is content-addressed: its identity
is a hash of the build script, which embeds every tool's version, download URL,
and checksum. A container backend builds the image on demand the first time it
is needed and reuses it while the hash is unchanged; a change to any tool
version or hash, or to the base image, yields a new hash and triggers a rebuild.

The same image can be published to a registry and pulled instead of built. A
pulled image carries no prior trust, so reposcan verifies it: a digest-pinned
reference is trusted by content, and a tag-only reference is pinned on first use
and refused later if the tag has moved (see
[use a published image](../how-to/use-a-published-image.md)).

## Tools

Each tool is defined once in a registry with its supply-chain pins inline:
native binaries by per-platform download URL and sha256, Go tools by their
checksum-database hashes, and PyPI tools by a hash-locked requirements file. The
tools are installed the same way whether baked into the image or installed onto
the host by `bootstrap`.

## The scan model

A scan is a set of tool invocations over a target plus a rule for consolidating
their outputs. The relationship between scans and tools is many-to-many: a scan
may drive several tools (the `sbom` scan runs three), and a tool may serve
several scans (trivy serves both `sbom` and `sca`). A scan translates its own
options into each tool's flags, and its consolidation step merges the tools'
outputs into one artifact.

Findings scans produce SARIF; the `sbom` scan produces a CycloneDX inventory.
When several tools contribute, their results are merged and de-duplicated -- by
rule and location for SARIF, by package URL for CycloneDX -- and each entry is
annotated with the tools that reported it. Because the tools disagree on exit
conventions, `scan` presents uniform exit codes rather than passing a tool's
code through (see [scans](../reference/scans.md)).

The driver also handles two cross-cutting concerns for every scan so the scan
modules stay simple: it excludes git-ignored paths from filesystem-walking tools
(see [path exclusion](path-exclusion.md)), and it records each executed command
as provenance in the report.

## Dependency resolution

The `sbom` and `sca` scans see a full transitive dependency tree only from a
committed lockfile. When the scan has network access, a resolution pre-step runs
each ecosystem's package manager in resolve-only mode to generate the missing
lockfiles before the tools run. It runs no untrusted code by default and copies
the repository to a writable location first, since the mount is read-only. This
is the one place scanning may execute repository code, and only when explicitly
enabled with `--allow-code-execution`. The mechanism and its rationale are in
[SBOM generation](sbom-generation.md).

## Output

Every report reposcan prints is routed through one output module. The default is
a concise table on stdout; `--format` selects the native SARIF or CycloneDX
JSON, or a sqlite database that is both queryable and losslessly
reconstructable. The `render` command reads a saved report back and converts it
between the same formats without re-running the scan.
