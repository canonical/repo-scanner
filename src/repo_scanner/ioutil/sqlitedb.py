# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Read and write tabular data as a sqlite database.

A generic utility with no domain knowledge: it stores and retrieves named `Table`s
(each a set of string columns and rows). Every column is TEXT; callers serialize any
richer values themselves. `read` returns a table's rows in insertion order, or None
when the table (or the database) is not there.
"""

import sqlite3
from collections.abc import Iterable
from typing import NamedTuple

# The 16-byte header every sqlite 3 database file starts with.
_MAGIC = b"SQLite format 3\x00"


class Table(NamedTuple):
    """A named table of string columns and rows."""

    name: str
    columns: tuple[str, ...]
    rows: list[tuple[str, ...]]


def is_sqlite(data: bytes) -> bool:
    """Whether `data` begins with the sqlite database file header."""
    return data[:16] == _MAGIC


def write(path: str, tables: Iterable[Table]) -> None:
    """Write each `Table` to a new sqlite database at `path`."""
    connection = sqlite3.connect(path)
    try:
        for table in tables:
            columns = [f'"{column}"' for column in table.columns]
            column_defs = ", ".join(f"{column} TEXT" for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            connection.execute(f'CREATE TABLE "{table.name}" ({column_defs})')
            connection.executemany(
                f'INSERT INTO "{table.name}" VALUES ({placeholders})', table.rows
            )
        connection.commit()
    finally:
        connection.close()


def read(path: str, name: str) -> Table | None:
    """The named table's columns and rows (in insertion order), or None.

    Returns None when the table does not exist or `path` is not a sqlite database.
    """
    connection = sqlite3.connect(path)
    try:
        cursor = connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid')
        columns = tuple(description[0] for description in cursor.description)
        return Table(name, columns, cursor.fetchall())
    except sqlite3.Error:
        return None
    finally:
        connection.close()
