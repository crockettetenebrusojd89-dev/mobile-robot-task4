"""2D room polygon containment and boundary margin helpers; no ROS dependency."""

import math


def _point_to_segment_distance(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq <= 1e-18:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_len_sq))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def polygon_edge_distance(x, y, polygon):
    """Return the minimum Euclidean distance from (x, y) to the polygon boundary."""
    if len(polygon) < 3:
        raise ValueError("polygon must contain at least 3 vertices")
    min_dist = math.inf
    n = len(polygon)
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        d = _point_to_segment_distance(x, y, ax, ay, bx, by)
        if d < min_dist:
            min_dist = d
    return min_dist


def point_in_polygon(x, y, polygon):
    """Return True if (x, y) is inside or on the boundary of a 2D polygon."""
    if not (math.isfinite(x) and math.isfinite(y)):
        return False
    if len(polygon) < 3:
        raise ValueError("polygon must contain at least 3 vertices")
    if polygon_edge_distance(x, y, polygon) <= 1e-9:
        return True

    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_intersect = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_intersect:
                inside = not inside
    return inside


def point_in_room(x, y, polygon, margin_m=0.1):
    """Check if (x, y) lies within polygon expanded (or shrunk if < 0) by margin_m."""
    if not (math.isfinite(x) and math.isfinite(y)):
        return False
    if not math.isfinite(margin_m):
        raise ValueError("margin_m must be finite")
    inside = point_in_polygon(x, y, polygon)
    if margin_m >= 0.0:
        if inside:
            return True
        return polygon_edge_distance(x, y, polygon) <= margin_m
    # Negative margin requires strict interior clearance of at least |margin_m|.
    return inside and polygon_edge_distance(x, y, polygon) >= (-margin_m)
