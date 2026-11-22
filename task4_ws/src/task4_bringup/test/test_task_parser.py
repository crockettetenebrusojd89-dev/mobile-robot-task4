"""Unit tests for Chinese task parsing, synonyms, longest match, and error rejection."""

from pathlib import Path
import unittest

from task4_bringup.task_parser import load_yaml_config, parse_task


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


class TaskParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rooms = load_yaml_config(CONFIG_DIR / "rooms.yaml")
        cls.objects = load_yaml_config(CONFIG_DIR / "objects.yaml")

    def test_three_rooms_and_varied_phrasings(self):
        cases = [
            ("去客厅数一下有几把椅子", "living_room", "chair"),
            ("帮我看看厨房里面有多少把凳子", "kitchen", "chair"),
            ("到卧室查一查座椅数量", "bedroom", "chair"),
            ("起居室有几张木椅", "living_room", "chair"),
        ]
        for sentence, exp_room, exp_obj in cases:
            with self.subTest(sentence=sentence):
                res = parse_task(sentence, self.rooms, self.objects, task_id="t-fixed", stamp=123.0)
                self.assertTrue(res["ok"], res)
                task = res["task"]
                self.assertEqual(task["task_id"], "t-fixed")
                self.assertEqual(task["room"], exp_room)
                self.assertEqual(task["object_class"], exp_obj)
                self.assertTrue(task["object_enabled"])

    def test_cola_and_longest_match_bottle_synonyms(self):
        res_cola = parse_task("去厨房找一下有几瓶可乐", self.rooms, self.objects)
        self.assertTrue(res_cola["ok"])
        self.assertEqual(res_cola["task"]["object_class"], "bottle")
        self.assertFalse(res_cola["task"]["object_enabled"])

        res_longest = parse_task("看看客厅有几个矿泉水瓶", self.rooms, self.objects)
        self.assertTrue(res_longest["ok"])
        self.assertEqual(res_longest["task"]["object_class"], "bottle")
        self.assertEqual(res_longest["task"]["matched_object_alias"], "矿泉水瓶")

        res_disabled = parse_task("去厨房找一下有几瓶可乐", self.rooms, self.objects, require_enabled=True)
        self.assertFalse(res_disabled["ok"])
        self.assertEqual(res_disabled["error"], "object_disabled")

    def test_missing_and_ambiguous_inputs_are_rejected(self):
        self.assertEqual(parse_task("", self.rooms, self.objects)["error"], "empty_text")
        self.assertEqual(parse_task("数一下有几把椅子", self.rooms, self.objects)["error"], "missing_room")
        self.assertEqual(parse_task("去厨房看一下", self.rooms, self.objects)["error"], "missing_object")
        self.assertEqual(
            parse_task("去客厅和厨房数椅子", self.rooms, self.objects)["error"],
            "ambiguous_room",
        )
        self.assertEqual(
            parse_task("去卧室数椅子和杯子", self.rooms, self.objects)["error"],
            "ambiguous_object",
        )


if __name__ == "__main__":
    unittest.main()
