from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from growing_agent.memory import MemoryStore, build_default_state


class TestMemoryStore(unittest.TestCase):
    def test_read_missing_returns_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            store = MemoryStore(state_path)
            self.assertEqual(store.read_state(), build_default_state())

    def test_write_and_read_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            store = MemoryStore(state_path)
            expected = {
                "iteration": 4,
                "last_score": 0.75,
                "history": [{"iteration": 4, "score": 0.75}],
                "language": "ja",
            }
            store.write_state(expected)
            self.assertEqual(store.read_state(), expected)

    def test_corrupt_file_is_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            state_path.write_text("{not-valid-json", encoding="utf-8")
            store = MemoryStore(state_path)
            state = store.read_state()
            self.assertEqual(state, build_default_state())

            backups = list(Path(tmpdir).glob("state.json.corrupt-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue(backups[0].read_text(encoding="utf-8").startswith("{not"))

            # Corrupt file should be replaced with a valid default state.
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted, build_default_state())

            # A second read should not create new backup files.
            self.assertEqual(store.read_state(), build_default_state())
            backups_after_second_read = list(Path(tmpdir).glob("state.json.corrupt-*"))
            self.assertEqual(len(backups_after_second_read), 1)

    def test_reset_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            store = MemoryStore(state_path)
            store.write_state({"iteration": 99, "last_score": 0.2, "history": [1]})
            reset = store.reset_state()
            self.assertEqual(reset, build_default_state())
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted, build_default_state())


if __name__ == "__main__":
    unittest.main()
