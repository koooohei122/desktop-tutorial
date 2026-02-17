from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
