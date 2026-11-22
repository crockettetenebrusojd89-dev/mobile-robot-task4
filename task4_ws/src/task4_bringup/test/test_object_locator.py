"""Unit and real-frame replay tests for object_locator core and decoding."""

import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import cv2
import numpy as np

from task4_bringup.detector import HsvChairDetector, create_detector
from task4_bringup.object_locator import (
    LocatorConfig,
    ObjectLocatorCore,
    decode_color_bgr,
    decode_depth_meters,
    draw_debug_overlay,
    parse_camera_info,
)


def make_stamp(sec, nanosec):
    return SimpleNamespace(sec=sec, nanosec=nanosec)


def make_image(array, encoding, frame_id="oakd_rgb_camera_optical_frame", sec=12, nanosec=345000000,
               step_padding=0, is_bigendian=0):
    height, width = array.shape[:2]
    row_bytes = width * array.shape[2] * array.itemsize if array.ndim == 3 else width * array.itemsize
    step = row_bytes + step_padding
    if step_padding:
        raw = np.zeros((height, step), dtype=np.uint8)
        raw[:, :row_bytes] = np.frombuffer(array.tobytes(), dtype=np.uint8).reshape(height, row_bytes)
        data = raw.tobytes()
    else:
        data = array.tobytes()
    return SimpleNamespace(
        header=SimpleNamespace(stamp=make_stamp(sec, nanosec), frame_id=frame_id),
        width=width,
        height=height,
        encoding=encoding,
        is_bigendian=is_bigendian,
        step=step,
        data=data,
    )


def make_camera_info(width=320, height=240, frame_id="oakd_rgb_camera_optical_frame",
                     fx=221.765, fy=221.765, cx=160.0, cy=120.0):
    msg = SimpleNamespace(
        header=SimpleNamespace(stamp=make_stamp(0, 0), frame_id=frame_id),
        width=width,
        height=height,
        k=[fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0],
    )
    return parse_camera_info(msg)


class StubDetector:
    def __init__(self, detections):
        self._detections = detections

    def predict(self, image_bgr):
        return list(self._detections)


class ObjectLocatorCoreTests(unittest.TestCase):
    def test_decode_color_and_depth_encodings_with_stride_and_endianness(self):
        rgb = np.zeros((4, 6, 3), dtype=np.uint8)
        rgb[:, :, 0] = 200  # R
        rgb[:, :, 2] = 10   # B
        rgb_msg = make_image(rgb, "rgb8", step_padding=5)
        bgr = decode_color_bgr(rgb_msg)
        self.assertEqual(bgr.shape, (4, 6, 3))
        self.assertEqual(int(bgr[0, 0, 2]), 200)
        self.assertEqual(int(bgr[0, 0, 0]), 10)

        depth_mm = np.full((4, 6), 2500, dtype=">u2")
        depth_msg = make_image(depth_mm, "16UC1", step_padding=4, is_bigendian=1)
        meters = decode_depth_meters(depth_msg)
        self.assertTrue(np.allclose(meters, 2.5))

    def test_preserves_acquisition_stamp_and_transforms_to_map(self):
        rgb_msg = make_image(np.zeros((240, 320, 3), dtype=np.uint8), "bgr8", sec=42, nanosec=500000000)
        depth_msg = make_image(np.full((240, 320), 2.0, dtype=np.float32), "32FC1", sec=42, nanosec=500000000)
        cam_info = make_camera_info()

        observed_stamps = []

        def tf_lookup(target, source, stamp):
            observed_stamps.append((target, source, stamp.sec, stamp.nanosec))
            return [-0.037, 0.0, 0.186], [-0.5, 0.5, -0.5, 0.5]

        detector = StubDetector([{"class": "chair", "conf": 0.9, "bbox": [155, 115, 165, 125]}])
        core = ObjectLocatorCore(detector, tf_lookup, LocatorConfig(map_frame="base_link"))
        obs, debug_bgr = core.process_frame(rgb_msg, depth_msg, cam_info)

        self.assertTrue(obs["valid_frame"])
        self.assertIsNone(obs["reason"])
        self.assertAlmostEqual(obs["stamp"], 42.5, places=9)
        self.assertEqual(obs["frame_id"], "base_link")
        self.assertEqual(observed_stamps, [("base_link", "oakd_rgb_camera_optical_frame", 42, 500000000)])
        self.assertEqual(len(obs["detections"]), 1)
        det = obs["detections"][0]
        self.assertTrue(det["valid"])
        self.assertAlmostEqual(det["xyz_cam"][2], 2.0, places=4)
        self.assertAlmostEqual(det["xyz_map"][0], 1.963, places=3)
        self.assertIsNotNone(debug_bgr)

    def test_valid_empty_frame_vs_all_invalid_depth_frame(self):
        rgb_msg = make_image(np.zeros((240, 320, 3), dtype=np.uint8), "bgr8", sec=10, nanosec=0)
        cam_info = make_camera_info()
        tf_lookup = lambda t, s, stamp: ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])
        core = ObjectLocatorCore(StubDetector([]), tf_lookup, LocatorConfig(map_frame="odom"))

        good_depth = make_image(np.full((240, 320), 3.0, dtype=np.float32), "32FC1", sec=10, nanosec=0)
        obs_empty, _ = core.process_frame(rgb_msg, good_depth, cam_info)
        self.assertTrue(obs_empty["valid_frame"])
        self.assertEqual(obs_empty["detections"], [])

        nan_depth = make_image(np.full((240, 320), np.nan, dtype=np.float32), "32FC1", sec=10, nanosec=0)
        obs_bad, _ = core.process_frame(rgb_msg, nan_depth, cam_info)
        self.assertFalse(obs_bad["valid_frame"])
        self.assertEqual(obs_bad["reason"], "no_valid_depth_in_frame")

    def test_missing_tf_marks_frame_and_candidates_invalid_with_reason(self):
        rgb_msg = make_image(np.zeros((240, 320, 3), dtype=np.uint8), "bgr8")
        depth_msg = make_image(np.full((240, 320), 2.0, dtype=np.float32), "32FC1")
        cam_info = make_camera_info()

        def failing_tf(target, source, stamp):
            raise RuntimeError("extrapolation into future")

        detector = StubDetector([{"class": "chair", "conf": None, "bbox": [140, 100, 180, 140]}])
        core = ObjectLocatorCore(detector, failing_tf, LocatorConfig(map_frame="map"))
        obs, _ = core.process_frame(rgb_msg, depth_msg, cam_info)

        self.assertFalse(obs["valid_frame"])
        self.assertIn("tf_lookup_failed", obs["reason"])
        self.assertEqual(len(obs["detections"]), 1)
        det = obs["detections"][0]
        self.assertFalse(det["valid"])
        self.assertIsNone(det["xyz_map"])
        self.assertIsNotNone(det["xyz_cam"])
        self.assertIn("tf_lookup_failed", det["reason"])

    def test_partial_invalid_candidate_depth_keeps_other_valid_candidates(self):
        rgb_msg = make_image(np.zeros((240, 320, 3), dtype=np.uint8), "bgr8")
        depth = np.full((240, 320), 2.0, dtype=np.float32)
        depth[20:60, 20:60] = np.nan
        depth_msg = make_image(depth, "32FC1")
        cam_info = make_camera_info()
        tf_lookup = lambda t, s, stamp: ([0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0])

        detector = StubDetector([
            {"class": "chair", "conf": None, "bbox": [20, 20, 60, 60]},
            {"class": "chair", "conf": None, "bbox": [140, 100, 180, 140]},
        ])
        core = ObjectLocatorCore(detector, tf_lookup, LocatorConfig(map_frame="map"))
        obs, _ = core.process_frame(rgb_msg, depth_msg, cam_info)

        self.assertTrue(obs["valid_frame"])
        self.assertFalse(obs["detections"][0]["valid"])
        self.assertIsNone(obs["detections"][0]["xyz_map"])
        self.assertEqual(obs["detections"][0]["reason"], "no_valid_depth")
        self.assertTrue(obs["detections"][1]["valid"])
        self.assertIsNotNone(obs["detections"][1]["xyz_map"])

    def test_replay_real_t3_1_holdout_frame_with_hsv_detector(self):
        holdout_frames = (
            Path(__file__).resolve().parents[3]
            / "results"
            / "m3_detection"
            / "2026-11-22_t3_1_holdout"
            / "frames"
        )
        if not holdout_frames.is_dir():
            self.skipTest("T3.1 holdout frames directory not present")

        bgr = cv2.imdecode(np.frombuffer((holdout_frames / "frame_000.png").read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
        depth = np.load(holdout_frames / "frame_000.npy", allow_pickle=False)
        meta = json.loads((holdout_frames / "frame_000.json").read_text(encoding="utf-8"))

        rgb_msg = make_image(
            bgr,
            "bgr8",
            frame_id=meta["rgb"]["frame_id"],
            sec=meta["rgb"]["stamp_sec"],
            nanosec=meta["rgb"]["stamp_nanosec"],
        )
        depth_msg = make_image(
            depth.astype(np.float32),
            "32FC1",
            frame_id=meta["depth"]["frame_id"],
            sec=meta["depth"]["stamp_sec"],
            nanosec=meta["depth"]["stamp_nanosec"],
        )
        k = meta["camera_info"]["k"]
        cam_info = make_camera_info(
            width=meta["camera_info"]["width"],
            height=meta["camera_info"]["height"],
            frame_id=meta["camera_info"]["frame_id"],
            fx=k[0],
            fy=k[4],
            cx=k[2],
            cy=k[5],
        )

        detector = create_detector("hsv", classes=("chair",))
        self.assertIsInstance(detector, HsvChairDetector)
        core = ObjectLocatorCore(
            detector,
            lambda t, s, stamp: ([-0.037, 0.0, 0.186], [-0.5, 0.5, -0.5, 0.5]),
            LocatorConfig(map_frame="base_link"),
        )
        obs, debug_bgr = core.process_frame(rgb_msg, depth_msg, cam_info)
        self.assertTrue(obs["valid_frame"])
        self.assertEqual(len(obs["detections"]), 1)
        self.assertTrue(obs["detections"][0]["valid"])
        self.assertAlmostEqual(obs["detections"][0]["xyz_map"][0], 0.8229, places=3)
        overlay = draw_debug_overlay(debug_bgr, obs["detections"])
        self.assertEqual(overlay.shape, bgr.shape)


if __name__ == "__main__":
    unittest.main()
