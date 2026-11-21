#!/usr/bin/env python3
"""Export world-frame model origins for offline evaluation."""

import argparse
from hashlib import sha256
import math
from pathlib import Path
from xml.etree import ElementTree

import yaml


CATEGORIES = {"chair", "bottle", "cup"}


def extract(path):
    source = path.read_bytes()
    worlds = ElementTree.fromstring(source).findall("world")
    if len(worlds) != 1 or not worlds[0].get("name"):
        raise ValueError("Expected one named SDF world")
    world = worlds[0]
    objects = []
    names = set()
    for entity in world:
        if entity.tag not in ("model", "include"):
            continue
        name = entity.get("name") if entity.tag == "model" else entity.findtext("name")
        category = name.split("_", 1)[0] if name else None
        if category not in CATEGORIES:
            continue
        if name in names:
            raise ValueError(f"Duplicate target name: {name}")
        poses = entity.findall("pose")
        has_placement_frame = (
            entity.get("placement_frame") is not None or entity.find("placement_frame") is not None
        )
        if len(poses) != 1 or poses[0].attrib or has_placement_frame:
            raise ValueError(f"{name} must specify a direct six-value world pose")
        values = [float(value) for value in (poses[0].text or "").split()]
        if len(values) != 6 or not all(math.isfinite(value) for value in values):
            raise ValueError(f"Invalid world pose for {name}")
        objects.append({"name": name, "category": category,
                        "position_m": values[:3], "rpy_rad": values[3:]})
        names.add(name)
    return {"schema_version": 1, "purpose": "offline_evaluation", "frame_id": "world",
            "world": world.attrib["name"], "source_sdf": path.name,
            "source_sha256": sha256(source).hexdigest(),
            "reference_point": "model_origin", "objects": objects}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        truth = extract(args.sdf)
        with args.out.open("x") as output:
            yaml.safe_dump(truth, output, sort_keys=False)
    except (ElementTree.ParseError, OSError, ValueError) as error:
        parser.error(str(error))
    print(f"{truth['world']}: {len(truth['objects'])} targets | {args.out}")


if __name__ == "__main__":
    main()
