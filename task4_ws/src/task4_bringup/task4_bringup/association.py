"""Persistent per-task object association and confirmed counting; no ROS dependency."""

import math
from statistics import median

from task4_bringup.room_geometry import point_in_room


def _solve_component_matching(obs_indices, rec_indices, dist_map):
    """Find maximum-cardinality, minimum-total-distance 1-to-1 matching on a component."""
    best_count = 0
    best_cost = 0.0
    best_pairs = []

    rec_used = set()
    current_pairs = []

    # Order observations by fewest candidate edges first to prune search quickly.
    adj = {
        oi: sorted(
            [(dist_map[(oi, ri)], ri) for ri in rec_indices if (oi, ri) in dist_map],
            key=lambda item: item[0],
        )
        for oi in obs_indices
    }
    ordered_obs = sorted(obs_indices, key=lambda oi: len(adj[oi]))

    def dfs(pos, count, cost):
        nonlocal best_count, best_cost, best_pairs
        remaining = len(ordered_obs) - pos
        if count + remaining < best_count:
            return
        if pos == len(ordered_obs):
            if count > best_count or (count == best_count and cost < best_cost - 1e-12):
                best_count = count
                best_cost = cost
                best_pairs = list(current_pairs)
            return

        oi = ordered_obs[pos]
        for d, ri in adj[oi]:
            if ri in rec_used:
                continue
            rec_used.add(ri)
            current_pairs.append((oi, ri))
            dfs(pos + 1, count + 1, cost + d)
            current_pairs.pop()
            rec_used.remove(ri)

        # Also explore leaving observation oi unmatched so another observation can take its partner.
        dfs(pos + 1, count, cost)

    dfs(0, 0, 0.0)
    return best_pairs


def optimal_bipartite_match(n_obs, n_rec, dist_map):
    """Decompose gated edges into connected components and solve optimal 1-to-1 matching."""
    if not dist_map:
        return []
    obs_adj = {i: [] for i in range(n_obs)}
    rec_adj = {j: [] for j in range(n_rec)}
    for oi, ri in dist_map:
        obs_adj[oi].append(ri)
        rec_adj[ri].append(oi)

    visited_obs = set()
    visited_rec = set()
    matches = []

    for start_obs in range(n_obs):
        if start_obs in visited_obs or not obs_adj[start_obs]:
            continue
        comp_obs = []
        comp_rec = []
        queue = [("obs", start_obs)]
        visited_obs.add(start_obs)
        while queue:
            kind, idx = queue.pop()
            if kind == "obs":
                comp_obs.append(idx)
                for ri in obs_adj[idx]:
                    if ri not in visited_rec:
                        visited_rec.add(ri)
                        queue.append(("rec", ri))
            else:
                comp_rec.append(idx)
                for oi in rec_adj[idx]:
                    if oi not in visited_obs:
                        visited_obs.add(oi)
                        queue.append(("obs", oi))
        matches.extend(_solve_component_matching(comp_obs, comp_rec, dist_map))

    return sorted(matches, key=lambda pair: pair[0])


class _TrackedRecord:
    def __init__(self, object_class, xyz, stamp):
        self.id = None
        self.object_class = object_class
        self.samples = [list(xyz)]
        self.stamps = [float(stamp)]
        self.first_stamp = float(stamp)
        self.last_stamp = float(stamp)
        self.confirmed = False

    def add_observation(self, xyz, stamp):
        self.samples.append(list(xyz))
        self.stamps.append(float(stamp))
        self.last_stamp = max(self.last_stamp, float(stamp))
        self.first_stamp = min(self.first_stamp, float(stamp))

    def position(self):
        return [
            float(median(s[0] for s in self.samples)),
            float(median(s[1] for s in self.samples)),
            float(median(s[2] for s in self.samples)),
        ]

    def to_dict(self):
        x, y, z = self.position()
        return {
            "id": self.id,
            "class": self.object_class,
            "x": x,
            "y": y,
            "z": z,
            "n_obs": len(self.samples),
            "first_stamp": self.first_stamp,
            "last_stamp": self.last_stamp,
        }


class Inventory:
    """Room-scoped persistent object tracker and deduplicated counter."""

    def __init__(self, object_class, room_polygon, gate_m, min_hits=3, room_margin_m=0.1):
        if not str(object_class).strip():
            raise ValueError("object_class must be non-empty")
        if not (math.isfinite(gate_m) and gate_m > 0.0):
            raise ValueError("gate_m must be finite and > 0")
        if int(min_hits) < 1:
            raise ValueError("min_hits must be >= 1")
        if len(room_polygon) < 3:
            raise ValueError("room_polygon must have at least 3 vertices")

        self.object_class = str(object_class)
        self.room_polygon = [list(p) for p in room_polygon]
        self.gate_m = float(gate_m)
        self.min_hits = int(min_hits)
        self.room_margin_m = float(room_margin_m)

        self._records = []
        self._next_id = 1
        self._seen_stamps = set()
        self.ambiguity_count = 0
        self.rejected_counts = {
            "invalid_frame": 0,
            "duplicate_stamp": 0,
            "wrong_class": 0,
            "invalid_detection": 0,
            "outside_room": 0,
        }

    def update(self, batch, stamp=None):
        """Process one observation frame (dict or list of detection dicts) and return events."""
        if isinstance(batch, dict):
            frame_stamp = batch.get("stamp") if stamp is None else stamp
            if not batch.get("valid_frame", True):
                self.rejected_counts["invalid_frame"] += 1
                return [{"type": "frame_rejected", "reason": "invalid_frame", "stamp": frame_stamp}]
            detections = batch.get("detections", [])
        else:
            frame_stamp = stamp
            detections = batch

        if frame_stamp is None or not math.isfinite(float(frame_stamp)):
            raise ValueError("Observation batch requires a finite timestamp")
        frame_stamp = round(float(frame_stamp), 9)

        if frame_stamp in self._seen_stamps:
            self.rejected_counts["duplicate_stamp"] += 1
            return [{"type": "frame_rejected", "reason": "duplicate_stamp", "stamp": frame_stamp}]
        self._seen_stamps.add(frame_stamp)

        valid_obs = []
        events = []
        for det in detections:
            if det.get("class") != self.object_class:
                self.rejected_counts["wrong_class"] += 1
                continue
            xyz = det.get("xyz_map")
            if (
                not det.get("valid")
                or xyz is None
                or len(xyz) != 3
                or not all(math.isfinite(float(v)) for v in xyz)
            ):
                self.rejected_counts["invalid_detection"] += 1
                continue
            x, y, z = float(xyz[0]), float(xyz[1]), float(xyz[2])
            if not point_in_room(x, y, self.room_polygon, margin_m=self.room_margin_m):
                self.rejected_counts["outside_room"] += 1
                events.append({"type": "outside_room", "xyz_map": [x, y, z], "stamp": frame_stamp})
                continue
            valid_obs.append([x, y, z])

        if not valid_obs:
            return events

        dist_map = {}
        for oi, obs_xyz in enumerate(valid_obs):
            dists_within_gate = []
            for ri, rec in enumerate(self._records):
                rx, ry, _ = rec.position()
                d = math.hypot(obs_xyz[0] - rx, obs_xyz[1] - ry)
                if d <= self.gate_m:
                    dist_map[(oi, ri)] = d
                    dists_within_gate.append(d)
            if len(dists_within_gate) >= 2:
                dists_within_gate.sort()
                if dists_within_gate[1] - dists_within_gate[0] < 0.1:
                    self.ambiguity_count += 1
                    events.append({"type": "ambiguity", "obs_index": oi, "stamp": frame_stamp})

        matched_pairs = optimal_bipartite_match(len(valid_obs), len(self._records), dist_map)
        matched_obs = {oi for oi, _ in matched_pairs}

        for oi, ri in matched_pairs:
            rec = self._records[ri]
            rec.add_observation(valid_obs[oi], frame_stamp)
            events.append({"type": "matched", "record_index": ri, "id": rec.id, "stamp": frame_stamp})
            if not rec.confirmed and len(rec.samples) >= self.min_hits:
                rec.confirmed = True
                rec.id = self._next_id
                self._next_id += 1
                events.append({"type": "confirmed", "id": rec.id, "stamp": frame_stamp})

        for oi, obs_xyz in enumerate(valid_obs):
            if oi in matched_obs:
                continue
            rec = _TrackedRecord(self.object_class, obs_xyz, frame_stamp)
            if self.min_hits <= 1:
                rec.confirmed = True
                rec.id = self._next_id
                self._next_id += 1
                events.append({"type": "confirmed", "id": rec.id, "stamp": frame_stamp})
            else:
                events.append({"type": "tentative_created", "stamp": frame_stamp})
            self._records.append(rec)

        return events

    def count(self):
        return sum(1 for rec in self._records if rec.confirmed)

    def snapshot(self):
        confirmed = [rec.to_dict() for rec in self._records if rec.confirmed]
        confirmed.sort(key=lambda item: item["id"])
        tentative = [rec.to_dict() for rec in self._records if not rec.confirmed]
        return {
            "object_class": self.object_class,
            "gate_m": self.gate_m,
            "min_hits": self.min_hits,
            "count": len(confirmed),
            "objects": confirmed,
            "tentative": tentative,
            "ambiguity_count": self.ambiguity_count,
            "rejected_counts": dict(self.rejected_counts),
        }
