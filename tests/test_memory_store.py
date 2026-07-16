"""Tests for `memory/store.py`'s `ConversationStore` (Milestone 9, Part A).

Unlike the LLM/vision/TTS engines, this module has no optional-extra
dependency to fake -- `sqlite3` is in the Python standard library -- so
these tests run against a real SQLite database file under `tmp_path`,
not a mock. Nothing here is simulated.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from memory.store import ConversationStore


def test_creates_db_file_and_parent_dirs(tmp_path: Path) -> None:
    db_path = tmp_path / "nested" / "conversations.db"
    assert not db_path.exists()

    ConversationStore(db_path)

    assert db_path.exists()


def test_save_turn_returns_incrementing_ids(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "conversations.db")

    id1 = store.save_turn("hello", "hi there")
    id2 = store.save_turn("second query", "second response")

    assert id1 == 1
    assert id2 == 2


def test_save_turn_persists_real_data_readable_via_raw_sqlite(tmp_path: Path) -> None:
    db_path = tmp_path / "conversations.db"
    store = ConversationStore(db_path)
    store.save_turn("what's the weather", "I can't check that yet")

    # Bypass the store entirely and read the file with a fresh raw
    # connection, to confirm data actually landed on disk correctly
    # rather than just in some in-memory structure.
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT query, response FROM turns").fetchone()

    assert row == ("what's the weather", "I can't check that yet")


def test_count_turns(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "conversations.db")
    assert store.count_turns() == 0

    store.save_turn("q1", "r1")
    store.save_turn("q2", "r2")
    store.save_turn("q3", "r3")

    assert store.count_turns() == 3


def test_get_recent_turns_orders_newest_first_and_respects_limit(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "conversations.db")
    store.save_turn("first", "r1")
    store.save_turn("second", "r2")
    store.save_turn("third", "r3")

    recent = store.get_recent_turns(limit=2)

    assert len(recent) == 2
    assert recent[0]["query"] == "third"
    assert recent[1]["query"] == "second"


def test_explicit_timestamp_is_stored_as_given(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "conversations.db")
    fixed_ts = 1_700_000_000.0

    store.save_turn("q", "r", timestamp=fixed_ts)

    turns = store.get_recent_turns(limit=1)
    assert turns[0]["timestamp"] == fixed_ts


def test_omitted_timestamp_defaults_to_now(tmp_path: Path) -> None:
    store = ConversationStore(tmp_path / "conversations.db")
    before = time.time()

    store.save_turn("q", "r")

    after = time.time()
    turns = store.get_recent_turns(limit=1)
    assert before <= turns[0]["timestamp"] <= after


def test_reopening_same_db_path_preserves_existing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "conversations.db"
    store1 = ConversationStore(db_path)
    store1.save_turn("q1", "r1")

    # Simulate a second worker thread/session opening its own
    # ConversationStore against the same file (matches how main.py's
    # worker threads each go through ConversationStore.save_turn, which
    # opens a fresh connection per call rather than sharing one).
    store2 = ConversationStore(db_path)
    store2.save_turn("q2", "r2")

    assert store1.count_turns() == 2
    assert store2.count_turns() == 2


def test_unwritable_db_path_raises_runtime_error(tmp_path: Path) -> None:
    # A path whose parent is actually a *file*, not a directory, can never
    # be created -- forces the mkdir/connect path to fail so we can check
    # construction surfaces a clear RuntimeError rather than a raw
    # sqlite3.Error or an unrelated OSError.
    blocking_file = tmp_path / "not_a_directory"
    blocking_file.write_text("blocking")
    bad_db_path = blocking_file / "conversations.db"

    with pytest.raises(RuntimeError, match="Could not open/initialize"):
        ConversationStore(bad_db_path)
