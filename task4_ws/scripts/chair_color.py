"""Detect the distinctive brown chair material in the Task 4 home scene."""

import cv2
import numpy as np


HSV_LOWER = (6, 100, 55)
HSV_UPPER = (14, 255, 255)
CLOSE_KERNEL_WH = (3, 11)
MIN_COLOR_PIXELS = 85
MIN_WIDTH = 10
MIN_HEIGHT = 12


def detect_scene_chairs(image_bgr):
    """Return original-image boxes for connected patches of chair material."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    material = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE_KERNEL_WH)
    joined = cv2.morphologyEx(material, cv2.MORPH_CLOSE, kernel)
    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(joined)
    color_counts = np.bincount(labels[material != 0], minlength=component_count)

    boxes = []
    for label, (x, y, width, height, _) in enumerate(stats[1:], start=1):
        if width < MIN_WIDTH or height < MIN_HEIGHT or color_counts[label] < MIN_COLOR_PIXELS:
            continue
        boxes.append({
            "xyxy": [int(x), int(y), int(x + width), int(y + height)],
            "class_id": 56,
            "class_name": "chair",
            "confidence": None,
            "color_pixels": int(color_counts[label]),
        })
    return boxes
