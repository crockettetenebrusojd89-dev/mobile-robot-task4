"""Pure 3D back-projection and rigid transform helpers; no ROS dependency."""

import math

import numpy as np


def _validate_finite_vector(values, expected_len, name):
    try:
        arr = [float(v) for v in values]
    except TypeError as exc:
        raise ValueError(f"{name} must be a sequence of {expected_len} finite numbers") from exc
    if len(arr) != expected_len or not all(math.isfinite(v) for v in arr):
        raise ValueError(f"{name} must contain {expected_len} finite numbers")
    return arr


def _invalid_result(reason, valid_ratio=0.0):
    return {
        "valid": False,
        "xyz_cam": None,
        "valid_ratio": float(valid_ratio),
        "spread": None,
        "n": 0,
        "z_ref": None,
        "reason": reason,
    }


def region_point(
    depth,
    bbox,
    fx,
    fy,
    cx,
    cy,
    inner=0.6,
    band=0.15,
    min_valid_ratio=0.2,
    z_min=0.1,
    z_max=10.0,
):
    """Estimate a target surface point in camera optical frame from a bbox and metric depth."""
    depth_arr = np.asarray(depth, dtype=np.float64)
    if depth_arr.ndim != 2 or depth_arr.size == 0:
        raise ValueError("depth must be a non-empty 2D array")

    intrinsics = (fx, fy, cx, cy)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in intrinsics) or fx <= 0 or fy <= 0:
        raise ValueError("fx, fy, cx, cy must be finite with fx > 0 and fy > 0")
    if not (math.isfinite(inner) and 0.0 < inner <= 1.0):
        raise ValueError("inner must be in (0, 1]")
    if not (math.isfinite(band) and band >= 0.0):
        raise ValueError("band must be finite and >= 0")
    if not (math.isfinite(min_valid_ratio) and 0.0 < min_valid_ratio <= 1.0):
        raise ValueError("min_valid_ratio must be in (0, 1]")
    if not (math.isfinite(z_min) and math.isfinite(z_max) and 0.0 < z_min <= z_max):
        raise ValueError("z_min and z_max must be finite with 0 < z_min <= z_max")

    x0, y0, x1, y1 = _validate_finite_vector(bbox, 4, "bbox")
    if x1 <= x0 or y1 <= y0:
        return _invalid_result("empty_bbox")

    height, width = depth_arr.shape
    bx0 = max(0.0, min(float(width), x0))
    by0 = max(0.0, min(float(height), y0))
    bx1 = max(0.0, min(float(width), x1))
    by1 = max(0.0, min(float(height), y1))
    if bx1 <= bx0 or by1 <= by0:
        return _invalid_result("bbox_outside_image")

    ux = 0.5 * (bx0 + bx1)
    vy = 0.5 * (by0 + by1)
    hw = 0.5 * inner * (bx1 - bx0)
    hh = 0.5 * inner * (by1 - by0)
    ix0 = max(0, int(math.floor(ux - hw)))
    iy0 = max(0, int(math.floor(vy - hh)))
    ix1 = min(width, int(math.ceil(ux + hw)))
    iy1 = min(height, int(math.ceil(vy + hh)))
    if ix1 <= ix0 or iy1 <= iy0:
        return _invalid_result("empty_region")

    patch = depth_arr[iy0:iy1, ix0:ix1]
    valid_mask = np.isfinite(patch) & (patch >= z_min) & (patch <= z_max)
    valid_count = int(np.count_nonzero(valid_mask))
    valid_ratio = float(valid_count / patch.size)
    if valid_count == 0:
        return _invalid_result("no_valid_depth", valid_ratio=0.0)
    if valid_ratio < min_valid_ratio:
        return _invalid_result("insufficient_valid_depth", valid_ratio=valid_ratio)

    # Pick an actual depth element at the 20th percentile so sparse near noise
    # and background pixels behind (z_ref + band) are both excluded.
    sorted_z = np.sort(patch[valid_mask])
    ref_index = int(math.floor(0.20 * (sorted_z.size - 1)))
    z_ref = float(sorted_z[ref_index])
    fg_mask = valid_mask & (patch >= z_ref) & (patch <= z_ref + band)

    rel_v, rel_u = np.nonzero(fg_mask)
    u = rel_u.astype(np.float64) + ix0
    v = rel_v.astype(np.float64) + iy0
    z = patch[fg_mask]
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    points = np.column_stack((x, y, z))
    center = points.mean(axis=0)
    deltas = points - center
    spread = float(np.sqrt(np.mean(np.sum(deltas * deltas, axis=1))))
    return {
        "valid": True,
        "xyz_cam": [float(center[0]), float(center[1]), float(center[2])],
        "valid_ratio": valid_ratio,
        "spread": spread,
        "n": int(z.size),
        "z_ref": z_ref,
        "reason": None,
    }


def quat_to_matrix(quaternion):
    """Convert an xyzw quaternion into a 3x3 rotation matrix."""
    qx, qy, qz, qw = _validate_finite_vector(quaternion, 4, "quaternion")
    norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    if norm <= 1e-12:
        raise ValueError("quaternion must have positive norm")
    qx /= norm
    qy /= norm
    qz /= norm
    qw /= norm

    xx = qx * qx
    yy = qy * qy
    zz = qz * qz
    xy = qx * qy
    xz = qx * qz
    yz = qy * qz
    wx = qw * qx
    wy = qw * qy
    wz = qw * qz

    return np.array(
        [
            [1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)],
            [2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)],
            [2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)],
        ],
        dtype=np.float64,
    )


def transform_point(translation, quaternion, p):
    """Apply a rigid transform (translation + xyzw quaternion) to a 3D point."""
    tx, ty, tz = _validate_finite_vector(translation, 3, "translation")
    px, py, pz = _validate_finite_vector(p, 3, "p")
    rot = quat_to_matrix(quaternion)
    transformed = rot @ np.array([px, py, pz], dtype=np.float64) + np.array([tx, ty, tz], dtype=np.float64)
    return [float(transformed[0]), float(transformed[1]), float(transformed[2])]
