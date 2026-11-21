#!/usr/bin/env python3
"""Save timestamp-matched RGB, metric depth and calibration for offline use."""

import argparse
from collections import deque
from functools import partial
import json
import math
from pathlib import Path
import time

import cv2
import numpy as np

from check_rgbd import camera_metadata, depth_in_meters, image_metadata
from check_scan_clock import stamp_ns


def color_bgr(msg):
    encoding = msg.encoding.lower()
    width, height, step = msg.width, msg.height, msg.step
    if encoding not in {"rgb8", "bgr8"}:
        raise ValueError(f"Unsupported color encoding: {msg.encoding}")
    if min(width, height) <= 0 or step < 3 * width or len(msg.data) < height * step:
        raise ValueError("Invalid color image payload or stride")
    pixels = np.ndarray((height, width, 3), dtype=np.uint8, buffer=bytes(msg.data),
                        strides=(step, 3, 1))
    return cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR) if encoding == "rgb8" else pixels


def header_stamp(msg):
    return stamp_ns(msg.header.stamp)


def remember(queue, msg):
    queue.append(msg)


def nearest(queue, stamp, tolerance_ns):
    if not queue:
        return None
    item = min(queue, key=lambda msg: abs(header_stamp(msg) - stamp))
    return item if abs(header_stamp(item) - stamp) <= tolerance_ns else None


def transform_record(buffer, msg):
    from rclpy.time import Time

    tf = buffer.lookup_transform("base_link", msg.header.frame_id, Time.from_msg(msg.header.stamp))
    t, q = tf.transform.translation, tf.transform.rotation
    return {"sample_stamp_ns": header_stamp(msg), "frame_id": msg.header.frame_id,
            "translation_m": [t.x, t.y, t.z], "quaternion_xyzw": [q.x, q.y, q.z, q.w]}


def save_frame(output, index, rgb, depth, info, laser):
    if len({msg.header.frame_id for msg in (rgb, depth, info)}) != 1 or not info.header.frame_id:
        raise ValueError("Color, depth and calibration frames must agree")
    if (rgb.width, rgb.height) != (depth.width, depth.height) or (
            rgb.width, rgb.height) != (info.width, info.height):
        raise ValueError("Color, depth and calibration dimensions must agree")
    if not all(math.isfinite(x) for x in info.k) or min(info.k[0], info.k[4]) <= 0:
        raise ValueError("Camera intrinsics are missing or invalid")
    metadata = {
        "rgb": image_metadata(rgb),
        "depth": image_metadata(depth),
        "camera_info": camera_metadata(info),
        "depth_array_unit": "m",
        "calibration_matched_by_timestamp": True,
        "rgb_depth_delta_ns": abs(header_stamp(rgb) - header_stamp(depth)),
        "depth_camera_info_delta_ns": abs(header_stamp(info) - header_stamp(depth)),
    }
    if laser is not None:
        metadata["laser_comparison"] = laser
    prefix = output / f"frame_{index:03d}"
    if not cv2.imwrite(str(prefix.with_suffix(".png")), color_bgr(rgb)):
        raise OSError(f"Failed to save {prefix.with_suffix('.png')}")
    np.save(prefix.with_suffix(".npy"), depth_in_meters(depth).astype(np.float32), allow_pickle=False)
    prefix.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")


def capture(args):
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import CameraInfo, Image, LaserScan
    from tf2_ros import Buffer, TransformException, TransformListener

    rgb, depths, infos, scans = (deque(maxlen=20) for _ in range(4))
    subscriptions = (
        (Image, "/oakd/rgb/preview/image_raw", rgb),
        (Image, "/oakd/rgb/preview/depth", depths),
        (CameraInfo, "/oakd/rgb/preview/camera_info", infos),
    )
    if args.with_lidar:
        subscriptions += ((LaserScan, "/scan", scans),)
    reason = "Waiting for image and CameraInfo stamps within 20 ms"
    saved = 0
    rclpy.init(args=[])
    node = None
    try:
        node = rclpy.create_node("task4_rgbd_capture", enable_rosout=False)
        if args.with_lidar:
            buffer = Buffer()
            listener = TransformListener(buffer, node)
        for msg_type, topic, queue in subscriptions:
            node.create_subscription(msg_type, topic, partial(remember, queue),
                                     qos_profile_sensor_data)
        deadline = time.monotonic() + args.timeout
        next_stamp = 1
        while rclpy.ok() and time.monotonic() < deadline and saved < args.count:
            rclpy.spin_once(node, timeout_sec=0.05)
            for depth in reversed(depths):
                stamp = header_stamp(depth)
                if stamp < next_stamp:
                    continue
                color = nearest(rgb, stamp, 20_000_000)
                info = nearest(infos, stamp, 20_000_000)
                if color is None or info is None:
                    continue
                laser = None
                if args.with_lidar:
                    scan = nearest(scans, stamp, 80_000_000)
                    if scan is None:
                        reason = "Waiting for a laser scan within 80 ms of the depth image"
                        continue
                    try:
                        laser = {
                            "camera_in_base": transform_record(buffer, depth),
                            "laser_in_base": transform_record(buffer, scan),
                            "angle_min_rad": scan.angle_min,
                            "angle_increment_rad": scan.angle_increment,
                            "range_min_m": scan.range_min,
                            "range_max_m": scan.range_max,
                            "ranges_m": [x if math.isfinite(x) else None for x in scan.ranges],
                        }
                    except TransformException as exc:
                        reason = str(exc)
                        continue
                save_frame(args.out, saved, color, depth, info, laser)
                saved += 1
                next_stamp = stamp + max(1, round(args.interval * 1e9))
                break
        if args.with_lidar:
            listener.unregister()
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return {"status": "CAPTURED" if saved == args.count else "NEEDS_ATTENTION",
            "saved_frames": saved, "requested_frames": args.count,
            "reason": None if saved == args.count else reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--interval", type=float, default=0.25, help="Minimum interval in ROS seconds")
    parser.add_argument("--timeout", type=float, default=18, help="Wall-clock timeout in seconds")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--with-lidar", action="store_true", help="Also record nearby scan and installation TF")
    args = parser.parse_args()
    if args.count < 1 or not math.isfinite(args.interval) or args.interval < 0:
        parser.error("--count must be positive and --interval finite and nonnegative")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    args.out.mkdir(parents=True, exist_ok=False)
    try:
        report = capture(args)
    except Exception as exc:
        report = {"status": "NEEDS_ATTENTION", "reason": str(exc),
                  "saved_frames": len(list(args.out.glob("frame_*.json")))}
    (args.out / "capture.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "CAPTURED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
