#!/usr/bin/env python3
"""Check the live Task 4 simulation before publishing a demonstration task."""

import argparse
from functools import partial
import json
import math
import time

from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.msg import State
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from rcl_interfaces.msg import ParameterType
from rcl_interfaces.srv import GetParameters
import rclpy
from rclpy.action import ActionClient
from rclpy.qos import DurabilityPolicy, QoSProfile, qos_profile_sensor_data
from rclpy.time import Time
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener


LIFECYCLE_NODES = ("map_server", "amcl", "planner_server", "controller_server", "bt_navigator")
SENSORS = {
    "/scan": (LaserScan, lambda msg: bool(msg.ranges)),
    "/oakd/rgb/preview/image_raw": (Image, lambda msg: bool(msg.data)),
    "/oakd/rgb/preview/depth": (Image, lambda msg: bool(msg.data)),
    "/oakd/rgb/preview/camera_info": (CameraInfo, lambda msg: msg.k[0] > 0 and msg.k[4] > 0),
}
MAX_STREAM_AGE_SEC = 3.0


def stamp_seconds(stamp):
    return stamp.sec + stamp.nanosec / 1_000_000_000


def check_demo(node, timeout):
    samples = {}
    perception_status = None
    amcl_pose = None

    def observe(name, stamp, require_advance=False):
        if not math.isfinite(stamp) or stamp <= 0:
            return
        previous = samples.get(name)
        if previous is not None and stamp == previous["stamp"] and require_advance:
            return
        advanced = previous is not None and (
            stamp > previous["stamp"] or (stamp == previous["stamp"] and previous["advanced"])
        )
        samples[name] = {"stamp": stamp, "received": time.monotonic(), "advanced": advanced}

    def receive_sensor(name, has_data, msg):
        if msg.header.frame_id and has_data(msg):
            observe(name, stamp_seconds(msg.header.stamp))

    def receive_pose(msg):
        nonlocal amcl_pose
        if msg.header.frame_id == "map" and stamp_seconds(msg.header.stamp) > 0:
            amcl_pose = stamp_seconds(msg.header.stamp)

    def receive_perception(msg, *, status=False):
        nonlocal perception_status
        try:
            data = json.loads(msg.data)
            if not isinstance(data, dict):
                return
            if status:
                perception_status = (data, time.monotonic())
            elif data.get("valid_frame") is True and data.get("frame_id") == "map":
                observe("/task4/observations", float(data["stamp"]), require_advance=True)
        except (KeyError, TypeError, ValueError):
            return

    def stream_check(name, now, require_advance=False):
        sample = samples.get(name)
        if sample is None:
            return {"ok": False, "detail": "no valid message received"}
        age = now - sample["received"]
        return {
            "ok": age <= MAX_STREAM_AGE_SEC and (not require_advance or sample["advanced"]),
            "stamp": sample["stamp"],
            "age_sec": round(age, 3),
            "advanced": sample["advanced"],
        }

    node.create_subscription(Clock, "/clock",
                             lambda msg: observe("/clock", stamp_seconds(msg.clock), require_advance=True),
                             qos_profile_sensor_data)
    for name, (msg_type, has_data) in SENSORS.items():
        node.create_subscription(msg_type, name, partial(receive_sensor, name, has_data),
                                 qos_profile_sensor_data)
    node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", receive_pose,
                             QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
    node.create_subscription(String, "/task4/observations", receive_perception, 10)
    node.create_subscription(String, "/task4/perception_status", partial(receive_perception, status=True), 10)
    tf_buffer = Buffer()
    tf_listener = TransformListener(tf_buffer, node)
    navigation = ActionClient(node, NavigateToPose, "navigate_to_pose")

    services = {
        name: (node.create_client(GetState, f"/{name}/get_state"), GetState.Request())
        for name in LIFECYCLE_NODES
    }
    services["use_astar"] = (
        node.create_client(GetParameters, "/planner_server/get_parameters"),
        GetParameters.Request(names=["GridBased.use_astar"]),
    )
    pending = {}
    replies = {}
    started = time.monotonic()
    next_poll = started
    checks = {}
    while rclpy.ok():
        now = time.monotonic()
        for name, future in list(pending.items()):
            if future.done():
                replies[name] = future.result()
                del pending[name]
        if now >= next_poll:
            next_poll = now + 0.5
            for name, (client, request) in services.items():
                if name not in pending and client.service_is_ready():
                    pending[name] = client.call_async(request)

        checks = {name: stream_check(name, now) for name in SENSORS}
        checks["/clock"] = stream_check("/clock", now, require_advance=True)
        for name in LIFECYCLE_NODES:
            state = replies[name].current_state if name in replies else State()
            checks[f"/{name}"] = {"ok": state.id == State.PRIMARY_STATE_ACTIVE,
                                  "state": state.label or "no response"}
        astar = replies["use_astar"].values if "use_astar" in replies else []
        astar_enabled = astar[0].bool_value if astar and astar[0].type == ParameterType.PARAMETER_BOOL else None
        checks["GridBased.use_astar"] = {"ok": astar_enabled is True, "value": astar_enabled}
        checks["/amcl_pose"] = {"ok": amcl_pose is not None, "map_stamp": amcl_pose}
        checks["map -> base_link"] = {"ok": bool(tf_buffer.can_transform("map", "base_link", Time()))}
        checks["/navigate_to_pose"] = {"ok": navigation.server_is_ready()}
        subscribers = node.get_subscriptions_info_by_topic("/task4/task")
        checks["/task4/task"] = {"ok": any(endpoint.node_name == "search_manager" for endpoint in subscribers)}
        checks["/task4/observations"] = stream_check("/task4/observations", now, require_advance=True)
        checks["/task4/perception_status"] = {"ok": False, "detail": "no status received"}
        if perception_status is not None:
            data, received = perception_status
            age = now - received
            checks["/task4/perception_status"] = {
                "ok": age <= MAX_STREAM_AGE_SEC and data.get("stale") is False and data.get("target_frame") == "map",
                "age_sec": round(age, 3),
                "stale": data.get("stale"),
                "target_frame": data.get("target_frame"),
                "last_error": data.get("last_error"),
            }
        if all(check["ok"] for check in checks.values()) or now - started >= timeout:
            break
        rclpy.spin_once(node, timeout_sec=min(0.1, timeout - (now - started)))

    return {"ok": bool(checks) and all(check["ok"] for check in checks.values()), "checks": checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=20.0, help="maximum wait in wall-clock seconds")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a positive finite number")

    rclpy.init()
    node = rclpy.create_node("task4_demo_preflight")
    try:
        report = check_demo(node, args.timeout)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
