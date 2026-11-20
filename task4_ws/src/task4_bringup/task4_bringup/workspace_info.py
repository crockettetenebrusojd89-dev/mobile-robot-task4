"""Verify the package entry point without starting nodes or moving a robot."""

import json
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory


def main():
    share = Path(get_package_share_directory("task4_bringup"))
    expected = [share / "config" / name for name in ("frames_topics.yaml", "rooms.example.yaml")]
    missing = [str(path) for path in expected if not path.is_file()]
    print(json.dumps({
        "package": "task4_bringup",
        "stage": "workspace_initialization",
        "ros_distro": os.environ.get("ROS_DISTRO"),
        "package_share": str(share),
        "config_files_present": not missing,
        "missing_files": missing,
        "robot_functions": "not implemented",
    }, ensure_ascii=False, indent=2))
    return 1 if missing else 0
