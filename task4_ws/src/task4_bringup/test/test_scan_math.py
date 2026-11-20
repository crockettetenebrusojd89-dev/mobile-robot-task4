"""Meaningful boundary and geometry checks; no ROS graph or simulated data source."""

import math
import unittest

from task4_bringup.scan_math import summarize_scan


class ScanMathTests(unittest.TestCase):
    def test_invalid_filter_limits_and_original_index(self):
        values = [math.inf, math.nan, 0.1, 0.2, 12.0, 12.1, -1.0]
        report = summarize_scan(values, -0.3, 0.1, 0.2, 12.0)
        self.assertEqual(report["sample_count"], 7)
        self.assertEqual(report["valid_count"], 2)
        self.assertEqual(report["invalid_count"], 5)
        self.assertEqual(report["nearest"]["index"], 3)
        self.assertAlmostEqual(report["nearest"]["angle_rad"], 0.0)
        self.assertAlmostEqual(report["nearest"]["x_m"], 0.2)
        self.assertAlmostEqual(report["nearest"]["y_m"], 0.0)

    def test_quarter_turn_projection_uses_radians(self):
        report = summarize_scan([3.0, 1.0], 0.0, math.pi / 2, 0.2, 12.0)
        self.assertAlmostEqual(report["nearest"]["angle_deg"], 90.0)
        self.assertAlmostEqual(report["nearest"]["x_m"], 0.0)
        self.assertAlmostEqual(report["nearest"]["y_m"], 1.0)

    def test_no_returns_does_not_invent_zero_distance(self):
        for values in ([], [math.inf, -math.inf, math.nan, 0.0, 13.0]):
            with self.subTest(values=values):
                report = summarize_scan(values, 0.0, 0.1, 0.2, 12.0)
                self.assertEqual(report["valid_count"], 0)
                self.assertIsNone(report["nearest"])

    def test_invalid_metadata_is_rejected(self):
        for metadata in ((math.nan, 0.1, 0.2, 12.0), (0.0, math.inf, 0.2, 12.0),
                         (0.0, 0.1, -0.1, 12.0), (0.0, 0.1, 2.0, 1.0),
                         (0.0, 0.0, 0.2, 12.0)):
            with self.subTest(metadata=metadata):
                with self.assertRaises(ValueError):
                    summarize_scan([1.0, 2.0], *metadata)

    def test_reverse_order_and_tie_keep_original_first_index(self):
        report = summarize_scan([2.0, 1.0, 1.0], math.pi / 2, -math.pi / 2, 0.2, 12.0)
        self.assertEqual(report["nearest"]["index"], 1)
        self.assertAlmostEqual(report["nearest"]["angle_rad"], 0.0)
        self.assertAlmostEqual(report["nearest"]["x_m"], 1.0)


if __name__ == "__main__":
    unittest.main()
