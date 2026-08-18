# Scans

Each scan runs one or more tools against a repository and consolidates their
output into a single artifact: SARIF for findings scans, CycloneDX for the SBOM
inventory. Where several tools contribute, their results are merged and
de-duplicated, and each finding or component is annotated with the tools that
reported it.

Findings scans exit `0` (no findings), `3` (findings), `1` (error), or `2`
(usage). The `sbom` scan is an inventory and exits `0` whenever it runs. All
scans accept the shared output options (`-o`, `-f/--format`, `-n/--limit`,
`--wrap`); see [commands](commands.md#scan).

## secrets

Leaked credentials, via trufflehog. Emits SARIF. Options:

- `--mode <history|filesystem>`: scan the git history (default) or only the
  working-tree files.
- `--depth <N>`: in history mode, scan only the most recent N commits (default:
  all).

## sast

Static analysis of source code, via semgrep. Emits SARIF.

## iac

Infrastructure-as-code checks, via checkov. Emits SARIF.

## workflow

CI/CD workflow auditing, via zizmor and poutine. Emits SARIF.

## sca

Dependency vulnerabilities, via trivy, grype, and govulncheck. Emits SARIF.
govulncheck applies only to Go modules and is skipped on other repositories.
This scan resolves dependencies first (see
[SBOM generation](../explanation/sbom-generation.md)) and accepts
`--allow-code-execution` and `--include-dev-dependencies`.

## sbom

Software bill of materials, via trivy, syft, and cdxgen. Emits CycloneDX. This
scan resolves dependencies first and accepts `--allow-code-execution` and
`--include-dev-dependencies`. How it generates the inventory, its dev-dependency
handling, and its coverage per ecosystem, are covered in
[SBOM generation](../explanation/sbom-generation.md).
