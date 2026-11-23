"""CLI tool to parse a Chinese task sentence and publish JSON on /task4/task."""

import argparse
import json
from pathlib import Path
import time

from task4_bringup.task_parser import default_config_paths, load_yaml_config, parse_task


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="Chinese task instruction, e.g. '去厨房数一下有几把椅子'")
    parser.add_argument("--topic", default="/task4/task")
    parser.add_argument("--rooms", type=Path, default=None)
    parser.add_argument("--objects", type=Path, default=None)
    parser.add_argument("--allow-disabled", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Parse and print JSON without ROS publishing")
    parsed_args = parser.parse_args(args)

    default_rooms, default_objects = default_config_paths()
    rooms_cfg = load_yaml_config(parsed_args.rooms or default_rooms)
    objects_cfg = load_yaml_config(parsed_args.objects or default_objects)

    result = parse_task(
        parsed_args.text,
        rooms_cfg,
        objects_cfg,
        source="text",
        require_enabled=not parsed_args.allow_disabled,
    )
    if not result["ok"]:
        print(json.dumps(result, ensure_ascii=False))
        return 1

    payload = json.dumps(result["task"], ensure_ascii=False, allow_nan=False)
    if parsed_args.dry_run:
        print(payload)
        return 0

    publish_error = publish_task(payload, parsed_args.topic)
    if publish_error:
        print(json.dumps({"ok": False, "error": publish_error, "topic": parsed_args.topic}, ensure_ascii=False))
        return 1
    print(payload)
    return 0


def publish_task(payload, topic, *, node_name="task4_task_cli"):
    """Wait for a subscriber and report a bounded DDS acknowledgement error."""
    import rclpy
    from rclpy.duration import Duration
    from rclpy.node import Node
    from std_msgs.msg import String

    rclpy.init()
    node = Node(node_name)
    try:
        pub = node.create_publisher(String, topic, 10)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and pub.get_subscription_count() == 0:
            rclpy.spin_once(node, timeout_sec=0.05)
        if pub.get_subscription_count() == 0:
            return "no_subscriber"
        # Allow DDS reliable endpoint handshake to settle before publishing and tearing down.
        settle_until = time.monotonic() + 2.0
        while time.monotonic() < settle_until:
            rclpy.spin_once(node, timeout_sec=0.05)
        msg = String()
        msg.data = payload
        pub.publish(msg)
        if not pub.wait_for_all_acked(Duration(seconds=8.0)):
            return "delivery_unconfirmed"
        flush_until = time.monotonic() + 0.5
        while time.monotonic() < flush_until:
            rclpy.spin_once(node, timeout_sec=0.05)
        return None
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
