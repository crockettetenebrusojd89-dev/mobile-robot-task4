"""Boundary and geometry checks for 3D back-projection and rigid transforms."""

import math
import unittest

import numpy as np

from task4_bringup.geometry3d import quat_to_matrix, region_point, transform_point


class Geometry3DTests(unittest.TestCase):
    FX = 221.765
    FY = 221.765
    CX = 160.0
    CY = 120.0

    def test_center_pixel_projects_along_optical_z(self):
        depth = np.full((240, 320), 2.5, dtype=np.float32)
        result = region_point(depth, [160, 120, 161, 121], self.FX, self.FY, self.CX, self.CY)
        self.assertTrue(result["valid"])
        self.assertIsNone(result["reason"])
        self.assertEqual(result["n"], 1)
        self.assertAlmostEqual(result["valid_ratio"], 1.0)
        self.assertAlmostEqual(result["spread"], 0.0)
        self.assertAlmostEqual(result["xyz_cam"][0], 0.0, places=6)
        self.assertAlmostEqual(result["xyz_cam"][1], 0.0, places=6)
        self.assertAlmostEqual(result["xyz_cam"][2], 2.5, places=6)

    def test_off_center_pixel_matches_hand_calculation(self):
        depth = np.full((240, 320), 2.0, dtype=np.float32)
        result = region_point(depth, [200, 120, 201, 121], self.FX, self.FY, self.CX, self.CY)
        expected_x = (200.0 - self.CX) * 2.0 / self.FX
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["xyz_cam"][0], expected_x, places=6)
        self.assertAlmostEqual(result["xyz_cam"][1], 0.0, places=6)
        self.assertAlmostEqual(result["xyz_cam"][2], 2.0, places=6)

    def test_nan_inf_and_out_of_range_depths_are_filtered(self):
        depth = np.full((240, 320), 2.0, dtype=np.float32)
        # Inner 60% of [150, 110, 170, 130] is [154:166, 114:126] (12x12 = 144 pixels).
        depth[114:118, 154:166] = np.nan
        depth[118:120, 154:166] = np.inf
        depth[120:121, 154:166] = 0.05  # below z_min=0.1
        depth[121:122, 154:166] = 12.0  # above z_max=10.0

        result = region_point(depth, [150, 110, 170, 130], self.FX, self.FY, self.CX, self.CY)
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["valid_ratio"], 4.0 / 12.0, places=6)
        self.assertEqual(result["n"], 48)
        self.assertAlmostEqual(result["xyz_cam"][2], 2.0, places=6)

    def test_all_invalid_or_insufficient_depth_returns_invalid_without_origin(self):
        all_nan = np.full((240, 320), np.nan, dtype=np.float32)
        r_nan = region_point(all_nan, [140, 100, 180, 140], self.FX, self.FY, self.CX, self.CY)
        self.assertFalse(r_nan["valid"])
        self.assertIsNone(r_nan["xyz_cam"])
        self.assertEqual(r_nan["n"], 0)
        self.assertEqual(r_nan["reason"], "no_valid_depth")

        all_far = np.full((240, 320), 15.0, dtype=np.float32)
        r_far = region_point(all_far, [140, 100, 180, 140], self.FX, self.FY, self.CX, self.CY, z_max=10.0)
        self.assertFalse(r_far["valid"])
        self.assertIsNone(r_far["xyz_cam"])
        self.assertEqual(r_far["reason"], "no_valid_depth")

        sparse = np.full((240, 320), np.nan, dtype=np.float32)
        sparse[119:121, 159:161] = 2.0  # 4 pixels out of 24x24 inner region (< 0.2)
        r_sparse = region_point(sparse, [140, 100, 180, 140], self.FX, self.FY, self.CX, self.CY, min_valid_ratio=0.2)
        self.assertFalse(r_sparse["valid"])
        self.assertIsNone(r_sparse["xyz_cam"])
        self.assertEqual(r_sparse["reason"], "insufficient_valid_depth")
        self.assertLess(r_sparse["valid_ratio"], 0.2)

        r_out = region_point(np.ones((240, 320)), [350, 250, 380, 280], self.FX, self.FY, self.CX, self.CY)
        self.assertFalse(r_out["valid"])
        self.assertIsNone(r_out["xyz_cam"])
        self.assertEqual(r_out["reason"], "bbox_outside_image")

    def test_bimodal_foreground_and_background_selects_foreground(self):
        depth = np.full((240, 320), 4.5, dtype=np.float32)
        # Inner region of [140, 100, 180, 140] is [148:172, 108:132] (24x24).
        # Make 60% of the inner rows foreground at 1.80 m and 40% background at 4.50 m,
        # plus 1 row (~4%) of near outlier at 0.90 m that the 20th percentile rejects.
        depth[108:109, 148:172] = 0.90
        depth[109:123, 148:172] = 1.80

        result = region_point(depth, [140, 100, 180, 140], self.FX, self.FY, self.CX, self.CY, band=0.15)
        self.assertTrue(result["valid"])
        self.assertAlmostEqual(result["z_ref"], 1.80, places=5)
        self.assertEqual(result["n"], 14 * 24)
        self.assertAlmostEqual(result["xyz_cam"][2], 1.80, places=5)

    def test_measured_camera_quaternion_transforms_optical_axes_to_base_link(self):
        translation = [-0.037, 0.0, 0.186]
        quaternion = [-0.5, 0.5, -0.5, 0.5]

        rot = quat_to_matrix(quaternion)
        self.assertTrue(np.allclose(rot.T @ rot, np.eye(3), atol=1e-9))
        self.assertAlmostEqual(float(np.linalg.det(rot)), 1.0, places=9)

        # Optical +Z (forward) -> base_link +X; +X (right) -> -Y; +Y (down) -> -Z.
        p_forward = transform_point(translation, quaternion, [0.0, 0.0, 2.0])
        self.assertTrue(np.allclose(p_forward, [1.963, 0.0, 0.186], atol=1e-9))

        p_right = transform_point(translation, quaternion, [1.0, 0.0, 0.0])
        self.assertTrue(np.allclose(p_right, [-0.037, -1.0, 0.186], atol=1e-9))

        p_down = transform_point(translation, quaternion, [0.0, 1.0, 0.0])
        self.assertTrue(np.allclose(p_down, [-0.037, 0.0, -0.814], atol=1e-9))

        # Unnormalized quaternion produces identical rotation.
        p_scaled = transform_point(translation, [-1.0, 1.0, -1.0, 1.0], [0.0, 0.0, 2.0])
        self.assertTrue(np.allclose(p_scaled, p_forward, atol=1e-9))

    def test_invalid_parameters_raise_value_error(self):
        valid_depth = np.ones((10, 10), dtype=np.float32)
        with self.assertRaises(ValueError):
            region_point(valid_depth, [0, 0, 5, 5], 0.0, self.FY, self.CX, self.CY)
        with self.assertRaises(ValueError):
            region_point(valid_depth, [0, 0, 5, 5], self.FX, self.FY, self.CX, self.CY, z_min=2.0, z_max=1.0)
        with self.assertRaises(ValueError):
            quat_to_matrix([0.0, 0.0, 0.0, 0.0])
        with self.assertRaises(ValueError):
            transform_point([0.0, 0.0, math.nan], [0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 1.0])


if __name__ == "__main__":
    unittest.main()
