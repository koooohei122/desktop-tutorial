from __future__ import annotations

from datetime import date
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


if __name__ == "__main__":
    unittest.main()
