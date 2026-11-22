"""Atomic task result persistence and read-back integrity verification; no ROS dependency."""

import hashlib
import json
import math
import os
from pathlib import Path

from PIL import Image

from task4_bringup.map_annotate import render_annotated_map


def atomic_write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path, payload):
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    )


def save_run_results(
    run_dir,
    *,
    task,
    inventory_snapshot,
    viewpoints,
    status_record,
    map_yaml_path,
    log_lines=(),
    render_scale=3,
):
    """Write all run artifacts atomically and immediately verify read-back consistency."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    atomic_write_json(run_dir / "task.json", task)
    inventory_out = {
        "task_id": task.get("task_id"),
        "room": task.get("room"),
        "object_class": inventory_snapshot.get("object_class"),
        "count": int(inventory_snapshot["count"]),
        "objects": list(inventory_snapshot["objects"]),
        "tentative": list(inventory_snapshot.get("tentative", [])),
        "ambiguity_count": int(inventory_snapshot.get("ambiguity_count", 0)),
        "rejected_counts": dict(inventory_snapshot.get("rejected_counts", {})),
    }
    atomic_write_json(run_dir / "inventory.json", inventory_out)
    atomic_write_json(run_dir / "viewpoints.json", viewpoints)

    title = (
        f"{task.get('room', '')} {task.get('object_class', '')} "
        f"count={inventory_out['count']} [{status_record.get('status', '')}]"
    ).strip()
    map_meta = render_annotated_map(
        map_yaml_path,
        inventory_out["objects"],
        run_dir / "map_annotated.png",
        title=title,
        scale=render_scale,
    )
    atomic_write_json(run_dir / "map_annotations.json", map_meta)
    atomic_write_json(run_dir / "status.json", status_record)
    atomic_write_text(
        run_dir / "run.log",
        "".join(line if line.endswith("\n") else line + "\n" for line in log_lines),
    )
    return verify_run_directory(run_dir)


def verify_run_directory(run_dir):
    """Read back saved run artifacts and check internal consistency."""
    run_dir = Path(run_dir)
    errors = []
    required = [
        "task.json",
        "inventory.json",
        "viewpoints.json",
        "status.json",
        "map_annotations.json",
        "map_annotated.png",
        "run.log",
    ]
    for name in required:
        if not (run_dir / name).is_file():
            errors.append(f"missing_file:{name}")
    if errors:
        return {"ok": False, "errors": errors}

    try:
        task = json.loads((run_dir / "task.json").read_text(encoding="utf-8"))
        inv = json.loads((run_dir / "inventory.json").read_text(encoding="utf-8"))
        viewpoints = json.loads((run_dir / "viewpoints.json").read_text(encoding="utf-8"))
        status = json.loads((run_dir / "status.json").read_text(encoding="utf-8"))
        ann = json.loads((run_dir / "map_annotations.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "errors": [f"json_read_error:{exc}"]}

    if task.get("source") == "voice":
        try:
            voice = json.loads((run_dir / "voice.json").read_text(encoding="utf-8"))
            audio = (run_dir / "voice.wav").read_bytes()
            if voice["task_id"] != task["task_id"] or voice["input"] != task.get("voice_input"):
                errors.append("voice_task_mismatch")
            if "".join(voice["transcript"].split()) != task.get("text"):
                errors.append("voice_transcript_mismatch")
            if not audio or hashlib.sha256(audio).hexdigest() != voice["audio_sha256"]:
                errors.append("voice_audio_mismatch")
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(f"voice_read_error:{exc}")

    objects = inv.get("objects", [])
    if inv.get("count") != len(objects):
        errors.append(f"count_mismatch:count={inv.get('count')} vs len(objects)={len(objects)}")

    ids = [obj.get("id") for obj in objects]
    if any(not isinstance(oid, int) or oid < 1 for oid in ids):
        errors.append("invalid_object_id")
    if len(set(ids)) != len(ids):
        errors.append("duplicate_object_ids")

    markers = ann.get("markers", [])
    if len(markers) != len(objects):
        errors.append(f"marker_count_mismatch:markers={len(markers)} vs objects={len(objects)}")
    else:
        for obj, marker in zip(objects, markers):
            if obj.get("id") != marker.get("id"):
                errors.append(f"marker_id_mismatch:{obj.get('id')} vs {marker.get('id')}")
            if (
                not math.isfinite(marker.get("x", math.nan))
                or not math.isfinite(marker.get("y", math.nan))
                or abs(float(obj["x"]) - float(marker["x"])) > 1e-6
                or abs(float(obj["y"]) - float(marker["y"])) > 1e-6
            ):
                errors.append(f"marker_coord_mismatch:id={obj.get('id')}")

    try:
        with Image.open(run_dir / "map_annotated.png") as img:
            w, h = img.size
        if (w, h) != (ann.get("rendered_width"), ann.get("rendered_height")):
            errors.append(
                f"image_size_mismatch:({w},{h}) vs ({ann.get('rendered_width')},{ann.get('rendered_height')})"
            )
    except Exception as exc:
        errors.append(f"image_read_error:{exc}")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "task_id": task.get("task_id"),
        "status": status.get("status"),
        "count": inv.get("count"),
        "viewpoints_recorded": len(viewpoints),
        "markers": len(markers),
    }
