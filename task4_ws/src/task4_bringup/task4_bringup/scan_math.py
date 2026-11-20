"""Process LaserScan values in their original sensor frame; no ROS dependency."""

import math


def summarize_scan(ranges, angle_min, angle_increment, range_min, range_max):
    """Filter a scan and find its closest valid return, preserving its array index.

    Angles are radians and ranges are meters. Range limits are inclusive.
    No valid return is represented by nearest=None, never by a zero distance.
    """
    metadata = (angle_min, angle_increment, range_min, range_max)
    if not all(math.isfinite(value) for value in metadata):
        raise ValueError("角度与量程参数必须是有限数值")
    if range_min < 0 or range_max < range_min:
        raise ValueError("量程参数必须满足 0 <= range_min <= range_max")
    if len(ranges) > 1 and angle_increment == 0:
        raise ValueError("多个距离样本不能使用零角度间隔")

    valid_count = 0
    nearest_index = None
    nearest_distance = math.inf
    for index, distance in enumerate(ranges):
        if not math.isfinite(distance):
            continue
        if distance < range_min or distance > range_max:
            continue
        valid_count += 1
        if distance < nearest_distance:
            nearest_distance = float(distance)
            nearest_index = index

    nearest = None
    if nearest_index is not None:
        angle = angle_min + nearest_index * angle_increment
        nearest = {
            "index": nearest_index,
            "distance_m": nearest_distance,
            "angle_rad": angle,
            "angle_deg": math.degrees(angle),
            "x_m": nearest_distance * math.cos(angle),
            "y_m": nearest_distance * math.sin(angle),
        }
    return {
        "sample_count": len(ranges),
        "valid_count": valid_count,
        "invalid_count": len(ranges) - valid_count,
        "nearest": nearest,
    }
