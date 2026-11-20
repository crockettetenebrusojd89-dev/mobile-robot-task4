#!/usr/bin/env python3
"""Read-only environment inventory; does not start ROS discovery or a simulator."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys


def inspect_environment():
    modules = {
        name: importlib.util.find_spec(name) is not None
        for name in ("rclpy", "ament_index_python", "setuptools", "cv2", "numpy", "yaml", "ultralytics")
    }
    executables = {name: shutil.which(name) for name in ("ros2", "colcon", "ign", "gazebo", "gz")}
    packages = {}
    try:
        from ament_index_python.packages import get_package_prefix, PackageNotFoundError
    except ImportError:
        packages["index_error"] = "ament_index_python is not available; source env.sh first"
    else:
        for name in ("rclpy", "rviz2", "nav2_bringup", "slam_toolbox", "turtlebot3_gazebo", "gazebo_ros", "turtlebot4_ignition_bringup", "yolo_bringup", "task4_bringup"):
            try:
                packages[name] = get_package_prefix(name)
            except PackageNotFoundError:
                packages[name] = None
    baseline_ready = (
        os.environ.get("ROS_DISTRO") == "humble"
        and sys.version_info >= (3, 10)
        and all(modules[name] for name in ("rclpy", "ament_index_python", "setuptools"))
        and all(executables[name] for name in ("ros2", "colcon"))
    )
    return {
        "scope": "workspace prerequisites only; task-four robot functions are not implemented or tested",
        "baseline_ready": bool(baseline_ready),
        "os": platform.freedesktop_os_release().get("PRETTY_NAME", platform.system()),
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "ros_distro": os.environ.get("ROS_DISTRO"),
        "executables": executables,
        "modules_discoverable": modules,
        "packages_in_current_environment": packages,
        "existing_turtlebot4_overlay_setup": str(Path.home() / "turtlebot4_ws/install/setup.bash") if (Path.home() / "turtlebot4_ws/install/setup.bash").is_file() else None,
        "notes": [
            "Module discovery does not verify runtime behavior or model inference.",
            "Missing optional simulator/detector packages do not fail the workspace check.",
            "Package visibility reflects the current terminal; an existing overlay is not automatically sourced.",
            "Robot model, simulator, voice provider and detector version still require selection and verification.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Also save this inventory as JSON")
    args = parser.parse_args()
    report = inspect_environment()
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(payload, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0 if report["baseline_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
