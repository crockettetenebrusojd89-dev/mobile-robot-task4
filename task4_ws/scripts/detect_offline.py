#!/usr/bin/env python3
"""Run a local detector on recorded RGB frames and save boxes and timings."""

import argparse
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from chair_color import (CLOSE_KERNEL_WH, HSV_LOWER, HSV_UPPER, MIN_COLOR_PIXELS,
                         MIN_HEIGHT, MIN_WIDTH, detect_scene_chairs)


def frame_metadata(path, image):
    metadata = path.with_suffix(".json")
    if not metadata.is_file():
        return None
    rgb = json.loads(metadata.read_text(encoding="utf-8"))["rgb"]
    if (rgb["height"], rgb["width"]) != image.shape[:2]:
        raise ValueError(f"RGB metadata does not match {path}")
    return {
        "frame_id": rgb["frame_id"],
        "stamp_ns": rgb["stamp_sec"] * 1_000_000_000 + rgb["stamp_nanosec"],
    }


def read_image(path):
    # Decoding a byte buffer also supports Chinese paths on OpenCV builds
    # whose imread filename handling follows the platform locale.
    image = cv2.imdecode(np.frombuffer(path.read_bytes(), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unreadable image: {path}")
    return image


def draw_boxes(image, boxes):
    height, width = image.shape[:2]
    for box in boxes:
        left, top, right, bottom = map(round, box["xyxy"])
        bottom, right = min(bottom, height - 1), min(right, width - 1)
        color = (65, 211, 30)
        cv2.rectangle(image, (left, top), (right, bottom), color, 2)
        confidence = box["confidence"]
        label = box["class_name"] if confidence is None else f'{box["class_name"]} {confidence:.2f}'
        (text_width, text_height), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
        label_top = max(0, top - text_height - 6)
        cv2.rectangle(image, (left, label_top), (left + text_width + 4, label_top + text_height + 5),
                      color, cv2.FILLED)
        cv2.putText(image, label, (left + 2, label_top + text_height + 1),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (17, 28, 16), 1, cv2.LINE_AA)


def prepare_yolo(args, parser):
    import torch
    import ultralytics

    conf = args.conf if args.conf is not None else 0.25
    imgsz = args.imgsz if args.imgsz is not None else 640
    classes = args.classes if args.classes is not None else [56]
    torch.set_num_threads(args.threads)
    model = ultralytics.YOLO(str(args.weights.resolve()), task="detect")
    if any(class_id not in model.names for class_id in classes):
        parser.error("Requested class ID does not exist in this model.")
    options = dict(conf=conf, imgsz=imgsz, classes=classes,
                   device="cpu", verbose=False, save=False)

    def predict(image):
        result = model.predict(source=image, **options)[0]
        boxes = []
        for xyxy, confidence, class_id in zip(
            result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()
        ):
            if not all(math.isfinite(value) for value in (*xyxy, confidence, class_id)):
                raise ValueError("Nonfinite detector result")
            class_id = int(class_id)
            boxes.append({"xyxy": xyxy, "confidence": confidence, "class_id": class_id,
                          "class_name": result.names[class_id]})
        return boxes

    return predict, {
        "weights": args.weights.name,
        "weights_sha256": hashlib.sha256(args.weights.read_bytes()).hexdigest(),
        "ultralytics_version": ultralytics.__version__,
        "torch_version": torch.__version__,
        "confidence_threshold": conf,
        "image_size": imgsz,
        "classes": {class_id: model.names[class_id] for class_id in classes},
        "timing_scope": "PNG read and decode, model preprocessing, inference, NMS and box extraction after warmup",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True, help="Directory of recorded PNG frames")
    parser.add_argument("--backend", choices=("yolov8", "hsv"), default="yolov8")
    parser.add_argument("--weights", type=Path, help="Existing local YOLO weights")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--conf", type=float, help="YOLO confidence threshold (default: 0.25)")
    parser.add_argument("--imgsz", type=int, help="YOLO input size (default: 640)")
    parser.add_argument("--classes", nargs="+", type=int,
                        help="YOLO COCO IDs (chair=56 by default, bottle=39, cup=41)")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("Use threads >= 1.")
    paths = sorted(args.frames.glob("frame_*.png"))
    if not paths:
        parser.error("No frame_*.png images found.")

    cv2.setNumThreads(args.threads)
    if args.backend == "yolov8":
        if args.weights is None or not args.weights.is_file():
            parser.error("Provide a local YOLO weights file.")
        if args.conf is not None and not 0 < args.conf <= 1:
            parser.error("Use 0 < conf <= 1.")
        if args.imgsz is not None and (args.imgsz < 32 or args.imgsz % 32 != 0):
            parser.error("Use a positive multiple of 32 for imgsz.")
        predict, detector = prepare_yolo(args, parser)
    else:
        if any(value is not None for value in (args.weights, args.conf, args.imgsz, args.classes)):
            parser.error("Weights, confidence, input size and class filtering apply to YOLO.")
        predict = detect_scene_chairs
        detector = {
            "confidence_threshold": None,
            "classes": {56: "chair"},
            "hsv_lower": HSV_LOWER, "hsv_upper": HSV_UPPER,
            "close_kernel_wh": CLOSE_KERNEL_WH,
            "min_color_pixels": MIN_COLOR_PIXELS,
            "min_width": MIN_WIDTH, "min_height": MIN_HEIGHT,
            "timing_scope": "PNG read and decode, HSV mask, closing and connected components after warmup",
        }
    predict(read_image(paths[0]))  # Warm up before timing.

    output_images = args.out / "images"
    output_images.mkdir(parents=True, exist_ok=True)
    results = []
    for path in paths:
        started = perf_counter()
        image = read_image(path)
        boxes = predict(image)
        elapsed_ms = (perf_counter() - started) * 1_000
        metadata = frame_metadata(path, image)
        draw_boxes(image, boxes)
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise OSError(f"Could not encode overlay for {path}")
        (output_images / path.name).write_bytes(encoded.tobytes())
        results.append({
            "image": path.name, "observation": metadata,
            "elapsed_ms": elapsed_ms, "detections": boxes,
        })

    elapsed = [result["elapsed_ms"] for result in results]
    report = {
        "backend": args.backend,
        **detector,
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "device": "cpu",
        "threads": args.threads,
        "frame_count": len(results),
        "latency_ms": {"median": float(np.median(elapsed)), "p95": float(np.percentile(elapsed, 95)),
                       "max": max(elapsed)},
        "frames": results,
    }
    (args.out / "detections.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8",
    )
    print(f"{len(results)} frames, {sum(len(row['detections']) for row in results)} detections, "
          f"median {report['latency_ms']['median']:.1f} ms, p95 {report['latency_ms']['p95']:.1f} ms")


if __name__ == "__main__":
    main()
