from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from growing_agent.prompt_planner import plan_prompt_task


class TestPromptPlanner(unittest.TestCase):
    def test_plan_japanese_chrome_youtube_prompt(self) -> None:
        prompt = "google chromeを開いて、今日におすすめな曲をyoutubeで流して"
        planned = plan_prompt_task(prompt=prompt, priority=9)
        self.assertEqual(planned["intent"], "youtube_music_recommendation")
        self.assertEqual(planned["task_type"], "mission")
        self.assertEqual(int(planned["priority"]), 9)
        payload = planned["payload"]
        self.assertIsInstance(payload, dict)
        steps = payload.get("steps", [])
        self.assertTrue(isinstance(steps, list) and steps)
        self.assertEqual(steps[0]["task_type"], "command")
        command = steps[0]["payload"]["command"]
        self.assertEqual(command[0], "google-chrome")
        self.assertIn("youtube.com/results", command[1])
        self.assertNotIn("chrome", planned["preview"]["query"].lower())

    def test_plan_unsupported_prompt_raises(self) -> None:
        with self.assertRaises(ValueError):
            plan_prompt_task(prompt="状態を確認して", priority=5)

    def test_plan_generic_open_and_search_prompt(self) -> None:
        prompt = "Firefoxを開いて、python asyncioをgoogleで検索して"
        planned = plan_prompt_task(prompt=prompt, priority=7)
        self.assertEqual(planned["intent"], "generic_prompt_workflow")
        self.assertEqual(planned["task_type"], "mission")
        payload = planned["payload"]
        steps = payload.get("steps", [])
        self.assertTrue(isinstance(steps, list) and len(steps) >= 2)
        self.assertEqual(steps[0]["task_type"], "desktop_action")
        self.assertEqual(steps[0]["payload"]["action"], "launch_app")
        self.assertEqual(steps[0]["payload"]["app_name"], "Firefox")
        type_steps = [
            step
            for step in steps
            if step.get("task_type") == "desktop_action"
            and step.get("payload", {}).get("action") == "type_text"
        ]
        self.assertTrue(type_steps)
        self.assertIn("google.com/search", type_steps[0]["payload"]["text"])

    def test_plan_generic_type_and_hotkey_prompt(self) -> None:
        prompt = "「hello world」と入力して、Enterを押して"
        planned = plan_prompt_task(prompt=prompt, priority=6)
        self.assertEqual(planned["intent"], "generic_prompt_workflow")
        steps = planned["payload"]["steps"]
        type_steps = [
            step
            for step in steps
            if step.get("task_type") == "desktop_action"
            and step.get("payload", {}).get("action") == "type_text"
        ]
        hotkey_steps = [
            step
            for step in steps
            if step.get("task_type") == "desktop_action"
            and step.get("payload", {}).get("action") == "hotkey"
        ]
        self.assertTrue(type_steps)
        self.assertEqual(type_steps[0]["payload"]["text"], "hello world")
        self.assertTrue(hotkey_steps)
        self.assertEqual(hotkey_steps[0]["payload"]["keys"], ["Return"])

    def test_plan_notepad_diary_prompt(self) -> None:
        prompt = "メモ帳を開いて今日の日記を書いて"
        planned = plan_prompt_task(prompt=prompt, priority=8)
        self.assertEqual(planned["intent"], "generic_prompt_workflow")
        steps = planned["payload"]["steps"]
        self.assertTrue(steps)
        self.assertEqual(steps[0]["task_type"], "desktop_action")
        self.assertEqual(steps[0]["payload"]["action"], "launch_app")
        self.assertEqual(steps[0]["payload"]["app_name"], "メモ帳")

        type_steps = [
            step
            for step in steps
            if step.get("task_type") == "desktop_action"
            and step.get("payload", {}).get("action") == "type_text"
        ]
        self.assertTrue(type_steps)
        diary_text = type_steps[-1]["payload"]["text"]
        self.assertIn("日記", diary_text)
        self.assertIn(date.today().isoformat(), diary_text)

    def test_plan_open_app_with_custom_catalog_settings_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_dir = Path(tmpdir)
            (catalog_dir / "apps.json").write_text(
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
            planned = plan_prompt_task(
                prompt="acme noteを開いて",
                priority=8,
                catalog_dir=str(catalog_dir),
            )
            steps = planned["payload"]["steps"]
            self.assertTrue(steps)
            self.assertEqual(steps[0]["payload"]["action"], "launch_app")
            self.assertEqual(steps[0]["payload"]["app_name"], "AcmeNote")

    def test_plan_with_plugin_file_adds_new_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_file = Path(tmpdir) / "plugin_wait.py"
            plugin_file.write_text(
                (
                    "def register_prompt_handlers(registry):\n"
                    "    def plugin_wait_handler(state, clause_text, clause_normalized, clause_index):\n"
                    "        if 'plugin' not in clause_normalized:\n"
                    "            return\n"
                    "        state.steps.append({\n"
                    "            'task_type': 'desktop_action',\n"
                    "            'title': 'Plugin wait',\n"
                    "            'payload': {'action': 'wait', 'seconds': 0.2},\n"
                    "            'continue_on_failure': True,\n"
                    "        })\n"
                    "        state.preview_actions.append({\n"
                    "            'clause_index': clause_index,\n"
                    "            'action': 'plugin_wait',\n"
                    "        })\n"
                    "    registry.register('plugin_wait', plugin_wait_handler)\n"
                ),
                encoding="utf-8",
            )

            planned = plan_prompt_task(
                prompt="plugin workflow please",
                priority=5,
                plugin_paths=[str(plugin_file)],
            )
            steps = planned["payload"]["steps"]
            self.assertTrue(steps)
            self.assertEqual(steps[0]["payload"]["action"], "wait")
            actions = planned["preview"]["actions"]
            self.assertEqual(actions[0]["action"], "plugin_wait")


if __name__ == "__main__":
    unittest.main()
