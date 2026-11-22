#!/usr/bin/env python3
"""Record /task4/observations JSONL stream for a given duration or frame count."""

import argparse
import json
from pathlib import Path
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class ObservationRecorder(Node):
    def __init__(self, topic, out_path, view_label=None):
        super().__init__("task4_observation_recorder")
        self.view_label = view_label
        self.count = 0
        self.valid_count = 0
        self._file = out_path.open("w", encoding="utf-8")
        self.create_subscription(String, topic, self._on_obs, 20)

    def _on_obs(self, msg):
        payload = json.loads(msg.data)
        if self.view_label is not None:
            payload["view"] = self.view_label
        self._file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self._file.flush()
        self.count += 1
        if payload.get("valid_frame"):
            self.valid_count += 1

    def close(self):
        self._file.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default="/task4/observations")
    parser.add_argument("--duration", type=float, default=10.0, help="Recording wall duration in seconds")
    parser.add_argument("--view", default=None, help="Optional view label added to each JSONL row")
    parser.add_argument("--out", type=Path, required=True, help="Output JSONL file path")
    args = parser.parse_args()

    if args.duration <= 0:
        parser.error("--duration must be positive")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    node = ObservationRecorder(args.topic, args.out, view_label=args.view)
    try:
        deadline = time.monotonic() + args.duration
        while time.monotonic() < deadline and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        summary = {"out": str(args.out), "frames": node.count, "valid_frames": node.valid_count}
        node.close()
        node.destroy_node()
        rclpy.try_shutdown()
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if node.count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
