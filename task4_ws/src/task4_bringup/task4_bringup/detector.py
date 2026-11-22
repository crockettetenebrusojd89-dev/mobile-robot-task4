"""Detector backends for object_locator (scene chair HSV baseline and optional YOLOv8)."""

import math
from pathlib import Path

import cv2
import numpy as np


HSV_LOWER = (6, 100, 55)
HSV_UPPER = (14, 255, 255)
CLOSE_KERNEL_WH = (3, 11)
MIN_COLOR_PIXELS = 85
MIN_WIDTH = 10
MIN_HEIGHT = 12


class HsvChairDetector:
    """Color-based chair detector calibrated on task4_home simulated chairs."""

    def __init__(self, allowed_classes=("chair",)):
        self.allowed_classes = set(allowed_classes)
        self._kernel = cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE_KERNEL_WH)

    def predict(self, image_bgr):
        if "chair" not in self.allowed_classes:
            return []
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        material = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
        joined = cv2.morphologyEx(material, cv2.MORPH_CLOSE, self._kernel)
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(joined)
        color_counts = np.bincount(labels[material != 0], minlength=component_count)

        detections = []
        for label, (x, y, width, height, _) in enumerate(stats[1:], start=1):
            if width < MIN_WIDTH or height < MIN_HEIGHT or color_counts[label] < MIN_COLOR_PIXELS:
                continue
            detections.append({
                "class": "chair",
                "conf": None,
                "bbox": [int(x), int(y), int(x + width), int(y + height)],
            })
        return detections


class YoloDetector:
    """Optional YOLOv8 CPU detector loaded lazily when backend='yolov8'."""

    def __init__(self, weights_path, allowed_classes=("chair",), conf=0.25, imgsz=640):
        weights = Path(weights_path)
        if not weights_path or not weights.is_file():
            raise FileNotFoundError(f"YOLO weights not found: {weights_path}")
        if not (0.0 < conf <= 1.0):
            raise ValueError("conf must be in (0, 1]")
        if imgsz < 32 or imgsz % 32 != 0:
            raise ValueError("imgsz must be a positive multiple of 32")

        import ultralytics

        self.model = ultralytics.YOLO(str(weights.resolve()), task="detect")
        allowed = set(allowed_classes)
        self.class_ids = [
            int(cid) for cid, name in self.model.names.items() if name in allowed
        ]
        if not self.class_ids:
            raise ValueError(f"None of {sorted(allowed)} exist in model names")
        self.options = dict(
            conf=float(conf),
            imgsz=int(imgsz),
            classes=self.class_ids,
            device="cpu",
            verbose=False,
            save=False,
        )

    def predict(self, image_bgr):
        result = self.model.predict(source=image_bgr, **self.options)[0]
        detections = []
        for xyxy, confidence, class_id in zip(
            result.boxes.xyxy.tolist(),
            result.boxes.conf.tolist(),
            result.boxes.cls.tolist(),
        ):
            if not all(math.isfinite(value) for value in (*xyxy, confidence, class_id)):
                raise ValueError("Non-finite YOLO detection output")
            detections.append({
                "class": str(result.names[int(class_id)]),
                "conf": float(confidence),
                "bbox": [float(v) for v in xyxy],
            })
        return detections


def create_detector(backend="hsv", classes=("chair",), conf=0.25, weights_path="", imgsz=640):
    """Instantiate the configured detector backend."""
    normalized = str(backend).strip().lower()
    if normalized == "hsv":
        return HsvChairDetector(allowed_classes=classes)
    if normalized == "yolov8":
        return YoloDetector(
            weights_path=weights_path,
            allowed_classes=classes,
            conf=conf,
            imgsz=imgsz,
        )
    raise ValueError(f"Unsupported detector backend: {backend}")
