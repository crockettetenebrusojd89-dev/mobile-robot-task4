#!/usr/bin/env python3
"""Send one map-frame goal to Nav2 and save its Action outcome."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import signal
import sys

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.parameter import Parameter
from rclpy.signals import SignalHandlerOptions
from rclpy.utilities import remove_ros_args

from task4_bringup.navigation import NavigationClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x", type=float, required=True, help="Map x in metres")
    parser.add_argument("--y", type=float, required=True, help="Map y in metres")
    parser.add_argument("--yaw", type=float, required=True, help="Heading in radians")
    parser.add_argument("--timeout", type=float, default=120.0, help="Execution deadline in wall seconds")
    parser.add_argument("--cancel-after", type=float, help="Cancel after this many wall seconds of execution")
    parser.add_argument("--out", type=Path, help="JSON output path")
    args = parser.parse_args(remove_ros_args(sys.argv)[1:])

    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node(
        "task4_nav_goal_probe", parameter_overrides=[Parameter("use_sim_time", value=True)]
    )
    interrupted = False

    def request_stop(_signum, _frame):
        nonlocal interrupted
        interrupted = True

    stop_signals = (signal.SIGINT, signal.SIGTERM)
    old_handlers = {sig: signal.signal(sig, request_stop) for sig in stop_signals}
    try:
        navigator = NavigationClient(node)
        try:
            navigator.start(args.x, args.y, args.yaw, timeout=args.timeout, cancel_after=args.cancel_after)
        except ValueError as error:
            parser.error(str(error))
        try:
            while True:
                if interrupted:
                    navigator.cancel()
                result = navigator.poll()
                if result is not None:
                    break
                rclpy.spin_once(node, timeout_sec=0.05)
        except ExternalShutdownException:
            return 2

        output = json.dumps(asdict(result), ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(output, encoding="utf-8")
        print(output, end="")
        return 0 if result.succeeded else 1
    finally:
        for sig, handler in old_handlers.items():
            signal.signal(sig, handler)
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    sys.exit(main())
