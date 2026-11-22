#!/usr/bin/env python3
"""Analyze multi-view localization consistency from /task4/observations JSONL files."""

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


def load_rows(paths):
    rows = []
    for path in paths:
        default_view = path.stem
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "view" not in row:
                row["view"] = default_view
            rows.append(row)
    return rows


def select_target_point(detections, target_class, focus_xy=None):
    candidates = [
        d for d in detections
        if d.get("valid") and d.get("class") == target_class and d.get("xyz_map") is not None
    ]
    if not candidates:
        return None
    if focus_xy is None or len(candidates) == 1:
        return candidates[0]["xyz_map"]
    fx, fy = focus_xy
    return min(candidates, key=lambda d: math.hypot(d["xyz_map"][0] - fx, d["xyz_map"][1] - fy))["xyz_map"]


def draw_scatter_plot(view_stats, out_png, global_median):
    width, height = 760, 620
    canvas = np.full((height, width, 3), 252, dtype=np.uint8)
    all_pts = [pt for v in view_stats.values() for pt in v["points"]]
    if not all_pts:
        cv2.imwrite(str(out_png), canvas)
        return

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    cx = 0.5 * (min(xs) + max(xs))
    cy = 0.5 * (min(ys) + max(ys))
    span = max(max(xs) - min(xs), max(ys) - min(ys), 0.6) * 1.4
    pad = 80
    plot_size = min(width - 2 * pad, height - 2 * pad)
    ox, oy = pad + 40, pad

    def to_px(x, y):
        px = int(round(ox + ((x - (cx - span / 2)) / span) * plot_size))
        py = int(round(oy + plot_size - ((y - (cy - span / 2)) / span) * plot_size))
        return px, py

    cv2.rectangle(canvas, (ox, oy), (ox + plot_size, oy + plot_size), (210, 210, 210), 1)
    palette = [(45, 130, 220), (40, 175, 75), (200, 90, 50), (160, 70, 180), (40, 160, 170)]

    gx, gy = to_px(global_median[0], global_median[1])
    cv2.drawMarker(canvas, (gx, gy), (20, 20, 20), cv2.MARKER_CROSS, 18, 2)
    cv2.putText(canvas, f"global ({global_median[0]:.3f}, {global_median[1]:.3f})",
                (gx + 10, gy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 20), 1, cv2.LINE_AA)

    for idx, (view_name, stats) in enumerate(sorted(view_stats.items())):
        color = palette[idx % len(palette)]
        for pt in stats["points"]:
            cv2.circle(canvas, to_px(pt[0], pt[1]), 4, color, -1)
        med = stats["median_xy"]
        mx, my = to_px(med[0], med[1])
        cv2.circle(canvas, (mx, my), 9, color, 2)
        legend_y = oy + 24 + idx * 24
        cv2.circle(canvas, (ox + plot_size + 25, legend_y - 4), 6, color, -1)
        cv2.putText(canvas, f"{view_name} (n={stats['valid_target_frames']})",
                    (ox + plot_size + 38, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (30, 30, 30), 1, cv2.LINE_AA)

    cv2.putText(canvas, "T3.4 Multi-View Map Localization Scatter (m)",
                (ox, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.imwrite(str(out_png), canvas)


def analyze(rows, target_class="chair", focus_xy=None, min_object_spacing_m=1.2):
    by_view = {}
    for row in rows:
        by_view.setdefault(row["view"], []).append(row)

    view_stats = {}
    medians = []
    for view_name, view_rows in sorted(by_view.items()):
        pts = []
        valid_frames = 0
        for r in view_rows:
            if r.get("valid_frame"):
                valid_frames += 1
            pt = select_target_point(r.get("detections", []), target_class, focus_xy=focus_xy)
            if pt is not None:
                pts.append([float(pt[0]), float(pt[1]), float(pt[2])])

        if pts:
            arr = np.asarray(pts, dtype=np.float64)
            med = np.median(arr[:, :2], axis=0)
            dists = np.linalg.norm(arr[:, :2] - med, axis=1)
            intra_max = float(np.max(dists))
            intra_rms = float(np.sqrt(np.mean(dists * dists)))
            med_list = [float(med[0]), float(med[1])]
            medians.append((view_name, med_list))
        else:
            intra_max = None
            intra_rms = None
            med_list = None

        view_stats[view_name] = {
            "total_frames": len(view_rows),
            "valid_frames": valid_frames,
            "valid_target_frames": len(pts),
            "target_valid_rate": float(len(pts) / len(view_rows)) if view_rows else 0.0,
            "median_xy": med_list,
            "intra_view_rms_m": intra_rms,
            "intra_view_max_m": intra_max,
            "points": pts,
        }

    if len(medians) < 3:
        raise ValueError(f"Need at least 3 views with valid target detections, got {len(medians)}")

    med_arr = np.asarray([m for _, m in medians], dtype=np.float64)
    global_med = np.median(med_arr, axis=0)
    pair_distances = []
    for i in range(len(medians)):
        for j in range(i + 1, len(medians)):
            n1, p1 = medians[i]
            n2, p2 = medians[j]
            d = float(math.hypot(p1[0] - p2[0], p1[1] - p2[1]))
            pair_distances.append({"views": [n1, n2], "distance_m": d})

    max_cross_view_diff = max(p["distance_m"] for p in pair_distances)
    max_to_global = float(np.max(np.linalg.norm(med_arr - global_med, axis=1)))
    max_intra = max(v["intra_view_max_m"] for v in view_stats.values() if v["intra_view_max_m"] is not None)

    lower_bound_m = max_cross_view_diff + max_intra
    upper_bound_m = 0.5 * min_object_spacing_m
    recommended_gate_m = round(max(0.35, min(upper_bound_m, max(lower_bound_m + 0.12, max_cross_view_diff * 1.5))), 3)

    return {
        "target_class": target_class,
        "view_count_with_detections": len(medians),
        "global_median_xy": [float(global_med[0]), float(global_med[1])],
        "max_cross_view_median_distance_m": max_cross_view_diff,
        "max_view_median_to_global_m": max_to_global,
        "max_intra_view_deviation_m": max_intra,
        "pair_distances": pair_distances,
        "gate_selection": {
            "lower_bound_m": round(lower_bound_m, 4),
            "upper_bound_m": round(upper_bound_m, 4),
            "min_scene_spacing_m": min_object_spacing_m,
            "recommended_gate_m": recommended_gate_m,
            "feasible": lower_bound_m <= upper_bound_m,
        },
        "views": {
            k: {key: val for key, val in v.items() if key != "points"}
            for k, v in view_stats.items()
        },
    }, view_stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Input JSONL file(s)")
    parser.add_argument("--target-class", default="chair")
    parser.add_argument("--focus-xy", type=float, nargs=2, default=None,
                        help="Optional approximate map (x, y) of the target chair to disambiguate multi-chair views")
    parser.add_argument("--min-spacing", type=float, default=1.2)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-plot", type=Path, required=True)
    args = parser.parse_args()

    rows = load_rows(args.inputs)
    report, view_stats = analyze(
        rows,
        target_class=args.target_class,
        focus_xy=args.focus_xy,
        min_object_spacing_m=args.min_spacing,
    )
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    draw_scatter_plot(view_stats, args.out_plot, report["global_median_xy"])
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
