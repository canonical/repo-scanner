# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the generic sqlite tabular store (repo_scanner.sqlitedb)."""

import os
import sqlite3
import tempfile

from repo_scanner.sqlitedb import Table, is_sqlite, read, write


def test_is_sqlite_detects_the_header() -> None:
    assert is_sqlite(b"SQLite format 3\x00rest of the file")
    assert not is_sqlite(b'{"bomFormat": "CycloneDX"}')


def test_write_then_read_round_trips_a_table_in_insertion_order() -> None:
    table = Table("items", ("id", "name"), [("2", "b"), ("1", "a")])
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "x.db")
        write(path, [table])
        got = read(path, "items")
    assert got is not None
    assert got.columns == ("id", "name")
    assert got.rows == [("2", "b"), ("1", "a")]  # stored order, not sorted


def test_read_returns_none_for_a_missing_table_or_non_database() -> None:
    with tempfile.TemporaryDirectory() as directory:
        db = os.path.join(directory, "x.db")
        write(db, [Table("present", ("a",), [("1",)])])
        assert read(db, "absent") is None  # table not in the database

        not_a_db = os.path.join(directory, "note.txt")
        with open(not_a_db, "w") as handle:
            handle.write("not a database")
        assert read(not_a_db, "present") is None
        # reposcan catches/handles sqlite3 exceptions
        assert not isinstance(read(not_a_db, "present"), sqlite3.Error)
