# repo-scanner

`repo-scanner` (package name) or `reposcan` (CLI name) is a tool for running
security scans against a locally-cloned repository.

By default, it executes all scans in ephemeral containers. It defaults to LXD
and falls back to Docker based on availability. It supports running scans
directly on the local host, though this is discouraged.
