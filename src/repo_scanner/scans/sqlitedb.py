# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Read and write a scan artifact as a sqlite database.

The database is normalized so the artifact is both queryable and fully
reconstructable:

- a `metadata` table holds the document with its entries emptied (the kind plus all
  data not attached to an individual entry: schema/version, the SARIF tool driver and
  rules, the CycloneDX metadata and dependencies);
- an entry table (`findings` for SARIF, `components` for CycloneDX) holds one row per
  entry, with parsed columns for querying AND that entry's raw JSON in a `document`
  column, so a single finding/component reconstructs on its own.

`read` rebuilds the exact original document by splicing the entry rows (in their
stored order) back into the metadata shell. The entry table's name and columns come
from `artifact.records()`.
"""

import copy
import json
import sqlite3

from repo_scanner.scans import cyclonedx, sarif
from repo_scanner.scans.model import Artifact, ArtifactKind

# The 16-byte header every sqlite 3 database file starts with.
_MAGIC = b"SQLite format 3\x00"


def is_sqlite(data: bytes) -> bool:
    """Whether `data` begins with the sqlite database file header."""
    return data[:16] == _MAGIC


def write(artifact: Artifact, path: str) -> None:
    """Write `artifact` to a new sqlite database at `path`."""
    table = artifact.records()
    columns = [f'"{column}"' for column in table.columns]
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE metadata (kind TEXT, document TEXT)")
        connection.execute(
            "INSERT INTO metadata VALUES (?, ?)",
            (artifact.kind.value, json.dumps(_shell(artifact))),
        )
        connection.execute(
            f'CREATE TABLE "{table.name}" ({", ".join(f"{c} TEXT" for c in columns)})'
        )
        connection.executemany(
            f'INSERT INTO "{table.name}" VALUES ({", ".join("?" for _ in columns)})',
            table.rows,
        )
        connection.commit()
    finally:
        connection.close()


def read(path: str) -> Artifact | None:
    """The artifact reconstructed from the sqlite database at `path`, or None.

    Returns None if `path` is not a reposcan report database (no `metadata` table).
    """
    connection = sqlite3.connect(path)
    try:
        meta = connection.execute("SELECT kind, document FROM metadata").fetchone()
        if meta is None:
            return None
        kind, shell_json = meta
        shell = json.loads(shell_json)
        if kind == ArtifactKind.SARIF.value:
            rows = connection.execute(
                "SELECT run, document FROM findings ORDER BY rowid"
            ).fetchall()
            for run, document in rows:
                shell["runs"][int(run)]["results"].append(json.loads(document))
            return sarif.SarifDocument(shell)
        if kind == ArtifactKind.CYCLONEDX.value:
            rows = connection.execute(
                "SELECT document FROM components ORDER BY rowid"
            ).fetchall()
            shell["components"] = [json.loads(document) for (document,) in rows]
            return cyclonedx.CycloneDxDocument(shell)
        return None
    except sqlite3.Error:
        return None  # not a reposcan report database
    finally:
        connection.close()


def _shell(artifact: Artifact) -> dict:
    """The artifact's document with its entries emptied (the non-entry metadata)."""
    document = copy.deepcopy(artifact.to_dict())
    if artifact.kind is ArtifactKind.SARIF:
        for run in document.get("runs", []):
            run["results"] = []
    else:
        document["components"] = []
    return document
