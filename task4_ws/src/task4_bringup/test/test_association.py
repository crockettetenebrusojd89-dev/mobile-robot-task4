"""Boundary and matching tests for persistent Inventory deduplication."""

import unittest

from task4_bringup.association import Inventory


ROOM = [[0.0, 0.0], [5.0, 0.0], [5.0, 4.0], [0.0, 4.0]]


def det(x, y, z=0.4, cls="chair", valid=True):
    return {"class": cls, "valid": valid, "xyz_map": [x, y, z]}


class InventoryTests(unittest.TestCase):
    def test_empty_input_and_single_hit_not_counted(self):
        inv = Inventory("chair", ROOM, gate_m=0.5, min_hits=3)
        self.assertEqual(inv.update({"stamp": 1.0, "valid_frame": True, "detections": []}), [])
        inv.update({"stamp": 2.0, "valid_frame": True, "detections": [det(2.0, 2.0)]})
        self.assertEqual(inv.count(), 0)
        self.assertEqual(len(inv.snapshot()["tentative"]), 1)

    def test_revisit_with_noise_confirms_once_without_duplicate(self):
        inv = Inventory("chair", ROOM, gate_m=0.5, min_hits=3)
        for t, (x, y) in [(1.0, (2.00, 2.00)), (2.0, (2.10, 1.95)), (3.0, (1.92, 2.08))]:
            inv.update({"stamp": t, "valid_frame": True, "detections": [det(x, y)]})
        self.assertEqual(inv.count(), 1)
        # Revisit after gap: still matches existing ID 1
        inv.update({"stamp": 20.0, "valid_frame": True, "detections": [det(2.05, 2.02)]})
        inv.update({"stamp": 21.0, "valid_frame": True, "detections": [det(2.03, 1.98)]})
        snap = inv.snapshot()
        self.assertEqual(snap["count"], 1)
        self.assertEqual(snap["objects"][0]["id"], 1)
        self.assertEqual(snap["objects"][0]["n_obs"], 5)

    def test_two_nearby_objects_in_same_frame_do_not_merge_and_optimal_matching_beats_greedy(self):
        inv = Inventory("chair", ROOM, gate_m=0.6, min_hits=1)
        # Establish record 1 at (1.0, 1.0) and record 2 at (1.8, 1.0)
        inv.update({"stamp": 1.0, "valid_frame": True, "detections": [det(1.0, 1.0), det(1.8, 1.0)]})
        self.assertEqual(inv.count(), 2)

        # Next batch: obs0 at (1.35, 1.0) is within gate of BOTH (0.35 to r1, 0.45 to r2),
        # while obs1 at (2.25, 1.0) is ONLY within gate of r2 (0.45 to r2, 1.25 to r1).
        # Greedy would match obs0->r1 (d=0.35) leaving obs1->r2 (also works), OR if obs0 was
        # slightly closer to r2: (1.42, 1.0) -> d(r1)=0.42, d(r2)=0.38!
        # Greedy would steal r2 for obs0, stranding obs1! Optimal matching pairs obs0->r1, obs1->r2.
        inv.update({"stamp": 2.0, "valid_frame": True, "detections": [det(1.42, 1.0), det(2.25, 1.0)]})
        snap = inv.snapshot()
        self.assertEqual(snap["count"], 2)
        self.assertEqual(snap["ambiguity_count"], 1)

    def test_filters_wrong_class_invalid_depth_duplicate_stamp_and_outside_room(self):
        inv = Inventory("chair", ROOM, gate_m=0.5, min_hits=2, room_margin_m=0.1)
        inv.update({
            "stamp": 1.0,
            "valid_frame": True,
            "detections": [
                det(2.0, 2.0, cls="table"),         # wrong class
                det(2.0, 2.0, valid=False),         # invalid depth/TF
                {"class": "chair", "valid": True, "xyz_map": None},
                det(5.5, 2.0),                      # outside room (>0.1m margin)
                det(5.05, 2.0),                     # inside 0.1m margin -> accepted!
            ],
        })
        # Duplicate timestamp must be rejected and NOT confirm min_hits=2
        events_dup = inv.update({"stamp": 1.0, "valid_frame": True, "detections": [det(5.05, 2.0)]})
        self.assertEqual(events_dup[0]["reason"], "duplicate_stamp")
        self.assertEqual(inv.count(), 0)

        # Second unique timestamp confirms it
        inv.update({"stamp": 2.0, "valid_frame": True, "detections": [det(5.04, 2.0)]})
        snap = inv.snapshot()
        self.assertEqual(snap["count"], 1)
        self.assertEqual(snap["rejected_counts"]["wrong_class"], 1)
        self.assertEqual(snap["rejected_counts"]["invalid_detection"], 2)
        self.assertEqual(snap["rejected_counts"]["outside_room"], 1)
        self.assertEqual(snap["rejected_counts"]["duplicate_stamp"], 1)


if __name__ == "__main__":
    unittest.main()
