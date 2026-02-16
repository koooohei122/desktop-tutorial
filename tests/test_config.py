from __future__ import annotations

import unittest

from growing_agent.config import AgentConfig


class TestAgentConfig(unittest.TestCase):
    def test_default_language_is_english(self) -> None:
        config = AgentConfig()
        self.assertEqual(config.language, "en")

    def test_supported_languages_are_accepted(self) -> None:
        for language in ("en", "zh", "it", "fr", "pt", "hi", "ar", "ja", "es"):
            config = AgentConfig(language=language)
            self.assertEqual(config.language, language)

    def test_invalid_language_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgentConfig(language="fr")

    def test_non_string_language_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgentConfig(language=None)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
