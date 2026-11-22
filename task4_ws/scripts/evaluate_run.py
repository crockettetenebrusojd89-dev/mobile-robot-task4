#!/usr/bin/env python3
"""Independent ground-truth evaluator for Task 4 run directories (T5.0)."""

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path

import yaml

from task4_bringup.association import optimal_bipartite_match
from task4_bringup.room_geometry import point_in_room


def file_sha256(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def world_to_map_rigid(wx, wy, world_ref, map_ref):
    """Map Gazebo world (x, y) into SLAM map (x, y) via a rigid reference pose pair."""
    wx0, wy0, wyaw0 = [float(v) for v in world_ref]
    mx0, my0, myaw0 = [float(v) for v in map_ref]
    theta = myaw0 - wyaw0
    c, s = math.cos(theta), math.sin(theta)
    dx, dy = float(wx) - wx0, float(wy) - wy0
    return mx0 + c * dx - s * dy, my0 + s * dx + c * dy


def verify_versions(truth_cfg, rooms_cfg, map_manifest, map_yaml_path, world_sdf_path=None):
    checks = {
        "map_yaml_matches_rooms": file_sha256(map_yaml_path) == rooms_cfg.get("map_sha256"),
        "map_yaml_matches_manifest": file_sha256(map_yaml_path)
        == map_manifest.get("files_sha256", {}).get(Path(map_yaml_path).name),
        "world_matches_truth_and_manifest": truth_cfg.get("source_sha256")
        == map_manifest.get("world", {}).get("sha256"),
    }
    if world_sdf_path is not None and Path(world_sdf_path).is_file():
        checks["world_sdf_live_sha256_matches"] = file_sha256(world_sdf_path) == truth_cfg.get("source_sha256")
    return checks


def evaluate_run(
    run_dir,
    *,
    truth_path,
    rooms_path,
    map_manifest_path,
    map_yaml_path,
    match_radius_m=0.55,
    room_margin_m=0.1,
    world_sdf_path=None,
):
    run_dir = Path(run_dir)
    task = json.loads((run_dir / "task.json").read_text(encoding="utf-8"))
    inv = json.loads((run_dir / "inventory.json").read_text(encoding="utf-8"))
    status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))

    truth_cfg = yaml.safe_load(Path(truth_path).read_text(encoding="utf-8"))
    rooms_cfg = yaml.safe_load(Path(rooms_path).read_text(encoding="utf-8"))
    map_manifest = json.loads(Path(map_manifest_path).read_text(encoding="utf-8"))

    version_checks = verify_versions(
        truth_cfg, rooms_cfg, map_manifest, map_yaml_path, world_sdf_path=world_sdf_path
    )

    world_ref = map_manifest["gazebo_default_spawn_world_xy_yaw"]
    map_ref = map_manifest["gazebo_default_spawn_map_xy_yaw_estimate"]

    room_key = task["room"]
    target_class = task["object_class"]
    room_polygon = rooms_cfg["rooms"][room_key]["boundary_polygon"]

    expected_objects = []
    for obj in truth_cfg.get("objects", []):
        if obj.get("category") != target_class:
            continue
        wx, wy, wz = obj["position_m"]
        mx, my = world_to_map_rigid(wx, wy, world_ref, map_ref)
        if point_in_room(mx, my, room_polygon, margin_m=room_margin_m):
            expected_objects.append({
                "name": obj["name"],
                "category": obj["category"],
                "world_xy": [float(wx), float(wy)],
                "map_xy": [float(mx), float(my)],
            })

    predicted_objects = list(inv.get("objects", []))

    dist_map = {}
    for pi, pred in enumerate(predicted_objects):
        for ti, exp in enumerate(expected_objects):
            d = math.hypot(float(pred["x"]) - exp["map_xy"][0], float(pred["y"]) - exp["map_xy"][1])
            if d <= match_radius_m:
                dist_map[(pi, ti)] = d

    matches = optimal_bipartite_match(len(predicted_objects), len(expected_objects), dist_map)
    matched_preds = {pi for pi, _ in matches}
    matched_truths = {ti for _, ti in matches}

    matched_details = []
    errors_m = []
    for pi, ti in matches:
        d = dist_map[(pi, ti)]
        errors_m.append(d)
        matched_details.append({
            "pred_id": predicted_objects[pi]["id"],
            "truth_name": expected_objects[ti]["name"],
            "pred_xy": [float(predicted_objects[pi]["x"]), float(predicted_objects[pi]["y"])],
            "truth_map_xy": expected_objects[ti]["map_xy"],
            "error_m": round(d, 4),
        })

    tp = len(matches)
    fp = len(predicted_objects) - tp
    fn = len(expected_objects) - tp
    expected_count = len(expected_objects)
    predicted_count = int(inv.get("count", len(predicted_objects)))

    return {
        "task_id": task.get("task_id"),
        "room": room_key,
        "object_class": target_class,
        "run_status": status.get("status"),
        "elapsed_s": status.get("elapsed_s"),
        "version_checks": version_checks,
        "all_versions_valid": all(version_checks.values()),
        "alignment": {
            "method": "rigid_2d_from_map_manifest",
            "world_ref_xy_yaw": world_ref,
            "map_ref_xy_yaw": map_ref,
            "truth_reference_point": truth_cfg.get("reference_point"),
            "note": "Predicted coordinates come from visible surface median; truth uses model_origin.",
        },
        "match_radius_m": match_radius_m,
        "expected_count": expected_count,
        "predicted_count": predicted_count,
        "count_error": predicted_count - expected_count,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "mean_position_error_m": round(sum(errors_m) / len(errors_m), 4) if errors_m else None,
        "max_position_error_m": round(max(errors_m), 4) if errors_m else None,
        "matched_pairs": matched_details,
        "unmatched_predictions": [
            predicted_objects[pi] for pi in range(len(predicted_objects)) if pi not in matched_preds
        ],
        "missed_truths": [
            expected_objects[ti] for ti in range(len(expected_objects)) if ti not in matched_truths
        ],
    }


def main():
    ws = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Run directory results/runs/<task_id>")
    parser.add_argument("--truth", type=Path, default=ws / "worlds/task4_home.truth.yaml")
    parser.add_argument("--rooms", type=Path, default=ws / "src/task4_bringup/config/rooms.yaml")
    parser.add_argument("--manifest", type=Path, default=ws / "maps/manifest.json")
    parser.add_argument("--map", type=Path, default=ws / "maps/task4_home_v1.yaml")
    parser.add_argument("--world-sdf", type=Path, default=ws / "worlds/task4_home.sdf")
    parser.add_argument("--match-radius", type=float, default=0.55)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = evaluate_run(
        args.run_dir,
        truth_path=args.truth,
        rooms_path=args.rooms,
        map_manifest_path=args.manifest,
        map_yaml_path=args.map,
        match_radius_m=args.match_radius,
        world_sdf_path=args.world_sdf,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["all_versions_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
