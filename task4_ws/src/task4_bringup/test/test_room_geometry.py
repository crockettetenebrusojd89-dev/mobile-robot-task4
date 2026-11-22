"""Unit tests for room_geometry containment and margins."""

import math
import unittest

from task4_bringup.room_geometry import point_in_polygon, point_in_room, polygon_edge_distance


class RoomGeometryTests(unittest.TestCase):
    SQUARE = [[0.0, 0.0], [4.0, 0.0], [4.0, 3.0], [0.0, 3.0]]

    def test_inside_outside_and_boundary_points(self):
        self.assertTrue(point_in_polygon(2.0, 1.5, self.SQUARE))
        self.assertTrue(point_in_polygon(0.0, 1.5, self.SQUARE))
        self.assertTrue(point_in_polygon(4.0, 3.0, self.SQUARE))
        self.assertFalse(point_in_polygon(-0.2, 1.5, self.SQUARE))
        self.assertFalse(point_in_polygon(2.0, 3.2, self.SQUARE))

    def test_positive_and_negative_margins(self):
        self.assertAlmostEqual(polygon_edge_distance(4.05, 1.5, self.SQUARE), 0.05, places=6)
        self.assertTrue(point_in_room(4.05, 1.5, self.SQUARE, margin_m=0.1))
        self.assertFalse(point_in_room(4.15, 1.5, self.SQUARE, margin_m=0.1))
        self.assertTrue(point_in_room(1.0, 1.0, self.SQUARE, margin_m=-0.2))
        self.assertFalse(point_in_room(0.05, 1.0, self.SQUARE, margin_m=-0.2))

    def test_non_finite_coordinates_return_false(self):
        self.assertFalse(point_in_room(math.nan, 1.0, self.SQUARE))
        self.assertFalse(point_in_polygon(1.0, math.inf, self.SQUARE))


if __name__ == "__main__":
    unittest.main()
