"""Online RGB-D object_locator node converting 2D detections to map/odom 3D observations."""

from dataclasses import dataclass
import json
import math
import threading
import time

import cv2
import numpy as np

from task4_bringup.detector import create_detector
from task4_bringup.geometry3d import region_point, transform_point


def stamp_to_seconds(stamp):
    return float(stamp.sec) + float(stamp.nanosec) / 1_000_000_000.0


def decode_color_bgr(msg):
    """Decode rgb8/bgr8 Image message into a BGR numpy uint8 array."""
    encoding = str(msg.encoding).lower()
    width, height, step = int(msg.width), int(msg.height), int(msg.step)
    if encoding not in ("rgb8", "bgr8"):
        raise ValueError(f"unsupported_color_encoding:{msg.encoding}")
    if width <= 0 or height <= 0 or step < 3 * width:
        raise ValueError("invalid_color_dimensions_or_stride")
    payload = bytes(msg.data)
    if len(payload) < height * step:
        raise ValueError("truncated_color_payload")
    pixels = np.ndarray(
        (height, width, 3), dtype=np.uint8, buffer=payload, strides=(step, 3, 1)
    )
    if encoding == "rgb8":
        return cv2.cvtColor(pixels, cv2.COLOR_RGB2BGR)
    return pixels.copy()


def decode_depth_meters(msg):
    """Decode 32FC1 (meters) or 16UC1 (millimeters) depth Image into float64 meters."""
    width, height, step = int(msg.width), int(msg.height), int(msg.step)
    encoding = str(msg.encoding).upper()
    if encoding not in ("32FC1", "16UC1"):
        raise ValueError(f"unsupported_depth_encoding:{msg.encoding}")
    dtype = np.dtype((">" if msg.is_bigendian else "<") + ("f4" if encoding == "32FC1" else "u2"))
    if width <= 0 or height <= 0 or step < width * dtype.itemsize:
        raise ValueError("invalid_depth_dimensions_or_stride")
    payload = bytes(msg.data)
    if len(payload) < step * height:
        raise ValueError("truncated_depth_payload")
    pixels = np.ndarray(
        (height, width), dtype=dtype, buffer=payload, strides=(step, dtype.itemsize)
    )
    meters = pixels.astype(np.float64)
    if encoding == "16UC1":
        meters *= 0.001
    return meters


def parse_camera_info(msg):
    """Validate CameraInfo intrinsics and return a compact calibration dict."""
    width, height = int(msg.width), int(msg.height)
    frame_id = str(msg.header.frame_id).strip()
    if width <= 0 or height <= 0 or not frame_id:
        raise ValueError("invalid_camera_info_header_or_size")
    k = [float(v) for v in msg.k]
    if len(k) != 9 or not all(math.isfinite(v) for v in k):
        raise ValueError("invalid_camera_info_k")
    fx, fy, cx, cy = k[0], k[4], k[2], k[5]
    if fx <= 0.0 or fy <= 0.0:
        raise ValueError("non_positive_focal_length")
    return {
        "width": width,
        "height": height,
        "frame_id": frame_id,
        "fx": fx,
        "fy": fy,
        "cx": cx,
        "cy": cy,
    }


@dataclass(frozen=True)
class LocatorConfig:
    map_frame: str = "map"
    inner_ratio: float = 0.6
    depth_band_m: float = 0.15
    min_valid_ratio: float = 0.2
    z_min_m: float = 0.1
    z_max_m: float = 10.0


def draw_debug_overlay(image_bgr, detections):
    """Draw 2D detection boxes and localization status on a copy of the RGB frame."""
    canvas = image_bgr.copy()
    height, width = canvas.shape[:2]
    for det in detections:
        left, top, right, bottom = [int(round(v)) for v in det["bbox"]]
        left = max(0, min(width - 1, left))
        right = max(0, min(width - 1, right))
        top = max(0, min(height - 1, top))
        bottom = max(0, min(height - 1, bottom))
        color = (65, 211, 30) if det["valid"] else (0, 140, 255)
        cv2.rectangle(canvas, (left, top), (right, bottom), color, 2)
        if det["valid"] and det["xyz_map"] is not None:
            x, y, _ = det["xyz_map"]
            label = f"{det['class']} ({x:.2f},{y:.2f})"
        else:
            label = f"{det['class']} [{det['reason']}]"
        cv2.putText(
            canvas,
            label,
            (left, max(12, top - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            color,
            1,
            cv2.LINE_AA,
        )
    return canvas


class ObjectLocatorCore:
    """ROS-independent frame processor combining detector, region_point, and TF lookup."""

    def __init__(self, detector, tf_lookup, config=None):
        self.detector = detector
        self.tf_lookup = tf_lookup
        self.config = config or LocatorConfig()

    def process_frame(self, rgb_msg, depth_msg, camera_info):
        """Process one synced (rgb, depth) frame and return (observation_dict, debug_bgr_or_None)."""
        stamp_s = stamp_to_seconds(rgb_msg.header.stamp)
        camera_frame = str(rgb_msg.header.frame_id).strip()
        depth_frame = str(depth_msg.header.frame_id).strip()

        base_obs = {
            "stamp": stamp_s,
            "frame_id": self.config.map_frame,
            "camera_frame": camera_frame,
            "valid_frame": False,
            "reason": None,
            "detections": [],
        }

        if not camera_frame or camera_frame != depth_frame:
            base_obs["reason"] = "mismatched_or_empty_camera_frame"
            return base_obs, None
        if camera_info is None:
            base_obs["reason"] = "missing_camera_info"
            return base_obs, None
        if (
            int(rgb_msg.width) != int(depth_msg.width)
            or int(rgb_msg.height) != int(depth_msg.height)
            or int(rgb_msg.width) != camera_info["width"]
            or int(rgb_msg.height) != camera_info["height"]
        ):
            base_obs["reason"] = "image_camera_info_size_mismatch"
            return base_obs, None
        if camera_info["frame_id"] != camera_frame:
            base_obs["reason"] = "camera_info_frame_mismatch"
            return base_obs, None

        try:
            image_bgr = decode_color_bgr(rgb_msg)
            depth_m = decode_depth_meters(depth_msg)
        except ValueError as exc:
            base_obs["reason"] = f"decode_failed:{exc}"
            return base_obs, None

        # Verify at least one finite in-range depth pixel exists so a stalled/blank
        # depth frame cannot masquerade as a valid empty observation.
        valid_depth_pixels = np.isfinite(depth_m) & (depth_m >= self.config.z_min_m) & (depth_m <= self.config.z_max_m)
        if not bool(np.any(valid_depth_pixels)):
            base_obs["reason"] = "no_valid_depth_in_frame"
            return base_obs, image_bgr

        try:
            raw_detections = self.detector.predict(image_bgr)
        except Exception as exc:
            base_obs["reason"] = f"inference_failed:{exc}"
            return base_obs, image_bgr

        try:
            translation, quaternion = self.tf_lookup(
                self.config.map_frame, camera_frame, rgb_msg.header.stamp
            )
            tf_error = None
        except Exception as exc:
            translation, quaternion = None, None
            tf_error = f"tf_lookup_failed:{exc}"

        detections = []
        for det in raw_detections:
            geom = region_point(
                depth_m,
                det["bbox"],
                camera_info["fx"],
                camera_info["fy"],
                camera_info["cx"],
                camera_info["cy"],
                inner=self.config.inner_ratio,
                band=self.config.depth_band_m,
                min_valid_ratio=self.config.min_valid_ratio,
                z_min=self.config.z_min_m,
                z_max=self.config.z_max_m,
            )
            if not geom["valid"]:
                detections.append({
                    "class": det["class"],
                    "conf": det["conf"],
                    "bbox": [float(v) for v in det["bbox"]],
                    "xyz_map": None,
                    "xyz_cam": None,
                    "valid_ratio": geom["valid_ratio"],
                    "spread": geom["spread"],
                    "valid": False,
                    "reason": geom["reason"],
                })
                continue

            if tf_error is not None:
                detections.append({
                    "class": det["class"],
                    "conf": det["conf"],
                    "bbox": [float(v) for v in det["bbox"]],
                    "xyz_map": None,
                    "xyz_cam": geom["xyz_cam"],
                    "valid_ratio": geom["valid_ratio"],
                    "spread": geom["spread"],
                    "valid": False,
                    "reason": tf_error,
                })
                continue

            xyz_map = transform_point(translation, quaternion, geom["xyz_cam"])
            detections.append({
                "class": det["class"],
                "conf": det["conf"],
                "bbox": [float(v) for v in det["bbox"]],
                "xyz_map": xyz_map,
                "xyz_cam": geom["xyz_cam"],
                "valid_ratio": geom["valid_ratio"],
                "spread": geom["spread"],
                "valid": True,
                "reason": None,
            })

        base_obs["detections"] = detections
        if tf_error is not None:
            base_obs["valid_frame"] = False
            base_obs["reason"] = tf_error
        else:
            base_obs["valid_frame"] = True
            base_obs["reason"] = None
        return base_obs, image_bgr


def _build_ros_node_class():
    import message_filters
    from rclpy.duration import Duration
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from rclpy.time import Time
    from sensor_msgs.msg import CameraInfo, Image
    from std_msgs.msg import String
    from tf2_ros import Buffer, TransformException, TransformListener

    class ObjectLocatorNode(Node):
        """ROS 2 wrapper synchronizing RGB-D frames and publishing 3D observations."""

        def __init__(self):
            super().__init__("object_locator")
            self.declare_parameter("rgb_topic", "/oakd/rgb/preview/image_raw")
            self.declare_parameter("depth_topic", "/oakd/rgb/preview/depth")
            self.declare_parameter("camera_info_topic", "/oakd/rgb/preview/camera_info")
            self.declare_parameter("observations_topic", "/task4/observations")
            self.declare_parameter("status_topic", "/task4/perception_status")
            self.declare_parameter("debug_image_topic", "/task4/debug_image")
            self.declare_parameter("publish_debug_image", True)
            self.declare_parameter("map_frame", "map")
            self.declare_parameter("detector_backend", "hsv")
            self.declare_parameter("classes", ["chair"])
            self.declare_parameter("conf", 0.25)
            self.declare_parameter("imgsz", 640)
            self.declare_parameter("weights_path", "")
            self.declare_parameter("max_rate_hz", 5.0)
            self.declare_parameter("sync_queue_size", 5)
            self.declare_parameter("sync_slop_sec", 0.02)
            self.declare_parameter("tf_timeout_sec", 0.2)
            self.declare_parameter("stale_timeout_sec", 2.0)
            self.declare_parameter("inner_ratio", 0.6)
            self.declare_parameter("depth_band_m", 0.15)
            self.declare_parameter("min_valid_ratio", 0.2)
            self.declare_parameter("z_min_m", 0.1)
            self.declare_parameter("z_max_m", 10.0)

            rgb_topic = self.get_parameter("rgb_topic").value
            depth_topic = self.get_parameter("depth_topic").value
            info_topic = self.get_parameter("camera_info_topic").value
            obs_topic = self.get_parameter("observations_topic").value
            status_topic = self.get_parameter("status_topic").value
            debug_topic = self.get_parameter("debug_image_topic").value
            self.publish_debug_image = bool(self.get_parameter("publish_debug_image").value)

            self.map_frame = str(self.get_parameter("map_frame").value)
            backend = str(self.get_parameter("detector_backend").value)
            classes = list(self.get_parameter("classes").value)
            conf = float(self.get_parameter("conf").value)
            imgsz = int(self.get_parameter("imgsz").value)
            weights_path = str(self.get_parameter("weights_path").value)
            max_rate_hz = float(self.get_parameter("max_rate_hz").value)
            if max_rate_hz <= 0.0:
                raise ValueError("max_rate_hz must be positive")
            self.min_period_sec = 1.0 / max_rate_hz
            sync_queue_size = int(self.get_parameter("sync_queue_size").value)
            sync_slop_sec = float(self.get_parameter("sync_slop_sec").value)
            self.tf_timeout_sec = float(self.get_parameter("tf_timeout_sec").value)
            self.stale_timeout_sec = float(self.get_parameter("stale_timeout_sec").value)

            config = LocatorConfig(
                map_frame=self.map_frame,
                inner_ratio=float(self.get_parameter("inner_ratio").value),
                depth_band_m=float(self.get_parameter("depth_band_m").value),
                min_valid_ratio=float(self.get_parameter("min_valid_ratio").value),
                z_min_m=float(self.get_parameter("z_min_m").value),
                z_max_m=float(self.get_parameter("z_max_m").value),
            )
            detector = create_detector(
                backend=backend,
                classes=classes,
                conf=conf,
                weights_path=weights_path,
                imgsz=imgsz,
            )
            self.detector_backend = backend

            self.tf_buffer = Buffer()
            self.tf_listener = TransformListener(self.tf_buffer, self, spin_thread=False)
            self.core = ObjectLocatorCore(detector, self._lookup_tf_bounded, config=config)

            self.obs_pub = self.create_publisher(String, obs_topic, 10)
            self.status_pub = self.create_publisher(String, status_topic, 10)
            self.debug_pub = (
                self.create_publisher(Image, debug_topic, qos_profile_sensor_data)
                if self.publish_debug_image
                else None
            )

            self._lock = threading.Lock()
            self._cond = threading.Condition(self._lock)
            self._stop = False
            self._camera_info = None
            self._pending = None
            self._last_rx_stamp_s = None
            self._last_rx_wall = None
            self._last_infer_wall = -float("inf")
            self._processed_frames = 0
            self._valid_frames = 0
            self._dropped_frames = 0
            self._last_valid_stamp_s = None
            self._last_error = None
            self._epoch = 0

            self.info_sub = self.create_subscription(
                CameraInfo, info_topic, self._on_camera_info, qos_profile_sensor_data
            )
            self.rgb_sub = message_filters.Subscriber(
                self, Image, rgb_topic, qos_profile=qos_profile_sensor_data
            )
            self.depth_sub = message_filters.Subscriber(
                self, Image, depth_topic, qos_profile=qos_profile_sensor_data
            )
            self.sync = message_filters.ApproximateTimeSynchronizer(
                [self.rgb_sub, self.depth_sub],
                queue_size=sync_queue_size,
                slop=sync_slop_sec,
            )
            self.sync.registerCallback(self._on_rgbd)

            self.status_timer = self.create_timer(1.0, self._publish_status)
            self._worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._worker.start()

            self.get_logger().info(
                f"object_locator started: backend={backend}, map_frame={self.map_frame}, "
                f"max_rate_hz={max_rate_hz}"
            )

        def _lookup_tf_bounded(self, target_frame, source_frame, stamp_msg):
            query_time = Time.from_msg(stamp_msg)
            deadline = time.monotonic() + self.tf_timeout_sec
            with self._lock:
                start_epoch = self._epoch
            while not self.tf_buffer.can_transform(
                target_frame, source_frame, query_time, timeout=Duration(seconds=0.0)
            ):
                with self._lock:
                    if self._stop or self._epoch != start_epoch:
                        raise RuntimeError("sim_reset_or_shutdown_during_tf_wait")
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.01)
            try:
                tf = self.tf_buffer.lookup_transform(
                    target_frame, source_frame, query_time, timeout=Duration(seconds=0.0)
                )
            except TransformException as exc:
                raise RuntimeError(str(exc)) from exc
            t = tf.transform.translation
            q = tf.transform.rotation
            return [float(t.x), float(t.y), float(t.z)], [float(q.x), float(q.y), float(q.z), float(q.w)]

        def _on_camera_info(self, msg):
            try:
                parsed = parse_camera_info(msg)
            except ValueError as exc:
                with self._lock:
                    self._last_error = str(exc)
                return
            with self._lock:
                self._camera_info = parsed

        def _on_rgbd(self, rgb_msg, depth_msg):
            stamp_s = stamp_to_seconds(rgb_msg.header.stamp)
            now_wall = time.monotonic()
            with self._lock:
                if self._last_rx_stamp_s is not None and stamp_s + 0.5 < self._last_rx_stamp_s:
                    # Simulation time jumped backward: discard stale pending frame and reset TF buffer.
                    self._pending = None
                    self._camera_info = None
                    self._last_infer_wall = -float("inf")
                    self._epoch += 1
                    self.tf_buffer.clear()
                    self._last_error = "sim_time_reset_detected"
                    self.get_logger().warning("Simulation time reset detected; clearing cached frames and TF buffer.")
                elif self._pending is not None:
                    self._dropped_frames += 1

                self._last_rx_stamp_s = stamp_s
                self._last_rx_wall = now_wall
                self._pending = (rgb_msg, depth_msg, self._camera_info, self._epoch)
                self._cond.notify()

        def _worker_loop(self):
            while True:
                with self._lock:
                    while self._pending is None and not self._stop:
                        self._cond.wait(timeout=0.5)
                    if self._stop:
                        return
                    wait_sec = self.min_period_sec - (time.monotonic() - self._last_infer_wall)
                    if wait_sec > 0.0:
                        self._cond.wait(timeout=wait_sec)
                        if self._stop:
                            return
                        if self._pending is None:
                            continue
                    if time.monotonic() - self._last_infer_wall < self.min_period_sec:
                        continue
                    rgb_msg, depth_msg, camera_info, item_epoch = self._pending
                    self._pending = None
                    self._last_infer_wall = time.monotonic()

                obs, image_bgr = self.core.process_frame(rgb_msg, depth_msg, camera_info)

                with self._lock:
                    if item_epoch != self._epoch:
                        continue
                    self._processed_frames += 1
                    if obs["valid_frame"]:
                        self._valid_frames += 1
                        self._last_valid_stamp_s = obs["stamp"]
                        self._last_error = None
                    else:
                        self._last_error = obs.get("reason")

                out_msg = String()
                out_msg.data = json.dumps(obs, ensure_ascii=False, allow_nan=False)
                self.obs_pub.publish(out_msg)

                if self.debug_pub is not None and image_bgr is not None:
                    overlay = draw_debug_overlay(image_bgr, obs["detections"])
                    dbg = Image()
                    dbg.header = rgb_msg.header
                    dbg.height, dbg.width = overlay.shape[:2]
                    dbg.encoding = "bgr8"
                    dbg.is_bigendian = 0
                    dbg.step = int(overlay.shape[1] * 3)
                    dbg.data = overlay.tobytes()
                    self.debug_pub.publish(dbg)

        def _publish_status(self):
            now_wall = time.monotonic()
            with self._lock:
                stale = (
                    self._last_rx_wall is None
                    or (now_wall - self._last_rx_wall) > self.stale_timeout_sec
                )
                error = self._last_error
                if stale and self._last_rx_wall is not None and error is None:
                    error = "input_stream_stale"
                payload = {
                    "processed_frames": self._processed_frames,
                    "valid_frames": self._valid_frames,
                    "dropped_frames": self._dropped_frames,
                    "last_valid_stamp": self._last_valid_stamp_s,
                    "last_rx_stamp": self._last_rx_stamp_s,
                    "stale": stale,
                    "last_error": error,
                    "detector_backend": self.detector_backend,
                    "target_frame": self.map_frame,
                }
            msg = String()
            msg.data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            self.status_pub.publish(msg)

        def shutdown_worker(self):
            with self._lock:
                self._stop = True
                self._cond.notify_all()
            if self._worker.is_alive():
                self._worker.join(timeout=2.0)

    return ObjectLocatorNode


def main(args=None):
    import rclpy
    from rclpy.executors import ExternalShutdownException

    ObjectLocatorNode = _build_ros_node_class()
    rclpy.init(args=args)
    node = None
    try:
        node = ObjectLocatorNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.shutdown_worker()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
