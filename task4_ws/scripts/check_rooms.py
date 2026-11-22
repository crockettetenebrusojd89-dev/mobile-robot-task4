#!/usr/bin/env python3
"""Check room geometry and render the calibrated points on a Nav2 map."""

import argparse
from hashlib import sha256
from itertools import combinations
import json
import math
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label
import yaml


MIN_CLEARANCE_M = 0.30
WORKSPACE = Path(__file__).resolve().parents[1]


def numbers(values, length, name):
    if not isinstance(values, list) or len(values) != length:
        raise ValueError(f"{name} must have {length} coordinates")
    if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
           for v in values):
        raise ValueError(f"{name} must contain finite numbers")
    return values


def angles(values, name):
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} needs at least one yaw")
    numbers(values, len(values), name)
    if any(abs(value) > math.pi for value in values):
        raise ValueError(f"{name} must be in radians within [-pi, pi]")
    return values


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load_map(path, rooms):
    if (WORKSPACE / rooms["map_file"]).resolve() != path.resolve():
        raise ValueError("The rooms map_file does not match --map")
    if digest(path) != rooms["map_sha256"]:
        raise ValueError("The map YAML hash does not match the room calibration")
    meta = yaml.safe_load(path.read_text())
    if meta.get("mode", "trinary") != "trinary":
        raise ValueError("Room checks require a trinary map")
    image_path = path.parent / meta["image"]
    if digest(image_path) != rooms["map_image_sha256"]:
        raise ValueError("The map image hash does not match the room calibration")
    with Image.open(image_path) as image:
        if image.mode != "L":
            raise ValueError("Room checks require an 8-bit grayscale map")
        shade = np.asarray(image, dtype=float) / 255
    resolution, = numbers([meta["resolution"]], 1, "resolution")
    free_thresh, occupied_thresh = numbers(
        [meta["free_thresh"], meta["occupied_thresh"]], 2, "map thresholds"
    )
    if resolution <= 0 or not 0 <= free_thresh < occupied_thresh <= 1:
        raise ValueError("Invalid resolution or trinary thresholds")
    origin_x, origin_y, yaw = numbers(meta["origin"], 3, "origin")
    occupancy = shade if meta["negate"] else 1 - shade
    codes = np.select([occupancy < free_thresh, occupancy > occupied_thresh], [254, 0], default=205)
    height, width = codes.shape
    cos, sin = math.cos(yaw), math.sin(yaw)

    def pixel(x, y):
        dx, dy = x - origin_x, y - origin_y
        u = (cos * dx + sin * dy) / resolution
        v = (-sin * dx + cos * dy) / resolution
        return u, height - v

    def cell(x, y):
        u, v = pixel(x, y)
        column, row = math.floor(u), math.ceil(v) - 1
        if not 0 <= row < height or not 0 <= column < width:
            raise ValueError(f"Point ({x}, {y}) is outside the map")
        return row, column

    return codes, resolution, pixel, cell


def check_rooms(config, codes, resolution, cell):
    definitions = config["rooms"]
    if not isinstance(definitions, dict) or not definitions:
        raise ValueError("No room definitions")
    polygons = {}
    for room, definition in definitions.items():
        polygon = np.array([numbers(vertex, 2, room) for vertex in definition["boundary_polygon"]],
                           dtype=np.float32).reshape(-1, 2)
        if len(polygon) < 3 or not cv2.isContourConvex(polygon) or cv2.contourArea(polygon) < 1e-4:
            raise ValueError(f"{room} must have a nondegenerate convex boundary")
        for vertex in polygon:
            cell(*vertex)
        polygons[room] = polygon

    for (left, a), (right, b) in combinations(polygons.items(), 2):
        area, _ = cv2.intersectConvexConvex(a, b, handleNested=True)
        if area > 1e-4:
            raise ValueError(f"Room boundaries overlap: {left} and {right}")

    # Lower bound from any point in the sampled cell to a non-free cell square.
    free = codes == 254
    padded = np.pad(free, 1, constant_values=False)
    clearance = (distance_transform_edt(padded)[1:-1, 1:-1] - math.sqrt(2)) * resolution
    components, _ = label(free & (clearance >= MIN_CLEARANCE_M))
    used_components = set()
    report = {}
    for room, definition in definitions.items():
        display_name = definition["display_name"]
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"{room} needs a display name")
        polygon = polygons[room]
        entrance = numbers(definition["entrance_pose"], 3, f"{room} entrance")
        angles(entrance[2:], f"{room} entrance yaw")
        points = definition["observation_points"]
        if not isinstance(points, list) or not points:
            raise ValueError(f"{room} has no observation points")

        def check_point(x, y, name, headings):
            if cv2.pointPolygonTest(polygon, (float(x), float(y)), False) <= 0:
                raise ValueError(f"{name} must be inside its room")
            row, column = cell(x, y)
            component = int(components[row, column])
            if not component:
                raise ValueError(f"{name} must be free and have {MIN_CLEARANCE_M:.2f} m clearance")
            used_components.add(component)
            return {"xy": [x, y], "yaw_count": len(headings), "row": row, "column": column,
                    "clearance_lower_bound_m": round(float(clearance[row, column]), 3)}

        observations = []
        for index, point in enumerate(points, 1):
            name = f"{room} observation {index}"
            x, y = numbers([point["x"], point["y"]], 2, name)
            observations.append(check_point(x, y, name, angles(point["yaws"], name)))
        report[room] = {"entrance": check_point(*entrance[:2], f"{room} entrance", entrance[2:]),
                        "observations": observations}

    if len(used_components) != 1:
        raise ValueError("Entrances and observations do not share one clearance-safe component")
    return report


def draw_overlay(codes, config, pixel, output):
    scale, border = 5, 30
    height, width = codes.shape
    gray = np.select([codes == 254, codes == 0], [250, 30], default=198).astype(np.uint8)
    canvas = cv2.copyMakeBorder(cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST),
                               border + 24, border + 38, border, border, cv2.BORDER_CONSTANT, value=247)
    canvas = cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR)

    def pt(x, y):
        u, v = pixel(x, y)
        return round(u * scale + border), round(v * scale + border + 24)

    colors = [(173, 90, 30), (58, 122, 39), (135, 51, 152)]
    rooms = list(config["rooms"].items())
    tint = canvas.copy()
    for index, (_, definition) in enumerate(rooms):
        polygon = np.array([pt(*p) for p in definition["boundary_polygon"]])
        cv2.fillConvexPoly(tint, polygon, colors[index % len(colors)])
    canvas = cv2.addWeighted(canvas, .90, tint, .10, 0)

    for index, (room, definition) in enumerate(rooms):
        color = colors[index % len(colors)]
        polygon = np.array([pt(*p) for p in definition["boundary_polygon"]])
        cv2.polylines(canvas, [polygon], True, color, 2, cv2.LINE_AA)
        for n, p in enumerate(definition["observation_points"], 1):
            xy = pt(p["x"], p["y"])
            cv2.circle(canvas, xy, 6, color, -1, cv2.LINE_AA)
            cv2.putText(canvas, str(n), (xy[0] + 9, xy[1] - 7), cv2.FONT_HERSHEY_SIMPLEX,
                        .56, color, 2, cv2.LINE_AA)
        x, y, yaw = definition["entrance_pose"]
        cv2.arrowedLine(canvas, pt(x, y), pt(x + .32 * math.cos(yaw), y + .32 * math.sin(yaw)),
                        color, 3, cv2.LINE_AA, tipLength=.36)
        cv2.putText(canvas, room.replace("_", " ").title(), (border + index * 225, canvas.shape[0] - 35),
                    cv2.FONT_HERSHEY_SIMPLEX, .64, color, 2, cv2.LINE_AA)

    cv2.putText(canvas, "Task 4 room calibration", (border, 34), cv2.FONT_HERSHEY_SIMPLEX,
                .84, (30, 30, 30), 2, cv2.LINE_AA)
    cv2.putText(canvas, "Arrow: entrance heading   Dot: observation point   Gray: unknown",
                (border, canvas.shape[0] - 13), cv2.FONT_HERSHEY_SIMPLEX,
                .45, (52, 52, 52), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(output), canvas):
        raise OSError(f"Could not save {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rooms", type=Path, required=True)
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = yaml.safe_load(args.rooms.read_text())
        if config["schema_version"] != 1 or config["calibrated"] is not True or config["frame_id"] != "map":
            raise ValueError("Expected a calibrated version 1 room file in frame map")
        codes, resolution, pixel, cell = load_map(args.map, config)
        report = check_rooms(config, codes, resolution, cell)
        args.out.mkdir(parents=True, exist_ok=True)
        report_path = args.out / "summary.json"
        overlay = args.out / "rooms_overlay.png"
        if report_path.exists() or overlay.exists():
            raise FileExistsError("Choose a fresh output directory")
        draw_overlay(codes, config, pixel, overlay)
        summary = {
            "status": "ROOM_GEOMETRY_PASSED",
            "map_file": config["map_file"],
            "map_sha256": config["map_sha256"],
            "map_image_sha256": config["map_image_sha256"],
            "rooms_sha256": digest(args.rooms),
            "resolution_m": resolution,
            "connected_clearance_m": MIN_CLEARANCE_M,
            "rooms": report,
        }
        report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        print(f"Checked {len(report)} rooms; see {report_path} and {overlay}")
    except (KeyError, ValueError, TypeError, OSError, yaml.YAMLError, cv2.error) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
