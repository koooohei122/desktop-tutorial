from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from growing_agent.prompt_catalog import load_prompt_catalog


class TestPromptCatalog(unittest.TestCase):
    def test_default_catalog_resolves_browser_alias(self) -> None:
        catalog = load_prompt_catalog()
        app_name, is_browser = catalog.resolve_app("firefox")
        self.assertEqual(app_name, "Firefox")
        self.assertTrue(is_browser)

    def test_custom_catalog_allows_setting_only_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            (base / "apps.json").write_text(
                json.dumps(
                    {
                        "apps": [
                            {
                                "canonical": "AcmeNote",
                                "aliases": ["acme note", "acmenote"],
                                "is_browser": False,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            catalog = load_prompt_catalog(base)
            app_name, is_browser = catalog.resolve_app("acme note")
            self.assertEqual(app_name, "AcmeNote")
            self.assertFalse(is_browser)

    def test_workflow_template_render(self) -> None:
        catalog = load_prompt_catalog()
        rendered = catalog.render_workflow("open_app", {"app_name": "Obsidian"})
        self.assertTrue(rendered)
        self.assertEqual(rendered[0]["payload"]["app_name"], "Obsidian")


if __name__ == "__main__":
    unittest.main()
