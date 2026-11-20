#!/usr/bin/env python3
"""Prepare project-local Fortress compatibility files without editing ROS installs."""

import hashlib
import json
from pathlib import Path


def main():
    workspace = Path(__file__).resolve().parents[1]
    overlay = workspace / ".compat"
    records = []
    overrides = {
        "irobot_create_description": {"urdf/create3.urdf.xacro"},
        "irobot_create_control": {"config/control.yaml"},
    }
    for package, edited_paths in overrides.items():
        source = Path("/opt/ros/humble/share") / package
        if not source.is_dir():
            raise FileNotFoundError(source)
        target = overlay / "share" / package
        target.mkdir(parents=True, exist_ok=True)
        special_dirs = {Path(name).parts[0] for name in edited_paths}
        for entry in source.iterdir():
            destination = target / entry.name
            if entry.name in special_dirs:
                destination.mkdir(exist_ok=True)
                for item in entry.iterdir():
                    relative = str(item.relative_to(source))
                    output = destination / item.name
                    if relative in edited_paths:
                        original = item.read_text()
                        replacement = original
                        if package == "irobot_create_description":
                            if "<render_engine>ogre</render_engine>" not in original and "<render_engine>ogre2</render_engine>" not in original:
                                raise RuntimeError("Unexpected sensor renderer; inspect the installed description")
                            replacement = original.replace("<render_engine>ogre</render_engine>", "<render_engine>ogre2</render_engine>")
                        output.write_text(replacement)
                        records.append({
                            "source": str(item),
                            "source_sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
                            "output": str(output.relative_to(workspace)),
                            "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                            "purpose": "Use Ogre2 sensors" if package == "irobot_create_description" else "Use unmodified base controller defaults, including odometry TF",
                        })
                    elif not output.exists() and not output.is_symlink():
                        output.symlink_to(item, target_is_directory=item.is_dir())
            elif not destination.exists() and not destination.is_symlink():
                destination.symlink_to(entry, target_is_directory=entry.is_dir())
        index = overlay / "share/ament_index/resource_index/packages"
        index.mkdir(parents=True, exist_ok=True)
        (index / package).touch()
    (overlay / "COLCON_IGNORE").touch()
    (overlay / "manifest.json").write_text(json.dumps({"files": records}, ensure_ascii=False, indent=2) + "\n")
    print(f"Project-local simulation overlay ready: {overlay}")


if __name__ == "__main__":
    main()
