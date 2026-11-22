"""Unit tests for search_status decision logic and SearchExecutor state machine."""

import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import numpy as np
from PIL import Image
import yaml

from task4_bringup.search_manager import SearchExecutor, flatten_viewpoints
from task4_bringup.search_status import decide_status, format_terminal_summary


class SearchStatusTests(unittest.TestCase):
    def test_four_terminal_states_and_empty_room_completion(self):
        vps_ok = [
            {"nav_succeeded": True, "valid_frames": 4, "perception_ok": True},
            {"nav_succeeded": True, "valid_frames": 3, "perception_ok": True},
        ]
        self.assertEqual(decide_status(vps_ok, True, True, False)[0], "COMPLETED")
        self.assertEqual(decide_status([], True, True, False, entrance_ok=False)[0], "FAILED")
        self.assertEqual(decide_status(vps_ok, True, False, False)[0], "FAILED")
        self.assertEqual(decide_status(vps_ok, False, True, False)[0], "INCOMPLETE")
        self.assertEqual(
            decide_status([{"nav_succeeded": False, "nav_outcome": "ABORTED"}], True, True, False)[0],
            "INCOMPLETE",
        )
        self.assertEqual(
            decide_status([{"nav_succeeded": True, "valid_frames": 1, "perception_ok": True}], True, True, False)[0],
            "INCOMPLETE",
        )
        self.assertEqual(decide_status(vps_ok, True, True, True, cancel_confirmed=True)[0], "CANCELED")
        status_unc, reason_unc = decide_status(vps_ok, True, True, True, cancel_confirmed=False)
        self.assertEqual((status_unc, reason_unc), ("INCOMPLETE", "nav_cancel_unconfirmed"))

        txt_done = format_terminal_summary(
            {"task_id": "t1", "room_display": "卧室", "object_display": "椅子"},
            {"count": 0, "objects": []},
            "COMPLETED",
            "all_viewpoints_completed",
        )
        self.assertIn("搜索完成：共 0 个", txt_done)
        txt_inc = format_terminal_summary(
            {"task_id": "t2", "room_display": "厨房", "object_display": "椅子"},
            {"count": 1, "objects": [{"id": 1, "class": "chair", "x": 1.0, "y": 2.0, "n_obs": 3}]},
            "INCOMPLETE",
            "perception_stale_or_unavailable",
        )
        self.assertIn("未完成：已确认 1 个", txt_inc)
        self.assertNotIn("搜索完成", txt_inc)


class FakeNavClient:
    def __init__(self, outcomes, *, cancel_confirmed=True):
        self._outcomes = list(outcomes)
        self._cancel_confirmed = cancel_confirmed
        self._idx = 0
        self._active = False
        self._canceled = False
        self.started_poses = []

    def start(self, x, y, yaw, timeout=90.0):
        self.started_poses.append((x, y, yaw))
        self._active = True
        self._canceled = False

    def cancel(self):
        if self._active:
            self._canceled = True
            return True
        return False

    def poll(self):
        if not self._active:
            return None
        self._active = False
        if self._canceled:
            return SimpleNamespace(
                succeeded=False,
                outcome="CANCEL_REQUESTED" if not self._cancel_confirmed else "CANCELED",
                reason="canceled",
                goal_may_be_active=not self._cancel_confirmed,
            )
        outcome = self._outcomes[self._idx] if self._idx < len(self._outcomes) else "SUCCEEDED"
        self._idx += 1
        return SimpleNamespace(
            succeeded=(outcome == "SUCCEEDED"),
            outcome=outcome,
            reason=f"mock:{outcome}",
            goal_may_be_active=False,
        )


class SearchExecutorTests(unittest.TestCase):
    def _make_env(self, tmp_path):
        pgm = tmp_path / "map.pgm"
        Image.fromarray(np.full((100, 100), 254, dtype=np.uint8), mode="L").save(pgm)
        map_yaml = tmp_path / "map.yaml"
        map_yaml.write_text(yaml.safe_dump({
            "image": "map.pgm",
            "resolution": 0.05,
            "origin": [-1.0, -1.0, 0.0],
            "negate": 0,
            "occupied_thresh": 0.65,
            "free_thresh": 0.196,
        }), encoding="utf-8")
        rooms_cfg = {
            "rooms": {
                "living_room": {
                    "display_name": "客厅",
                    "entrance_pose": [0.2, 0.2, 0.0],
                    "boundary_polygon": [[0.0, 0.0], [3.0, 0.0], [3.0, 3.0], [0.0, 3.0]],
                    "observation_points": [
                        {"x": 1.0, "y": 1.0, "yaws": [0.0, 1.57]},
                    ],
                },
                "bedroom": {
                    "display_name": "卧室",
                    "entrance_pose": [0.5, 0.5, 0.0],
                    "boundary_polygon": [[0.0, 0.0], [3.0, 0.0], [3.0, 3.0], [0.0, 3.0]],
                    "observation_points": [
                        {"x": 1.2, "y": 1.2, "yaws": [0.0]},
                    ],
                },
            }
        }
        objects_cfg = {"objects": {"chair": {"display_name": "椅子", "enabled": True}}}
        return map_yaml, rooms_cfg, objects_cfg

    def test_full_search_continues_after_first_detection_and_handles_empty_room(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            map_yaml, rooms_cfg, objects_cfg = self._make_env(tmp_path)
            stamp = [1.0]
            client = FakeNavClient(["SUCCEEDED", "SUCCEEDED", "SUCCEEDED"])

            def spin_step(_dt):
                stamp[0] += 0.1
                if executor._obs_window_active:
                    executor.on_observation({
                        "stamp": round(stamp[0], 3),
                        "frame_id": "map",
                        "valid_frame": True,
                        "detections": [{"class": "chair", "valid": True, "xyz_map": [1.5, 1.5, 0.4]}],
                    })

            executor = SearchExecutor(
                rooms_cfg=rooms_cfg,
                objects_cfg=objects_cfg,
                map_yaml_path=map_yaml,
                results_dir=tmp_path / "runs",
                nav_client_factory=lambda: client,
                spin_step=spin_step,
                clock_now_sec=lambda: stamp[0],
                params={"dwell_sec": 0.35, "settle_sec": 0.05, "min_frames_per_dwell": 3, "min_hits": 3},
            )
            res = executor.execute_task({
                "task_id": "t-live-sim",
                "room": "living_room",
                "room_display": "客厅",
                "object_class": "chair",
                "object_display": "椅子",
            })
            self.assertEqual(res["status"], "COMPLETED")
            self.assertEqual(res["count"], 1)
            # Entrance + BOTH observation yaws executed (did not stop after first detection).
            self.assertEqual(len(client.started_poses), 3)
            self.assertTrue(res["verify"]["ok"])

            # Empty bedroom completes with count=0
            def spin_empty(_dt):
                stamp[0] += 0.1
                if executor._obs_window_active:
                    executor.on_observation({
                        "stamp": round(stamp[0], 3),
                        "frame_id": "map",
                        "valid_frame": True,
                        "detections": [],
                    })

            executor.spin_step = spin_empty
            res_empty = executor.execute_task({
                "task_id": "t-empty",
                "room": "bedroom",
                "room_display": "卧室",
                "object_class": "chair",
                "object_display": "椅子",
            })
            self.assertEqual(res_empty["status"], "COMPLETED")
            self.assertEqual(res_empty["count"], 0)

    def test_cancel_timeout_blocks_future_navigation_and_saves_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            map_yaml, rooms_cfg, objects_cfg = self._make_env(tmp_path)
            stamp = [1.0]
            client = FakeNavClient(["SUCCEEDED"], cancel_confirmed=False)

            def spin_with_cancel(_dt):
                stamp[0] += 0.1
                if len(client.started_poses) == 1:
                    executor.request_cancel("t-cancel-unc")

            executor = SearchExecutor(
                rooms_cfg=rooms_cfg,
                objects_cfg=objects_cfg,
                map_yaml_path=map_yaml,
                results_dir=tmp_path / "runs",
                nav_client_factory=lambda: client,
                spin_step=spin_with_cancel,
                clock_now_sec=lambda: stamp[0],
            )
            res = executor.execute_task({
                "task_id": "t-cancel-unc",
                "room": "living_room",
                "object_class": "chair",
            })
            self.assertEqual(res["status"], "INCOMPLETE")
            self.assertEqual(res["reason"], "nav_cancel_unconfirmed")
            saved_status = json.loads((tmp_path / "runs/t-cancel-unc/status.json").read_text())
            self.assertEqual(saved_status["status"], "INCOMPLETE")

            # Subsequent task is refused while previous goal may still be active
            res_next = executor.execute_task({
                "task_id": "t-after-unc",
                "room": "living_room",
                "object_class": "chair",
            })
            self.assertEqual(res_next["status"], "FAILED")
            self.assertEqual(res_next["reason"], "previous_navigation_goal_unconfirmed")


if __name__ == "__main__":
    unittest.main()
