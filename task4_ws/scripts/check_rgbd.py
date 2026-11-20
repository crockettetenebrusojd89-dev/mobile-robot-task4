#!/usr/bin/env python3
"""Summarize RGB/depth/CameraInfo messages without publishing robot commands."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

import numpy as np


def image_metadata(msg):
    return {
        "width": int(msg.width), "height": int(msg.height),
        "encoding": str(msg.encoding), "step_bytes": int(msg.step),
        "frame_id": str(msg.header.frame_id),
        "stamp_sec": int(msg.header.stamp.sec),
        "stamp_nanosec": int(msg.header.stamp.nanosec),
    }


def summarize_depth(msg):
    """Interpret standard REP 118 depth encodings, respecting row padding/endian."""
    width, height, step = int(msg.width), int(msg.height), int(msg.step)
    encoding = str(msg.encoding).upper()
    if encoding not in ("32FC1", "16UC1"):
        raise ValueError(f"Unsupported depth encoding: {msg.encoding}; inspect the driver")
    dtype = np.dtype((">" if msg.is_bigendian else "<") + ("f4" if encoding == "32FC1" else "u2"))
    if width <= 0 or height <= 0 or step < width * dtype.itemsize:
        raise ValueError("Invalid image dimensions or row stride")
    payload = bytes(msg.data)
    if len(payload) < step * height:
        raise ValueError("Depth image payload is shorter than step * height")
    pixels = np.ndarray((height, width), dtype=dtype, buffer=payload, strides=(step, dtype.itemsize))
    meters = pixels.astype(np.float64)
    if encoding == "16UC1":
        meters *= 0.001
    valid_mask = np.isfinite(meters) & (meters > 0.0)
    values = meters[valid_mask]
    u, v = width // 2, height // 2
    patch = meters[max(0, v - 2):min(height, v + 3), max(0, u - 2):min(width, u + 3)]
    patch_values = patch[np.isfinite(patch) & (patch > 0.0)]
    return {
        "unit_assumption": "REP 118: 32FC1 is meters; 16UC1 is millimeters converted to meters; custom drivers require separate verification",
        "valid_pixel_count": int(values.size),
        "valid_fraction": float(values.size / meters.size),
        "min_m": float(values.min()) if values.size else None,
        "median_m": float(np.median(values)) if values.size else None,
        "max_m": float(values.max()) if values.size else None,
        "center_pixel_uv": [u, v],
        "center_patch_valid_pixel_count": int(patch_values.size),
        "center_patch_median_z_m": float(np.median(patch_values)) if patch_values.size else None,
    }


def camera_metadata(msg):
    def finite(value):
        value = float(value)
        return value if math.isfinite(value) else None

    return {
        "width": int(msg.width), "height": int(msg.height),
        "frame_id": str(msg.header.frame_id),
        "stamp_sec": int(msg.header.stamp.sec), "stamp_nanosec": int(msg.header.stamp.nanosec),
        "distortion_model": str(msg.distortion_model),
        "k": [finite(value) for value in msg.k],
        "p": [finite(value) for value in msg.p],
        "d": [finite(value) for value in msg.d],
        "binning_x": int(msg.binning_x), "binning_y": int(msg.binning_y),
        "roi": {name: int(getattr(msg.roi, name)) for name in ("x_offset", "y_offset", "width", "height")},
    }


def collect(args):
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CameraInfo, Image

    report = {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "RGB-D data reception only; no alignment, TF or object localization certification",
        "topics": {"rgb": args.rgb_topic, "depth": args.depth_topic, "camera_info": args.info_topic},
        "message_counts": {"rgb": 0, "depth": 0, "camera_info": 0},
        "rgb": None, "depth": None, "camera_info": None,
        "depth_statistics": None, "depth_decode_error": None,
        "geometry_alignment_verified": False,
    }
    node = None
    rclpy.init(args=[])
    try:
        node = rclpy.create_node("task4_rgbd_learning_check")

        def on_rgb(msg):
            report["message_counts"]["rgb"] += 1
            report["rgb"] = image_metadata(msg)

        def on_depth(msg):
            report["message_counts"]["depth"] += 1
            report["depth"] = image_metadata(msg)
            try:
                report["depth_statistics"] = summarize_depth(msg)
                report["depth_decode_error"] = None
            except (ValueError, TypeError, OverflowError) as error:
                report["depth_statistics"] = None
                report["depth_decode_error"] = str(error)

        def on_info(msg):
            report["message_counts"]["camera_info"] += 1
            report["camera_info"] = camera_metadata(msg)

        subscriptions = [
            node.create_subscription(Image, args.rgb_topic, on_rgb, qos_profile_sensor_data),
            node.create_subscription(Image, args.depth_topic, on_depth, qos_profile_sensor_data),
            node.create_subscription(CameraInfo, args.info_topic, on_info, qos_profile_sensor_data),
        ]
        started = time.monotonic()
        while rclpy.ok() and time.monotonic() - started < args.timeout:
            rclpy.spin_once(node, timeout_sec=0.2)
            counts = report["message_counts"]
            stats = report["depth_statistics"]
            if counts["rgb"] >= 3 and counts["depth"] >= 3 and counts["camera_info"] and stats and stats["valid_pixel_count"]:
                break
        report["elapsed_wall_seconds"] = round(time.monotonic() - started, 3)
        # Keep subscription references until collection has finished.
        assert len(subscriptions) == 3
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    info = report["camera_info"]
    checks = {
        "rgb_received": report["message_counts"]["rgb"] >= 3,
        "depth_received": report["message_counts"]["depth"] >= 3,
        "camera_info_received": info is not None,
        "positive_finite_depth_present": bool(report["depth_statistics"] and report["depth_statistics"]["valid_pixel_count"]),
        "calibration_focal_lengths_positive": bool(info and info["k"][0] is not None and info["k"][4] is not None and info["k"][0] > 0 and info["k"][4] > 0),
    }
    report["checks"] = checks
    report["status"] = "DATA_RECEIVED" if all(checks.values()) else "NEEDS_ATTENTION"
    report["review_notes"] = [
        "Messages are sampled independently, not synchronized; matching dimensions or frame IDs does not prove geometric alignment.",
        "The center patch reports surface Z-depth, not the distance or location of a recognized object.",
        "This check does not assess laser, odometry, TF, map frames, full M1 completion or counting.",
    ]
    if report["rgb"] and report["depth"]:
        rgb, depth = report["rgb"], report["depth"]
        report["rgb_depth_dimensions_equal"] = (rgb["width"], rgb["height"]) == (depth["width"], depth["height"])
        stamp = lambda item: item["stamp_sec"] + item["stamp_nanosec"] * 1e-9
        report["latest_sample_stamp_difference_seconds"] = abs(stamp(rgb) - stamp(depth))
    return report


def show_summary(report):
    print(f"结果：{report['status']}")
    for key, label in (("rgb", "RGB"), ("depth", "深度")):
        data = report.get(key)
        if data:
            print(f"{label}：{data['width']}×{data['height']}，{data['encoding']}，frame={data['frame_id']}")
        else:
            print(f"{label}：未收到")
    stats = report.get("depth_statistics")
    if stats:
        print(f"有效深度像素比例：{stats['valid_fraction']:.1%}")
        print(f"中心附近有效 Z 深度中位数（米）：{stats['center_patch_median_z_m']}")
    info = report.get("camera_info")
    if info:
        print(f"CameraInfo：fx={info['k'][0]}，fy={info['k'][4]}，cx={info['k'][2]}，cy={info['k'][5]}")
    if report.get("depth_decode_error"):
        print(f"深度解码问题：{report['depth_decode_error']}")
    if report.get("error"):
        print(f"运行问题：{report['error']}")
    print("此结果只检查相机数据接收；对齐、TF、地图定位和完整传感器验收仍需后续验证。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=15.0, help="Maximum collection time in wall seconds")
    parser.add_argument("--rgb-topic", default="/oakd/rgb/preview/image_raw")
    parser.add_argument("--depth-topic", default="/oakd/rgb/preview/depth")
    parser.add_argument("--info-topic", default="/oakd/rgb/preview/camera_info")
    parser.add_argument("--output", type=Path, help="Save a JSON report; an existing file at this path is replaced")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a positive finite number")
    try:
        report = collect(args)
    except Exception as error:
        report = {"status": "ENVIRONMENT_ERROR", "error": str(error), "geometry_alignment_verified": False}
    show_summary(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print(f"报告已保存：{args.output.resolve()}")
    return 0 if report["status"] == "DATA_RECEIVED" else 1


if __name__ == "__main__":
    sys.exit(main())
