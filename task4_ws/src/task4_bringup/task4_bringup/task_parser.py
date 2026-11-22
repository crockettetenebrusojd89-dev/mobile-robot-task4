"""Chinese keyword extraction and structured task payload builder; no ROS dependency."""

from datetime import datetime
from pathlib import Path
import time

import yaml


DEFAULT_ROOM_ALIASES = {
    "living_room": ["客厅", "起居室", "living_room", "living room"],
    "kitchen": ["厨房", "kitchen"],
    "bedroom": ["卧室", "睡房", "bedroom"],
}


def load_yaml_config(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def default_config_paths():
    config_dir = Path(__file__).resolve().parents[1] / "config"
    if not (config_dir / "rooms.yaml").is_file():
        # Handle installed package layout under share/task4_bringup/config
        from ament_index_python.packages import get_package_share_directory

        config_dir = Path(get_package_share_directory("task4_bringup")) / "config"
    return config_dir / "rooms.yaml", config_dir / "objects.yaml"


def _match_longest_entities(text, alias_map):
    """Find distinct canonical keys in text by greedily selecting longest non-overlapping aliases."""
    candidates = []
    for canonical, aliases in alias_map.items():
        for alias in aliases:
            if alias:
                candidates.append((str(alias), canonical))
    candidates.sort(key=lambda item: len(item[0]), reverse=True)

    occupied = [False] * len(text)
    matched = {}
    for alias, canonical in candidates:
        start = 0
        while True:
            idx = text.find(alias, start)
            if idx < 0:
                break
            end = idx + len(alias)
            if not any(occupied[idx:end]):
                for pos in range(idx, end):
                    occupied[pos] = True
                matched.setdefault(canonical, alias)
            start = idx + 1
    return matched


def build_room_aliases(rooms_config):
    rooms = rooms_config.get("rooms", {})
    alias_map = {}
    displays = {}
    for key, info in rooms.items():
        display = str(info.get("display_name") or key)
        displays[key] = display
        aliases = set(DEFAULT_ROOM_ALIASES.get(key, []))
        aliases.add(key)
        aliases.add(display)
        for extra in info.get("synonyms", []):
            aliases.add(str(extra))
        alias_map[key] = sorted(aliases, key=len, reverse=True)
    return alias_map, displays


def build_object_aliases(objects_config):
    objects = objects_config.get("objects", {})
    alias_map = {}
    meta = {}
    for key, info in objects.items():
        display = str(info.get("display_name") or key)
        aliases = {key, display}
        for syn in info.get("synonyms", []):
            aliases.add(str(syn))
        alias_map[key] = sorted(aliases, key=len, reverse=True)
        meta[key] = {
            "display_name": display,
            "enabled": bool(info.get("enabled", False)),
            "note": info.get("note"),
        }
    return alias_map, meta


def generate_task_id(now=None):
    dt = now or datetime.now()
    return dt.strftime("t%Y%m%d-%H%M%S")


def parse_task(
    text,
    rooms_config,
    objects_config,
    *,
    source="text",
    stamp=None,
    task_id=None,
    require_enabled=False,
):
    """Parse a Chinese instruction into a structured task dict or an error dict."""
    raw = str(text or "").strip()
    if not raw:
        return {"ok": False, "error": "empty_text", "message": "指令为空，请重新说出房间和物品。"}

    room_aliases, room_displays = build_room_aliases(rooms_config)
    obj_aliases, obj_meta = build_object_aliases(objects_config)

    matched_rooms = _match_longest_entities(raw.lower(), room_aliases)
    matched_objects = _match_longest_entities(raw.lower(), obj_aliases)

    if len(matched_rooms) == 0:
        return {"ok": False, "error": "missing_room", "message": "未识别到目标房间（客厅/厨房/卧室），请重说。"}
    if len(matched_rooms) > 1:
        return {
            "ok": False,
            "error": "ambiguous_room",
            "rooms": sorted(matched_rooms.keys()),
            "message": f"检测到多个房间（{', '.join(sorted(matched_rooms.keys()))}），一次请只指定一个房间。",
        }

    if len(matched_objects) == 0:
        return {"ok": False, "error": "missing_object", "message": "未识别到目标物品类别，请重说。"}
    if len(matched_objects) > 1:
        return {
            "ok": False,
            "error": "ambiguous_object",
            "objects": sorted(matched_objects.keys()),
            "message": f"检测到多个物品类别（{', '.join(sorted(matched_objects.keys()))}），一次请只指定一种物品。",
        }

    room = next(iter(matched_rooms))
    object_class = next(iter(matched_objects))
    info = obj_meta[object_class]
    if require_enabled and not info["enabled"]:
        return {
            "ok": False,
            "error": "object_disabled",
            "object_class": object_class,
            "message": f"当前场景未启用物品类别 {info['display_name']}({object_class})，请先确认检测模型配置。",
        }

    return {
        "ok": True,
        "task": {
            "task_id": task_id or generate_task_id(),
            "room": room,
            "room_display": room_displays[room],
            "object_class": object_class,
            "object_display": info["display_name"],
            "object_enabled": info["enabled"],
            "matched_room_alias": matched_rooms[room],
            "matched_object_alias": matched_objects[object_class],
            "text": raw,
            "source": source,
            "stamp": float(time.time() if stamp is None else stamp),
        },
    }
