# Run a scan

`reposcan scan <type> <path>` runs one scan type against a repository directory.
The scan catalog and each scan's tools are in the
[scans reference](../reference/scans.md).

## Choose a scan type

```
reposcan scan secrets  ./repo    # leaked credentials (trufflehog)
reposcan scan sast     ./repo    # static analysis (semgrep)
reposcan scan iac      ./repo    # infrastructure-as-code (checkov)
reposcan scan workflow ./repo    # CI/CD workflows (zizmor, poutine)
reposcan scan sca      ./repo    # dependency vulnerabilities (trivy, grype, govulncheck)
reposcan scan sbom     ./repo    # software bill of materials (trivy, syft, cdxgen)
```

Run `reposcan scan --help` for the list, or `reposcan scan <type> --help` for a
scan's own options.

## Read the exit code

Findings scans use the exit code to report the outcome, so they fit into
pipelines:

- `0`: the scan ran and found nothing.
- `3`: the scan ran and reported one or more findings.
- `1`: a scan or tool error.
- `2`: a usage error (unknown scan, bad path, or an output file that already
  exists).

The `sbom` scan is an inventory rather than a pass/fail check, so it exits `0`
whenever it runs.

## Choose the output format

By default reposcan prints a concise table to stdout, capped at a row limit.
Override the format with `--format` and the destination with `-o`:

```
reposcan scan sast ./repo                        # table on stdout
reposcan scan sast ./repo --format json          # SARIF JSON on stdout
reposcan scan sast ./repo --format json -o out.sarif
reposcan scan sbom ./repo --format sqlite -o sbom.db
```

Findings scans emit SARIF; `sbom` emits CycloneDX. The `sqlite` format is
queryable and fully reconstructable, and it requires a file (`-o`). Two table
options tune the stdout view:

- `--limit N` (`-n`) sets the maximum rows shown (the rest are counted in a log
  line).
- `--wrap N` sets the maximum lines a long cell may wrap across (default 4;
  `--wrap 1` keeps each cell to a single clipped line).

To convert a report you already saved, use
[`render`](../reference/commands.md#render) rather than re-running the scan.

## Pass scan-specific options

Some scans take their own options. The `secrets` scan, for example, chooses
between git-history and working-tree mode and can limit the history depth:

```
reposcan scan secrets ./repo --mode filesystem
reposcan scan secrets ./repo --mode history --depth 500
```

## Related tasks

- Select where the tools run: [choose a backend](choose-a-backend.md).
- Use a published tool image: [use a published image](use-a-published-image.md).
