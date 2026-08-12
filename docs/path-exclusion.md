# Path exclusion for filesystem scanners

## Problem

The SBOM tools (trivy, syft, cdxgen) and the SCA tools (trivy, grype) catalog a
repository by walking its working tree. By default they descend into directories
a developer would never ship: virtualenvs (`.venv`, `.tox`), dependency caches
(`node_modules`), and build output. These are almost always listed in the repo's
`.gitignore`, so the scanners report packages that are not really part of the
project. Observed: syft cataloging packages under `.venv` and `.tox`.

Since scans run with the target repo as the working directory (see `run_scan`),
each tool's own path filters resolve relative to the repo root, which makes the
fix below straightforward.

## Findings per tool

None of the three SBOM tools honors `.gitignore` natively. Each has an open,
unmerged feature request. Each offers a manual path-exclusion flag instead, with
a different glob dialect and different anchoring rules.

### syft 1.46.0

- No `.gitignore` support (open, unmerged: anchore/syft#4026, PR #4437).
- Flag: `--exclude <glob>` (repeatable), or `exclude:` list in `.syft.yaml`.
- Dialect: doublestar (`github.com/bmatcuk/doublestar/v4`). Patterns are matched
  against each entry's absolute path, anchored to the `dir:` source root. A
  pattern MUST start with `./`, `*/`, or `**/` (anything else is a hard error).
- `a/**` matches `a` itself as well as its contents, so `**/.venv/**` prunes the
  `.venv` directory (SkipDir) at any depth. No negation (`!`) support
  (anchore/syft#4702).
- Docs: https://oss.anchore.com/docs/guides/sbom/file-selection/ ,
  https://github.com/anchore/syft/wiki/excluding-file-paths

### trivy 0.72.0

- No `.gitignore` support (open: aquasecurity/trivy#3670).
- Flags: `--skip-dirs <glob>`, `--skip-files <glob>` (repeatable), or
  `scan.skip-dirs`/`scan.skip-files` in `trivy.yaml`. Applies to `trivy fs` for
  both the CycloneDX SBOM and the vuln (SCA) scan.
- Dialect: doublestar, matched relative to the scan target / CWD (now the same
  path). Gotcha: a bare `**/X` does NOT match a root-level `X` (`**/.terraform`
  skips `foo/.terraform` but not `./.terraform`), so a wildcard exclude needs
  BOTH `X` and `**/X`.
- `.trivyignore` is NOT a path filter: it suppresses vulnerability/rule IDs from
  findings after the scan, and has no effect on what gets cataloged. (Maintainer
  confirmation: aquasecurity/trivy discussion #4584.)
- Docs:
  https://github.com/aquasecurity/trivy/blob/v0.72.0/docs/guide/configuration/skipping.md

### cdxgen 12.7.0

- No `.gitignore` support (no gitignore code in the source at all).
- Flag: `--exclude <glob>` (repeatable; not comma-separated). No env-var form.
- Dialect: the `glob`/minimatch family (not picomatch). Globs run with
  `nodir: true`, so patterns must match FILES under a directory: use the
  `**/<name>/**` form (both a depth prefix and a `/**` suffix); bare `**/.venv`
  will not reliably exclude its contents. No negation support.
- Default ignores are only `**/.git/**`, `**/.hg/**`, and (conditionally)
  `**/node_modules/**`. Two root causes of the reported leakage:
  - Python discovery of `site-packages`/`*.whl`/`*.egg-info` runs with
    `includeDot: true`, which deliberately descends into hidden dirs like
    `.venv` and `.tox`.
  - `node_modules` is deliberately walked when the glob targets `package.json`
    (to read installed packages), so it is not always excluded by default. An
    explicit `--exclude` overrides both (excludes are unconditionally appended
    to the ignore list). Do NOT set `CDXGEN_NO_IGNORE` (it disables the default
    ignores).
- Docs: https://github.com/CycloneDX/cdxgen/blob/v12.7.0/docs/ADVANCED.md ,
  https://github.com/CycloneDX/cdxgen/blob/v12.7.0/docs/ENV.md

## Fix

The exclusion set is derived from git and translated per tool.

The command:

```
git ls-files -z -o -i --exclude-standard --directory
```

...is run in the repo root to list ignored entries, with wholly-ignored
directories collapsed to `<dir>/`. Each path is mapped to tool flags:

| Tool        | ignored dir `d/`   | ignored file `f` |
| ----------- | ------------------ | ---------------- |
| syft, grype | `--exclude ./d/**` | `--exclude ./f`  |
| trivy       | `--skip-dirs d`    | `--skip-files f` |
| cdxgen      | `--exclude d/**`   | `--exclude f`    |

CWD is the repo root, so paths resolve directly and no wildcard anchoring is
needed. A non-git target, or unavailable git, yields no paths and no exclusions.

### Where it plugs in

`scans/exclude.py`:

- `IgnoredPaths.from_context(ctx, target)` runs the git lookup and returns the
  ignored directories and files.
- `build_exclude_flags(tool, ignored)` maps them to `tool`'s flags per the table
  above; empty for non-filesystem tools.

`run_scan` (`scans/model.py`) computes the ignored set once per scan, only when
an invocation names a tool in `EXCLUDABLE_TOOLS` (`trivy`, `syft`, `grype`,
`cdxgen`), then appends each tool's flags to its command. Scan modules are
unchanged. The SBOM scan (trivy, syft, cdxgen) and SCA scan (trivy, grype) are
covered; grype shares syft's dialect. govulncheck is unaffected: it analyzes the
Go module graph, not a file walk.
