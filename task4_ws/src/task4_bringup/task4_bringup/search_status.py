"""Pure status decision and terminal summary formatting for search_manager; no ROS dependency."""


def decide_status(
    viewpoint_records,
    perception_ok,
    save_ok,
    canceled,
    *,
    entrance_ok=True,
    cancel_confirmed=True,
    min_frames_per_dwell=3,
):
    """Determine final task status and primary reason from execution records.

    Returns (status, reason) where status is one of:
      COMPLETED | CANCELED | INCOMPLETE | FAILED
    """
    if canceled:
        if not cancel_confirmed:
            return "INCOMPLETE", "nav_cancel_unconfirmed"
        if not save_ok:
            return "FAILED", "save_verification_failed"
        return "CANCELED", "canceled_by_request"

    if not entrance_ok:
        return "FAILED", "entrance_navigation_failed"

    if not save_ok:
        return "FAILED", "save_verification_failed"

    if not viewpoint_records:
        return "INCOMPLETE", "no_viewpoints_executed"

    for idx, vp in enumerate(viewpoint_records):
        if not vp.get("nav_succeeded", False):
            return "INCOMPLETE", f"viewpoint_{idx}_navigation_failed:{vp.get('nav_outcome', 'unknown')}"
        if int(vp.get("valid_frames", 0)) < int(min_frames_per_dwell):
            return (
                "INCOMPLETE",
                f"viewpoint_{idx}_insufficient_valid_frames:{vp.get('valid_frames', 0)}/{min_frames_per_dwell}",
            )
        if not vp.get("perception_ok", True):
            return "INCOMPLETE", f"viewpoint_{idx}_perception_unhealthy"

    if not perception_ok:
        return "INCOMPLETE", "perception_stale_or_unavailable"

    return "COMPLETED", "all_viewpoints_completed"


def format_terminal_summary(task, inventory_snapshot, status, reason):
    """Format Task 4 R9 terminal summary lines."""
    task_id = task.get("task_id", "unknown")
    room_label = task.get("room_display") or task.get("room", "")
    obj_label = task.get("object_display") or task.get("object_class", "")
    count = int(inventory_snapshot.get("count", 0))
    objects = inventory_snapshot.get("objects", [])

    if status == "COMPLETED":
        lines = [f"[task {task_id}] {room_label} {obj_label} 搜索完成：共 {count} 个"]
    else:
        lines = [
            f"[task {task_id}] {room_label} {obj_label} 未完成：已确认 {count} 个，状态 {status}，原因 {reason}"
        ]

    for obj in objects:
        lines.append(
            f"  #{obj['id']} {obj['class']} (x={obj['x']:.3f}, y={obj['y']:.3f}, n_obs={obj.get('n_obs', 0)})"
        )
    return "\n".join(lines)
