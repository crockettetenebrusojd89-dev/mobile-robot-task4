#!/usr/bin/env python3
"""Read /scan, /clock and the scan frame's installation TF in one bounded window."""

import argparse
from bisect import bisect_left
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time


def stamp_ns(stamp):
    return stamp.sec * 1_000_000_000 + stamp.nanosec


def pair_samples(scans, clocks):
    if not clocks:
        return []
    receipt_times = [clock["received_ns"] for clock in clocks]
    pairs = []
    for scan in scans:
        index = bisect_left(receipt_times, scan["received_ns"])
        candidates = range(max(0, index - 1), min(len(clocks), index + 1))
        nearest = min(candidates, key=lambda i: abs(receipt_times[i] - scan["received_ns"]))
        clock = clocks[nearest]
        pairs.append({
            "scan": scan,
            "clock": clock,
            "receipt_delta_ns": scan["received_ns"] - clock["received_ns"],
            "stamp_delta_ns": scan["stamp_ns"] - clock["stamp_ns"],
        })
    return pairs


def describe_stream(samples):
    stamps = [sample["stamp_ns"] for sample in samples]
    return {
        "count": len(samples),
        "first_stamp_ns": stamps[0] if stamps else None,
        "last_stamp_ns": stamps[-1] if stamps else None,
        "advancing": bool(stamps) and stamps[-1] > stamps[0]
        and all(a <= b for a, b in zip(stamps, stamps[1:])),
        "receipt_hz": ((len(samples) - 1) * 1e9 /
                       (samples[-1]["received_ns"] - samples[0]["received_ns"]))
        if len(samples) > 1 else None,
    }


def collect(duration, base_frame):
    import rclpy
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.time import Time
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import LaserScan
    from tf2_ros import Buffer, TransformException, TransformListener

    scans, clocks, transforms = [], [], []
    tf_error = None
    origin = time.monotonic_ns()
    rclpy.init(args=[])
    node = None
    try:
        node = rclpy.create_node("task4_scan_clock_check", enable_rosout=False)
        buffer = Buffer()
        listener = TransformListener(buffer, node)

        def on_scan(msg):
            scans.append({
                "received_ns": time.monotonic_ns() - origin,
                "stamp_ns": stamp_ns(msg.header.stamp),
                "frame_id": msg.header.frame_id,
            })

        def on_clock(msg):
            clocks.append({
                "received_ns": time.monotonic_ns() - origin,
                "stamp_ns": stamp_ns(msg.clock),
            })

        node.create_subscription(LaserScan, "/scan", on_scan, qos_profile_sensor_data)
        node.create_subscription(Clock, "/clock", on_clock, qos_profile_sensor_data)
        deadline = time.monotonic() + duration
        next_tf = time.monotonic()
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=min(0.05, max(0, deadline - time.monotonic())))
            now = time.monotonic()
            if scans and scans[-1]["frame_id"] and now >= next_tf:
                next_tf = now + 0.5
                try:
                    source = scans[-1]["frame_id"]
                    tf = buffer.lookup_transform(base_frame, source, Time())
                    t, q = tf.transform.translation, tf.transform.rotation
                    transforms.append({
                        "received_ns": time.monotonic_ns() - origin,
                        "source": source,
                        "stamp_ns": stamp_ns(tf.header.stamp),
                        "translation_m": [t.x, t.y, t.z],
                        "quaternion_xyzw": [q.x, q.y, q.z, q.w],
                    })
                    tf_error = None
                except TransformException as exc:
                    tf_error = str(exc)
        publishers = {
            topic: sorted({f"{info.node_namespace.rstrip('/')}/{info.node_name}"
                           for info in node.get_publishers_info_by_topic(topic)})
            for topic in ("/scan", "/clock", "/tf", "/tf_static")
        }
        listener.unregister()
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return scans, clocks, transforms, tf_error, publishers


def summarize(scans, clocks, transforms, base_frame, tf_error, publishers):
    pairs = pair_samples(scans, clocks)
    close = [pair for pair in pairs if abs(pair["receipt_delta_ns"]) <= 200_000_000]
    scan, clock = describe_stream(scans), describe_stream(clocks)
    frames = sorted({sample["frame_id"] for sample in scans})
    checks = {
        "one_nonempty_scan_frame": len(frames) == 1 and bool(frames[0]),
        "one_clock_publisher": len(publishers["/clock"]) == 1,
        "both_streams_advancing": scan["advancing"] and clock["advancing"],
        "at_least_10_pairs": len(close) >= 10,
        "all_close_pairs_within_1_second": bool(close) and all(
            abs(pair["stamp_delta_ns"]) < 1_000_000_000 for pair in close
        ),
        "at_least_3_consistent_tf_samples": len(transforms) >= 3 and all(
            tf["source"] == transforms[0]["source"]
            and math.dist(tf["translation_m"], transforms[0]["translation_m"]) < 0.001
            and abs(sum(a * b for a, b in zip(
                tf["quaternion_xyzw"], transforms[0]["quaternion_xyzw"]
            ))) >= math.cos(math.radians(0.1) / 2)
            for tf in transforms
        ),
    }
    return {
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Read-only samples. Compare TF to the model and audit node clocks separately.",
        "status": "SAMPLES_OK" if all(checks.values()) else "NEEDS_ATTENTION",
        "base_frame": base_frame,
        "scan_frames": frames,
        "scan": scan,
        "clock": clock,
        "close_pairs": len(close),
        "max_close_pair_stamp_delta_ns": max(
            (abs(pair["stamp_delta_ns"]) for pair in close), default=None
        ),
        "tf_samples": transforms,
        "last_tf_error": tf_error,
        "publishers": publishers,
        "checks": checks,
    }, pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--base-frame", default="base_link")
    parser.add_argument("--out", required=True, type=Path, help="Existing, unused run directory")
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error("--duration must be positive and finite")
    report_path = args.out / "scan_clock.json"
    pairs_path = args.out / "clock_pairs.jsonl"
    if not args.out.is_dir() or report_path.exists() or pairs_path.exists():
        parser.error("--out must exist and contain no previous scan/clock results")
    scans, clocks, transforms, tf_error, publishers = collect(args.duration, args.base_frame)
    report, pairs = summarize(scans, clocks, transforms, args.base_frame, tf_error, publishers)
    with pairs_path.open("x") as file:
        for pair in pairs:
            file.write(json.dumps(pair) + "\n")
    with report_path.open("x") as file:
        json.dump(report, file, indent=2)
        file.write("\n")
    print(f"{report['status']} | /scan={len(scans)} /clock={len(clocks)} "
          f"pairs={report['close_pairs']} TF={len(transforms)} | {report_path}")
    return 0 if report["status"] == "SAMPLES_OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
