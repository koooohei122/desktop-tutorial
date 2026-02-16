from __future__ import annotations

import unittest

from growing_agent.config import AgentConfig


class TestAgentConfig(unittest.TestCase):
    def test_default_language_is_japanese(self) -> None:
        config = AgentConfig()
        self.assertEqual(config.language, "ja")

    def test_invalid_language_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgentConfig(language="fr")

    def test_non_string_language_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgentConfig(language=None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
