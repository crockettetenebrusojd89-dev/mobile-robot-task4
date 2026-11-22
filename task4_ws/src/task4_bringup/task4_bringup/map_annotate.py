"""Map coordinate conversion and atomic annotated-map rendering; no ROS dependency."""

from hashlib import sha256
import math
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import yaml


def _atomic_write_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def world_to_pixel(x, y, resolution, origin, width, height):
    """Convert map metric (x, y) to image (u, v) pixel coordinates (top-left origin)."""
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError("x and y must be finite")
    if not (math.isfinite(resolution) and resolution > 0):
        raise ValueError("resolution must be positive finite")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    ox, oy, yaw = [float(v) for v in origin]
    if not all(math.isfinite(v) for v in (ox, oy, yaw)):
        raise ValueError("origin must contain 3 finite numbers")

    dx, dy = float(x) - ox, float(y) - oy
    c, s = math.cos(yaw), math.sin(yaw)
    u = (c * dx + s * dy) / resolution
    v_bottom = (-s * dx + c * dy) / resolution
    v = float(height) - v_bottom
    return float(u), float(v)


def pixel_to_world(u, v, resolution, origin, width, height):
    """Inverse of world_to_pixel: convert image (u, v) back to map metric (x, y)."""
    if not (math.isfinite(u) and math.isfinite(v)):
        raise ValueError("u and v must be finite")
    if not (math.isfinite(resolution) and resolution > 0):
        raise ValueError("resolution must be positive finite")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    ox, oy, yaw = [float(v) for v in origin]
    if not all(math.isfinite(v) for v in (ox, oy, yaw)):
        raise ValueError("origin must contain 3 finite numbers")

    v_bottom = float(height) - float(v)
    lx = float(u) * resolution
    ly = v_bottom * resolution
    c, s = math.cos(yaw), math.sin(yaw)
    x = ox + c * lx - s * ly
    y = oy + s * lx + c * ly
    return float(x), float(y)


def load_map_metadata(map_yaml_path):
    yaml_path = Path(map_yaml_path)
    meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    image_path = Path(meta["image"])
    if not image_path.is_absolute():
        image_path = yaml_path.parent / image_path
    with Image.open(image_path) as img:
        gray = np.asarray(img.convert("L"), dtype=np.uint8)
    height, width = gray.shape
    return {
        "map_yaml_path": str(yaml_path),
        "map_yaml_sha256": sha256(yaml_path.read_bytes()).hexdigest(),
        "map_image_path": str(image_path),
        "map_image_sha256": sha256(image_path.read_bytes()).hexdigest(),
        "resolution": float(meta["resolution"]),
        "origin": [float(v) for v in meta["origin"]],
        "width": int(width),
        "height": int(height),
        "gray": gray,
    }


def render_annotated_map(
    map_yaml_path,
    objects,
    out_png,
    *,
    title=None,
    scale=3,
):
    """Render confirmed object IDs onto a copy of the original map image and write atomically."""
    info = load_map_metadata(map_yaml_path)
    gray = info["gray"]
    width, height = info["width"], info["height"]
    resolution = info["resolution"]
    origin = info["origin"]

    # Upscale cleanly with nearest-neighbor so occupancy cells remain sharp and labels readable.
    scale = max(1, int(scale))
    bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    if scale > 1:
        bgr = cv2.resize(bgr, (width * scale, height * scale), interpolation=cv2.INTER_NEAREST)

    markers = []
    for obj in objects:
        obj_id = int(obj["id"])
        x, y = float(obj["x"]), float(obj["y"])
        u, v = world_to_pixel(x, y, resolution, origin, width, height)
        in_bounds = 0.0 <= u < width and 0.0 <= v < height
        markers.append({
            "id": obj_id,
            "class": str(obj["class"]),
            "x": x,
            "y": y,
            "px_u": u,
            "px_v": v,
            "in_bounds": in_bounds,
        })
        if in_bounds:
            su = int(round(u * scale))
            sv = int(round(v * scale))
            cv2.circle(bgr, (su, sv), 6, (25, 165, 35), 2)
            cv2.drawMarker(bgr, (su, sv), (20, 40, 220), cv2.MARKER_CROSS, 10, 1)
            label = f"#{obj_id}"
            cv2.putText(
                bgr,
                label,
                (su + 7, max(14, sv - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (15, 25, 190),
                2,
                cv2.LINE_AA,
            )

    if title:
        cv2.putText(
            bgr,
            str(title),
            (10, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (20, 20, 20),
            2,
            cv2.LINE_AA,
        )

    ok, encoded = cv2.imencode(".png", bgr)
    if not ok:
        raise OSError(f"Failed to encode annotated map PNG for {out_png}")
    _atomic_write_bytes(out_png, encoded.tobytes())

    return {
        "map_file": info["map_yaml_path"],
        "map_sha256": info["map_yaml_sha256"],
        "map_image": info["map_image_path"],
        "map_image_sha256": info["map_image_sha256"],
        "base_width": width,
        "base_height": height,
        "render_scale": scale,
        "rendered_width": width * scale,
        "rendered_height": height * scale,
        "resolution": resolution,
        "origin": origin,
        "markers": markers,
    }
