"""Tests for map coordinate transforms, annotated map rendering, and result read-back."""

import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image
import yaml

from task4_bringup.map_annotate import pixel_to_world, world_to_pixel
from task4_bringup.result_io import save_run_results, verify_run_directory


class ResultAndMapTests(unittest.TestCase):
    def test_synthetic_world_and_pixel_roundtrip_zero_and_nonzero_yaw(self):
        for origin in ([-2.0, -1.0, 0.0], [-2.0, -1.0, math.pi / 4.0], [1.5, -0.5, -math.pi / 3.0]):
            with self.subTest(origin=origin):
                for x, y in ((0.0, 0.0), (1.25, 0.75), (-1.2, 1.8)):
                    u, v = world_to_pixel(x, y, 0.05, origin, 100, 80)
                    rx, ry = pixel_to_world(u, v, 0.05, origin, 100, 80)
                    self.assertAlmostEqual(rx, x, places=9)
                    self.assertAlmostEqual(ry, y, places=9)

        # At origin=[-2, -1, 0], resolution=0.05, height=80: world (-2, -1) -> bottom-left (u=0, v=80)
        u0, v0 = world_to_pixel(-2.0, -1.0, 0.05, [-2.0, -1.0, 0.0], 100, 80)
        self.assertAlmostEqual(u0, 0.0, places=9)
        self.assertAlmostEqual(v0, 80.0, places=9)

    def test_save_and_verify_readback_detects_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pgm = tmp_path / "syn.pgm"
            Image.fromarray(np.full((80, 100), 254, dtype=np.uint8), mode="L").save(pgm)
            map_yaml = tmp_path / "syn.yaml"
            map_yaml.write_text(yaml.safe_dump({
                "image": "syn.pgm",
                "resolution": 0.05,
                "origin": [-2.0, -1.0, 0.0],
                "negate": 0,
                "occupied_thresh": 0.65,
                "free_thresh": 0.196,
            }), encoding="utf-8")

            run_dir = tmp_path / "run_001"
            verification = save_run_results(
                run_dir,
                task={"task_id": "t-test", "room": "living_room", "object_class": "chair"},
                inventory_snapshot={
                    "object_class": "chair",
                    "count": 2,
                    "objects": [
                        {"id": 1, "class": "chair", "x": 0.5, "y": 1.0, "z": 0.4, "n_obs": 5, "first_stamp": 1.0, "last_stamp": 2.0},
                        {"id": 2, "class": "chair", "x": 1.5, "y": 0.2, "z": 0.4, "n_obs": 4, "first_stamp": 3.0, "last_stamp": 4.0},
                    ],
                    "tentative": [],
                },
                viewpoints=[{"pose": [0.0, 0.0, 0.0], "status": "SUCCEEDED"}],
                status_record={"status": "COMPLETED", "reason": "all_viewpoints_completed", "elapsed_s": 5.0},
                map_yaml_path=map_yaml,
                log_lines=["started", "completed count=2"],
                render_scale=2,
            )
            self.assertTrue(verification["ok"], verification)
            self.assertEqual(verification["count"], 2)

            # Tamper with inventory count -> verify_run_directory must reject
            inv = json.loads((run_dir / "inventory.json").read_text(encoding="utf-8"))
            inv["count"] = 99
            (run_dir / "inventory.json").write_text(json.dumps(inv), encoding="utf-8")
            bad = verify_run_directory(run_dir)
            self.assertFalse(bad["ok"])
            self.assertTrue(any("count_mismatch" in err for err in bad["errors"]))

    def test_real_task4_home_map_annotation_check(self):
        ws = Path(__file__).resolve().parents[3]
        map_yaml = ws / "maps" / "task4_home_v1.yaml"
        if not map_yaml.is_file():
            self.skipTest("task4_home_v1.yaml not present")
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "real_map_check"
            res = save_run_results(
                run_dir,
                task={"task_id": "t-real-map", "room": "living_room", "object_class": "chair"},
                inventory_snapshot={
                    "object_class": "chair",
                    "count": 2,
                    "objects": [
                        {"id": 1, "class": "chair", "x": 0.6896, "y": 1.1977, "z": 0.3956, "n_obs": 143, "first_stamp": 4.3, "last_stamp": 31.8},
                        {"id": 2, "class": "chair", "x": 0.1130, "y": -0.9887, "z": 0.2874, "n_obs": 45, "first_stamp": 29.8, "last_stamp": 31.8},
                    ],
                },
                viewpoints=[],
                status_record={"status": "COMPLETED"},
                map_yaml_path=map_yaml,
            )
            self.assertTrue(res["ok"], res)
            ann = json.loads((run_dir / "map_annotations.json").read_text(encoding="utf-8"))
            self.assertTrue(all(m["in_bounds"] for m in ann["markers"]))


if __name__ == "__main__":
    unittest.main()
