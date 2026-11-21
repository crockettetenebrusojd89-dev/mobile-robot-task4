#!/usr/bin/env python3
"""Check RGB-D alignment on the task4 high-contrast magenta box."""

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np


def target_component(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    if count < 2:
        raise ValueError("No target component found in the test region")
    label = 1 + int(stats[1:, cv2.CC_STAT_AREA].argmax())
    target = (labels == label).astype(np.uint8)
    if stats[label, cv2.CC_STAT_AREA] < 100:
        raise ValueError("Target needs at least 100 pixels")
    if target[0, :].any() or target[-1, :].any() or target[:, 0].any() or target[:, -1].any():
        raise ValueError("Target is cut off by the selected region or image edge")
    return target


def outline(mask):
    interior = cv2.erode(mask, np.ones((3, 3), np.uint8))
    return (mask != interior)


def edge_distance(edge):
    return cv2.distanceTransform((~edge).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)


def contour_alignment(color_edge, depth_edge):
    radius = 5
    outside = math.hypot(*color_edge.shape)
    color_distance = np.pad(edge_distance(color_edge), radius, constant_values=outside)
    depth_distance = np.pad(edge_distance(depth_edge), radius, constant_values=outside)
    color_v, color_u = np.nonzero(color_edge)
    depth_v, depth_u = np.nonzero(depth_edge)

    def distance_samples(dx, dy):
        # Measure both directions so a small fragment cannot represent a full contour.
        color_to_depth = depth_distance[color_v - dy + radius, color_u - dx + radius]
        depth_to_color = color_distance[depth_v + dy + radius, depth_u + dx + radius]
        return np.concatenate((color_to_depth, depth_to_color))

    shifts = range(-radius, radius + 1)
    offset = min(((dx, dy) for dx in shifts for dy in shifts),
                 key=lambda d: (float(distance_samples(*d).mean()), abs(d[0]) + abs(d[1])))
    return {
        "rgb_contour_pixels": int(color_edge.sum()),
        "depth_contour_pixels": int(depth_edge.sum()),
        "depth_shift_to_rgb_px": list(offset),
        "unaltered_contour_distance_median_px": float(np.median(distance_samples(0, 0))),
    }


def in_base(points, transform):
    quaternion = np.asarray(transform["quaternion_xyzw"], dtype=float)
    quaternion /= np.linalg.norm(quaternion)
    vector, real = quaternion[:3], quaternion[3]
    cross = 2 * np.cross(vector, points)
    return points + real * cross + np.cross(vector, cross) + transform["translation_m"]


def compare_laser(depth, region, target, metadata):
    info, laser = metadata["camera_info"], metadata["laser_comparison"]
    if any(value is None or abs(value) > 1e-8 for value in info["d"]):
        raise ValueError("This back-projection requires the fixture's zero-distortion camera")
    x0, y0, x1, y1 = region
    v, u = np.nonzero(cv2.erode(target, np.ones((9, 9), np.uint8)))
    z = depth[v + y0, u + x0]
    fx, fy, cx, cy = info["k"][0], info["k"][4], info["k"][2], info["k"][5]
    points = np.column_stack(((u + x0 - cx) * z / fx, (v + y0 - cy) * z / fy, z))
    camera_points = in_base(points, laser["camera_in_base"])

    ranges = np.asarray(laser["ranges_m"], dtype=float)
    angles = laser["angle_min_rad"] + np.arange(len(ranges)) * laser["angle_increment_rad"]
    valid = np.isfinite(ranges) & (ranges >= laser["range_min_m"]) & (ranges <= laser["range_max_m"])
    points = np.column_stack((ranges[valid] * np.cos(angles[valid]),
                             ranges[valid] * np.sin(angles[valid]), np.zeros(valid.sum())))
    laser_points = in_base(points, laser["laser_in_base"])
    camera_x = camera_points[np.abs(camera_points[:, 1]) <= 0.06, 0]
    laser_x = laser_points[(np.abs(laser_points[:, 1]) <= 0.06)
                           & (laser_points[:, 0] > 0), 0]
    if camera_x.size < 20 or laser_x.size < 4:
        raise ValueError("Too few front-face samples in the ±6 cm base-frame corridor")
    camera_distance, laser_distance = float(np.median(camera_x)), float(np.median(laser_x))
    return {"camera_face_x_m": camera_distance, "lidar_face_x_m": laser_distance,
            "difference_m": abs(camera_distance - laser_distance),
            "camera_point_count": int(camera_x.size), "lidar_point_count": int(laser_x.size),
            "depth_scan_stamp_delta_ns": abs(laser["camera_in_base"]["sample_stamp_ns"] -
                                             laser["laser_in_base"]["sample_stamp_ns"])}


def analyze_frame(path, region, depth_band, with_lidar):
    rgb = cv2.imread(str(path.with_suffix(".png")))
    depth = np.load(path.with_suffix(".npy"), allow_pickle=False)
    metadata = json.loads(path.read_text())
    x0, y0, x1, y1 = region
    if rgb is None or depth.ndim != 2 or rgb.shape[:2] != depth.shape:
        raise ValueError(f"Missing color image or mismatched dimensions: {path}")
    if not (0 <= x0 < x1 <= depth.shape[1] and 0 <= y0 < y1 <= depth.shape[0]):
        raise ValueError("Invalid region within the image")
    color = rgb[y0:y1, x0:x1].astype(np.int16)
    z = depth[y0:y1, x0:x1]
    magenta = (color[:, :, 2] - color[:, :, 1] > 60) & (color[:, :, 0] - color[:, :, 1] > 60)
    near = np.isfinite(z) & (z >= depth_band[0]) & (z <= depth_band[1])
    color_edge, depth_target = outline(target_component(magenta)), target_component(near)
    depth_edge = outline(depth_target)
    result = contour_alignment(color_edge, depth_edge)
    result["frame"] = path.stem
    result["rgb_depth_delta_ns"] = metadata["rgb_depth_delta_ns"]
    result["depth_camera_info_delta_ns"] = metadata["depth_camera_info_delta_ns"]
    overlay = rgb.copy()
    roi = overlay[y0:y1, x0:x1]
    roi[color_edge] = (0, 255, 0)
    roi[depth_edge] = (255, 255, 0)
    roi[color_edge & depth_edge] = (255, 255, 255)
    if with_lidar:
        result["laser_comparison"] = compare_laser(depth, region, depth_target, metadata)
    return result, overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--roi", type=int, nargs=4, required=True, metavar=("X0", "Y0", "X1", "Y1"))
    parser.add_argument("--depth-band", type=float, nargs=2, required=True, metavar=("NEAR_M", "FAR_M"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--with-lidar", action="store_true")
    args = parser.parse_args()
    if not all(math.isfinite(value) for value in args.depth_band) or not 0 < args.depth_band[0] < args.depth_band[1]:
        parser.error("--depth-band must be a finite increasing range in meters")
    paths = sorted(args.frames.glob("frame_*.json"))
    if not paths or args.out.exists() or args.out.with_suffix(".png").exists():
        parser.error("Need captured frames and a new report/overlay path")
    frames = []
    for path in paths:
        row, overlay = analyze_frame(path, args.roi, args.depth_band, args.with_lidar)
        frames.append(row)
        if len(frames) == 1 and not cv2.imwrite(str(args.out.with_suffix(".png")), overlay):
            raise OSError("Failed to write contour overlay")
    aligned = all(max(map(abs, row["depth_shift_to_rgb_px"])) <= 1
                  and row["unaltered_contour_distance_median_px"] <= 1.5 for row in frames)
    range_pass = (all(row["laser_comparison"]["difference_m"] <= 0.05 for row in frames)
                  if args.with_lidar else None)
    report = {"rgb_depth_aligned": aligned, "lidar_range_agrees": range_pass,
              "roi_xyxy": args.roi, "target_depth_band_m": args.depth_band, "frames": frames}
    with args.out.open("x") as file:
        json.dump(report, file, indent=2, allow_nan=False)
        file.write("\n")
    print(f"RGB-D aligned={aligned}, lidar agreement={range_pass}, frames={len(frames)} | {args.out}")
    return 0 if aligned and range_pass is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
