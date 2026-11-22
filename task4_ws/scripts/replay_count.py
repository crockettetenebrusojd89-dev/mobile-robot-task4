#!/usr/bin/env python3
"""Replay recorded /task4/observations JSONL files through Inventory for T4.3 deduplication check."""

import argparse
import json
from pathlib import Path

import yaml

from task4_bringup.association import Inventory


def load_observations(paths):
    rows = []
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    rows.sort(key=lambda item: float(item.get("stamp", 0.0)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--obs", nargs="+", type=Path, required=True, help="Input observation JSONL file(s)")
    parser.add_argument("--rooms", type=Path, required=True, help="rooms.yaml path")
    parser.add_argument("--room", required=True, help="Canonical room key in rooms.yaml")
    parser.add_argument("--object-class", "--class", dest="object_class", default="chair")
    parser.add_argument("--gate", type=float, default=0.35)
    parser.add_argument("--min-hits", type=int, default=3)
    parser.add_argument("--room-margin", type=float, default=0.1)
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    args = parser.parse_args()

    rooms_cfg = yaml.safe_load(args.rooms.read_text(encoding="utf-8"))
    room_info = rooms_cfg["rooms"][args.room]
    inv = Inventory(
        object_class=args.object_class,
        room_polygon=room_info["boundary_polygon"],
        gate_m=args.gate,
        min_hits=args.min_hits,
        room_margin_m=args.room_margin,
    )

    rows = load_observations(args.obs)
    events = []
    for batch in rows:
        batch_events = inv.update(batch)
        if batch_events:
            events.extend(batch_events)

    snapshot = inv.snapshot()
    report = {
        "room": args.room,
        "input_files": [str(p) for p in args.obs],
        "input_frame_count": len(rows),
        "inventory": snapshot,
        "key_events": [e for e in events if e.get("type") in ("tentative_created", "confirmed", "ambiguity", "outside_room", "frame_rejected")],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "replay_result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out / "events.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + ("\n" if events else ""),
        encoding="utf-8",
    )
    print(json.dumps({
        "room": args.room,
        "input_frames": len(rows),
        "confirmed_count": snapshot["count"],
        "objects": snapshot["objects"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
