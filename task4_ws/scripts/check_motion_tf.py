#!/usr/bin/env python3
"""Sample a stationary pose or compare the three T1.2 pose samples. Read-only."""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from statistics import median
import time

from check_scan_clock import stamp_ns


def xyz(value):
    return [value.x, value.y, value.z]


def xyzw(value):
    return [value.x, value.y, value.z, value.w]


def yaw(quaternion):
    x, y, z, w = quaternion
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def angle_change(start, finish):
    return math.remainder(finish - start, math.tau)


def rotation_difference(first, second):
    cosine = abs(sum(a * b for a, b in zip(first, second)))
    return math.degrees(2 * math.acos(min(1, cosine)))


def front_wall(scan, lidar_in_base):
    """Measure forward distance using returns within ±10° in the base frame."""
    lidar_yaw = yaw(lidar_in_base["quaternion_xyzw"])
    offset_x, offset_y, _ = lidar_in_base["translation_m"]
    forward_distances = []
    for index, distance in enumerate(scan.ranges):
        if not math.isfinite(distance) or not scan.range_min <= distance <= scan.range_max:
            continue
        angle = scan.angle_min + index * scan.angle_increment + lidar_yaw
        x = offset_x + distance * math.cos(angle)
        y = offset_y + distance * math.sin(angle)
        if abs(math.atan2(y, x)) <= math.radians(10):
            forward_distances.append(x)
    return {
        "ray_count": len(forward_distances),
        "median_base_x_m": median(forward_distances) if forward_distances else None,
    }


def write_json(path, data):
    with path.open("x") as file:
        json.dump(data, file, indent=2, allow_nan=False)
        file.write("\n")


def sample(timeout, scan_frame, camera_frame):
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.parameter import Parameter
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.time import Time
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import LaserScan
    from task4_bringup.scan_math import summarize_scan
    from tf2_ros import Buffer, TransformException, TransformListener

    scans, odoms = deque(maxlen=200), deque(maxlen=200)
    clock = None

    def clock_callback(message):
        nonlocal clock
        clock = stamp_ns(message.clock)

    def lookup(target, source, stamp):
        result = buffer.lookup_transform(target, source, Time.from_msg(stamp))
        return {
            "target": result.header.frame_id,
            "source": result.child_frame_id,
            "stamp_ns": stamp_ns(result.header.stamp),
            "translation_m": xyz(result.transform.translation),
            "quaternion_xyzw": xyzw(result.transform.rotation),
        }

    rclpy.init(args=[])
    node = None
    last_error = "Waiting for stamped /scan, /odom and /clock"
    try:
        node = rclpy.create_node(
            "task4_motion_snapshot", enable_rosout=False,
            parameter_overrides=[Parameter("use_sim_time", value=True)],
        )
        buffer = Buffer()
        listener = TransformListener(buffer, node)
        node.create_subscription(LaserScan, "/scan", lambda msg: scans.append(msg), qos_profile_sensor_data)
        node.create_subscription(Odometry, "/odom", lambda msg: odoms.append(msg), qos_profile_sensor_data)
        node.create_subscription(Clock, "/clock", clock_callback, qos_profile_sensor_data)
        deadline = time.monotonic() + timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            if clock is None or not scans or not odoms:
                continue
            # Keep processing TF callbacks while choosing a recent scan with time to arrive.
            scan = next((msg for msg in reversed(scans)
                         if 100_000_000 <= clock - stamp_ns(msg.header.stamp) <= 500_000_000), None)
            if scan is None:
                last_error = "No recent scan in the simulation clock window"
                continue
            if scan.header.frame_id != scan_frame:
                last_error = f"Unexpected LaserScan frame: {scan.header.frame_id}"
                continue
            scan_stamp = stamp_ns(scan.header.stamp)
            odom = min(odoms, key=lambda msg: abs(stamp_ns(msg.header.stamp) - scan_stamp))
            odom_stamp = stamp_ns(odom.header.stamp)
            if abs(odom_stamp - scan_stamp) > 100_000_000:
                last_error = "No odometry within 100 ms of the scan"
                continue
            if (odom.header.frame_id, odom.child_frame_id) != ("odom", "base_link"):
                last_error = f"Unexpected odometry frames: {odom.header.frame_id}, {odom.child_frame_id}"
                continue
            try:
                odom_to_base = lookup("odom", "base_link", odom.header.stamp)
                base_to_scan = lookup("base_link", scan_frame, scan.header.stamp)
                base_to_camera = lookup("base_link", camera_frame, scan.header.stamp)
                odom_to_scan = lookup("odom", scan_frame, scan.header.stamp)
            except TransformException as exc:
                last_error = str(exc)
                continue
            lidar = summarize_scan(
                scan.ranges, scan.angle_min, scan.angle_increment, scan.range_min, scan.range_max,
            )
            lidar["front_in_base"] = front_wall(scan, base_to_scan)
            listener.unregister()
            return {
                "status": "SAMPLED",
                "clock_ns": clock,
                "scan": {"stamp_ns": scan_stamp, "frame_id": scan_frame, **lidar},
                "odom": {
                    "stamp_ns": odom_stamp,
                    "frame_id": odom.header.frame_id,
                    "child_frame_id": odom.child_frame_id,
                    "translation_m": xyz(odom.pose.pose.position),
                    "quaternion_xyzw": xyzw(odom.pose.pose.orientation),
                    "linear_m_s": xyz(odom.twist.twist.linear),
                    "angular_rad_s": xyz(odom.twist.twist.angular),
                },
                "tf": {
                    "odom_to_base_at_odom": odom_to_base,
                    "base_to_scan_at_scan": base_to_scan,
                    "base_to_camera_at_scan": base_to_camera,
                    "odom_to_scan_at_scan": odom_to_scan,
                },
            }
        listener.unregister()
        return {"status": "NEEDS_ATTENTION", "reason": last_error}
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def compare(directory):
    snapshots = [json.loads((directory / f"{label}.json").read_text())
                 for label in ("before", "after", "rotated")]
    if any(item["status"] != "SAMPLED" for item in snapshots):
        return {"status": "NEEDS_ATTENTION", "reason": "One or more pose samples failed"}
    before, after, rotated = snapshots
    odom_start, odom_end = before["odom"], after["odom"]
    heading = yaw(odom_start["quaternion_xyzw"])
    dx = odom_end["translation_m"][0] - odom_start["translation_m"][0]
    dy = odom_end["translation_m"][1] - odom_start["translation_m"][1]
    forward = dx * math.cos(heading) + dy * math.sin(heading)
    lateral = -dx * math.sin(heading) + dy * math.cos(heading)
    turn = math.degrees(angle_change(
        yaw(odom_end["quaternion_xyzw"]), yaw(rotated["odom"]["quaternion_xyzw"]),
    ))
    turn_translation = math.dist(odom_end["translation_m"], rotated["odom"]["translation_m"])
    wall_before = before["scan"]["front_in_base"]["median_base_x_m"]
    wall_after = after["scan"]["front_in_base"]["median_base_x_m"]
    wall_delta = wall_before - wall_after if wall_before is not None and wall_after is not None else None

    def deviations(left, right):
        return {
            "translation_m": math.dist(left["translation_m"], right["translation_m"]),
            "rotation_deg": rotation_difference(left["quaternion_xyzw"], right["quaternion_xyzw"]),
        }

    odom_errors = [deviations(item["odom"], item["tf"]["odom_to_base_at_odom"])
                   for item in snapshots]
    installation_changes = {
        key: [deviations(before["tf"][key], item["tf"][key]) for item in (after, rotated)]
        for key in ("base_to_scan_at_scan", "base_to_camera_at_scan")
    }
    checks = {
        "forward_0_10_to_0_30_m": 0.1 <= forward <= 0.3,
        "forward_lateral_error_under_0_05_m": abs(lateral) < 0.05,
        "left_turn_60_to_120_deg": 60 <= turn <= 120,
        "turn_translation_under_0_05_m": turn_translation < 0.05,
        "front_wall_distance_decreased": wall_delta is not None and wall_delta > 0.02,
        "dynamic_tf_agrees_with_odom": all(item["translation_m"] < 0.01 and item["rotation_deg"] < 1
                                            for item in odom_errors),
        "installation_tf_stable": all(item["translation_m"] < 0.001 and item["rotation_deg"] < 0.1
                                      for changes in installation_changes.values() for item in changes),
        "odom_to_scan_queried_at_scan_time": all("odom_to_scan_at_scan" in item["tf"] for item in snapshots),
        "all_poses_stopped": all(math.hypot(*item["odom"]["linear_m_s"]) < 0.02
                                 and math.hypot(*item["odom"]["angular_rad_s"]) < 0.05
                                 for item in snapshots),
        "simulation_time_advances": all(
            current["clock_ns"] > previous["clock_ns"]
            and current["odom"]["stamp_ns"] > previous["odom"]["stamp_ns"]
            and current["scan"]["stamp_ns"] > previous["scan"]["stamp_ns"]
            for previous, current in zip(snapshots, snapshots[1:])
        ),
    }
    return {
        "status": "T1.2_PASSED" if all(checks.values()) else "NEEDS_ATTENTION",
        "checks": checks,
        "forward_m": forward,
        "lateral_m": lateral,
        "left_turn_deg": turn,
        "turn_translation_m": turn_translation,
        "wall_before_m": wall_before,
        "wall_after_m": wall_after,
        "wall_decrease_m": wall_delta,
        "odom_tf_errors": odom_errors,
        "installation_tf_changes": installation_changes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", choices=("before", "after", "rotated"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--compare", type=Path, metavar="RUN_DIR")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--scan-frame", default="turtlebot4/rplidar_link/rplidar")
    parser.add_argument("--camera-frame", default="oakd_rgb_camera_optical_frame")
    args = parser.parse_args()
    if (args.label is None) == (args.compare is None):
        parser.error("provide either --label or --compare")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error("--output must be a new file in an existing directory")
    report = (compare(args.compare) if args.compare else
              sample(args.timeout, args.scan_frame, args.camera_frame))
    report["recorded_at_utc"] = datetime.now(timezone.utc).isoformat()
    if args.label:
        report["label"] = args.label
    write_json(args.output, report)
    print(f"{report['status']} | {args.output}")
    if "reason" in report:
        print(report["reason"])
    return 0 if report["status"] in ("SAMPLED", "T1.2_PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
