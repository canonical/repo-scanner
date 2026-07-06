# repo-scanner

`repo-scanner` (package name) or `reposcan` (CLI name) is a tool for running
security scans against a locally-cloned repository.

By default, it executes all scans in ephemeral containers. It defaults to LXD
and falls back to Docker based on availability. It supports running scans
directly on the local host, though this is discouraged.

## Bundled tools and their licenses

`reposcan` drives a fixed set of third-party tools, each pinned by hash in
`src/repo_scanner/tools/registry.py`. Every tool remains under its own upstream
license, linked below:

| Tool                                                        | Purpose                                  | License                                                                       |
| ----------------------------------------------------------- | ---------------------------------------- | ----------------------------------------------------------------------------- |
| [semgrep](https://github.com/semgrep/semgrep)               | SAST                                     | [LGPL-2.1](https://github.com/semgrep/semgrep/blob/develop/LICENSE)           |
| [checkov](https://github.com/bridgecrewio/checkov)          | Infrastructure-as-code scanning          | [Apache-2.0](https://github.com/bridgecrewio/checkov/blob/main/LICENSE)       |
| [zizmor](https://github.com/zizmorcore/zizmor)              | GitHub Actions auditing                  | [MIT](https://github.com/zizmorcore/zizmor/blob/main/LICENSE)                 |
| [poutine](https://github.com/boostsecurityio/poutine)       | CI/CD pipeline auditing                  | [Apache-2.0](https://github.com/boostsecurityio/poutine/blob/main/LICENSE)    |
| [trufflehog](https://github.com/trufflesecurity/trufflehog) | Secret scanning                          | [AGPL-3.0](https://github.com/trufflesecurity/trufflehog/blob/main/LICENSE)   |
| [syft](https://github.com/anchore/syft)                     | SBOM generation                          | [Apache-2.0](https://github.com/anchore/syft/blob/main/LICENSE)               |
| [grype](https://github.com/anchore/grype)                   | Vulnerability scanning (SCA)             | [Apache-2.0](https://github.com/anchore/grype/blob/main/LICENSE)              |
| [trivy](https://github.com/aquasecurity/trivy)              | SBOM and vulnerability scanning          | [Apache-2.0](https://github.com/aquasecurity/trivy/blob/main/LICENSE)         |
| [cdxgen](https://github.com/CycloneDX/cdxgen)               | SBOM generation                          | [Apache-2.0](https://github.com/CycloneDX/cdxgen/blob/master/LICENSE)         |
| [govulncheck](https://github.com/golang/vuln)               | Go vulnerability scanning                | [BSD-3-Clause](https://github.com/golang/vuln/blob/master/LICENSE)            |
| [uv](https://github.com/astral-sh/uv)                       | Python installer (build prerequisite)    | [Apache-2.0 or MIT](https://github.com/astral-sh/uv/blob/main/LICENSE-APACHE) |
| [Go toolchain](https://go.dev)                              | Builds the Go tools (build prerequisite) | [BSD-3-Clause](https://go.dev/LICENSE)                                        |

### License compliance

`reposcan` does not modify, fork, or link any of these tools into its own code.
Each is installed from its official upstream release, pinned by hash, and
invoked as a separate, unmodified executable across a process boundary. Running
a program this way is mere aggregation, not the creation of a derivative work,
so no tool's license reaches into `reposcan`'s own source.

- Permissive licenses (Apache-2.0, MIT, BSD-3-Clause) allow use and
  redistribution provided the copyright and license notices are preserved. When
  a built image bundles a tool's binary, that tool's own license and notice
  files are kept alongside it.
- LGPL-2.1 (semgrep): `reposcan` uses semgrep as a standalone program rather
  than linking its library, so it is a plain user of the software. Notices are
  preserved and the corresponding source is the pinned upstream release.
- AGPL-3.0 (trufflehog): the strongest copyleft here. Its obligations attach to
  conveying a modified version, including over a network. `reposcan` runs
  trufflehog unmodified as a separate process and incorporates none of its code,
  so it creates no derivative work. Where a published image redistributes the
  trufflehog binary, AGPL-3.0's source-availability requirement is satisfied by
  the corresponding unmodified upstream source at the pinned release.

Because every tool is pinned by hash to an official upstream release (see the
`# verify:` links in the registry), the exact corresponding source for any
redistributed binary is always identifiable. Local bootstrap, which downloads
each tool from upstream at run time, redistributes nothing; redistribution
obligations (notice retention, source availability) apply only to published
images that bundle the binaries. This summary is provided in good faith and is
not legal advice; consult each linked license for its authoritative terms.
