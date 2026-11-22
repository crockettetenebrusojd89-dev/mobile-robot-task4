#!/usr/bin/env python3
"""Seed AMCL in the task4 simulation using a pose in the saved map frame."""

import argparse
import math
import sys
import time

from geometry_msgs.msg import PoseWithCovarianceStamped
import rclpy
from rclpy.duration import Duration
from rclpy.parameter import Parameter
from rclpy.utilities import remove_ros_args


def finite(text):
    value = float(text)
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError("pose coordinates must be finite")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x", type=finite, required=True, help="Map X in metres")
    parser.add_argument("--y", type=finite, required=True, help="Map Y in metres")
    parser.add_argument("--yaw", type=finite, required=True, help="Heading in radians")
    pose = parser.parse_args(remove_ros_args(sys.argv)[1:])

    rclpy.init()
    node = rclpy.create_node(
        "task4_set_initial_pose", parameter_overrides=[Parameter("use_sim_time", value=True)]
    )
    try:
        pub = node.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
        deadline = time.monotonic() + 8.0
        while not pub.get_subscription_count() or node.get_clock().now().nanoseconds == 0:
            if time.monotonic() >= deadline:
                print("Initial pose was not sent. Start AMCL and the simulation clock.", file=sys.stderr)
                return 1
            rclpy.spin_once(node, timeout_sec=0.1)

        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.pose.pose.position.x = pose.x
        msg.pose.pose.position.y = pose.y
        msg.pose.pose.orientation.z = math.sin(pose.yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(pose.yaw / 2.0)
        msg.pose.covariance[0] = msg.pose.covariance[7] = 0.15 ** 2
        msg.pose.covariance[35] = math.radians(10) ** 2
        acknowledged = False
        for _ in range(3):
            msg.header.stamp = node.get_clock().now().to_msg()
            pub.publish(msg)
            acknowledged |= pub.wait_for_all_acked(Duration(seconds=0.8))
            rclpy.spin_once(node, timeout_sec=0.25)
        if not acknowledged:
            print("The initial pose was not acknowledged.", file=sys.stderr)
            return 1
        print(f"Published initial map pose ({pose.x:.3f}, {pose.y:.3f}, {pose.yaw:.3f} rad)")
        return 0
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
