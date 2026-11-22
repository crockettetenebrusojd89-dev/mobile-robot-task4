"""Search manager state machine node orchestrating room navigation, dwell observation, and counting."""

import json
import math
from pathlib import Path
import time

import yaml

from task4_bringup.association import Inventory
from task4_bringup.result_io import save_run_results
from task4_bringup.search_status import decide_status, format_terminal_summary


def flatten_viewpoints(room_cfg):
    """Expand room observation_points (x, y, yaws) into sequential (x, y, yaw) poses."""
    poses = []
    for pt_idx, pt in enumerate(room_cfg.get("observation_points", [])):
        x = float(pt["x"])
        y = float(pt["y"])
        for yaw_idx, yaw in enumerate(pt.get("yaws", [])):
            poses.append({
                "point_index": pt_idx,
                "yaw_index": yaw_idx,
                "x": x,
                "y": y,
                "yaw": float(yaw),
            })
    return poses


def resolve_workspace_path(path_value, fallback_pkg_rel):
    p = Path(path_value)
    if p.is_file():
        return p
    if not p.is_absolute():
        cwd_candidate = Path.cwd() / p
        if cwd_candidate.is_file():
            return cwd_candidate
    from ament_index_python.packages import get_package_share_directory

    pkg_candidate = Path(get_package_share_directory("task4_bringup")) / fallback_pkg_rel
    if pkg_candidate.is_file():
        return pkg_candidate
    return p


class SearchExecutor:
    """Testable task execution engine driving NavigationClient, dwell windows, and Inventory."""

    def __init__(
        self,
        *,
        rooms_cfg,
        objects_cfg,
        map_yaml_path,
        results_dir,
        nav_client_factory,
        spin_step,
        clock_now_sec,
        status_publisher=None,
        logger=None,
        params=None,
    ):
        self.rooms_cfg = rooms_cfg
        self.objects_cfg = objects_cfg
        self.map_yaml_path = Path(map_yaml_path)
        self.results_dir = Path(results_dir)
        self.nav_client_factory = nav_client_factory
        self.spin_step = spin_step
        self.clock_now_sec = clock_now_sec
        self.status_publisher = status_publisher or (lambda payload: None)
        self.logger = logger or (lambda msg: None)

        cfg = params or {}
        self.dwell_sec = float(cfg.get("dwell_sec", 2.0))
        self.settle_sec = float(cfg.get("settle_sec", 0.5))
        self.nav_timeout_sec = float(cfg.get("nav_timeout_sec", 90.0))
        self.max_retries = int(cfg.get("max_retries", 1))
        self.min_frames_per_dwell = int(cfg.get("min_frames_per_dwell", 3))
        self.gate_m = float(cfg.get("gate_m", 0.35))
        self.min_hits = int(cfg.get("min_hits", 3))
        self.room_margin_m = float(cfg.get("room_margin_m", 0.1))
        self.map_frame = str(cfg.get("map_frame", "map"))

        self._nav_client = None
        self._active_task = None
        self._cancel_requested = False
        self._cancel_target_id = None
        self._obs_window_active = False
        self._window_observations = []
        self._latest_perception_status = None
        self._nav_blocked = False

    def request_cancel(self, task_id=""):
        tid = str(task_id or "").strip()
        if self._active_task is None:
            return False
        if tid and tid != self._active_task.get("task_id"):
            return False
        self._cancel_requested = True
        self._cancel_target_id = self._active_task.get("task_id")
        if self._nav_client is not None:
            self._nav_client.cancel()
        return True

    def on_observation(self, obs):
        if self._obs_window_active:
            self._window_observations.append(obs)

    def on_perception_status(self, status_dict):
        self._latest_perception_status = status_dict

    def _emit_state(self, state, task_id=None, detail=None):
        self.status_publisher({
            "task_id": task_id,
            "state": state,
            "detail": detail,
            "stamp_wall": time.time(),
        })

    def _wait_sim_or_wall(self, duration_sec, max_wall_sec=None):
        if duration_sec <= 0:
            return
        max_wall = max_wall_sec if max_wall_sec is not None else max(duration_sec * 6.0, duration_sec + 5.0)
        start_wall = time.monotonic()
        start_sim = self.clock_now_sec()
        while time.monotonic() - start_wall < max_wall:
            if self._cancel_requested:
                return
            self.spin_step(0.05)
            cur_sim = self.clock_now_sec()
            if start_sim is not None and cur_sim is not None and cur_sim >= start_sim:
                if cur_sim - start_sim >= duration_sec:
                    return
            elif time.monotonic() - start_wall >= duration_sec:
                return

    def _navigate_with_retry(self, x, y, yaw):
        if self._nav_blocked:
            return None, False
        if self._nav_client is None:
            self._nav_client = self.nav_client_factory()

        attempts = 0
        last_res = None
        while attempts <= self.max_retries:
            if self._cancel_requested:
                break
            attempts += 1
            try:
                self._nav_client.start(x, y, yaw, timeout=self.nav_timeout_sec)
            except RuntimeError:
                self._nav_blocked = True
                return last_res, False

            while True:
                if self._cancel_requested:
                    self._nav_client.cancel()
                self.spin_step(0.05)
                res = self._nav_client.poll()
                if res is not None:
                    last_res = res
                    if res.goal_may_be_active:
                        self._nav_blocked = True
                        return res, False
                    if res.succeeded:
                        return res, True
                    if self._cancel_requested or res.outcome == "CANCELED":
                        return res, True
                    # Retry only when rejected or terminal failure confirmed (not blocked).
                    break
        return last_res, True

    def execute_task(self, task):
        """Run the full IDLE -> NAVIGATING -> SEARCHING -> SUMMARIZING lifecycle for one task."""
        task_id = str(task.get("task_id", "")).strip()
        room_key = str(task.get("room", "")).strip()
        obj_class = str(task.get("object_class", "")).strip()

        rooms = self.rooms_cfg.get("rooms", {})
        objects = self.objects_cfg.get("objects", {})
        if not task_id or room_key not in rooms or obj_class not in objects:
            err = f"invalid_task_config:room={room_key},object_class={obj_class}"
            self.logger(err)
            self._emit_state("FAILED", task_id=task_id, detail=err)
            return {"status": "FAILED", "reason": err}

        if self._nav_blocked:
            err = "previous_navigation_goal_unconfirmed"
            self.logger(err)
            self._emit_state("FAILED", task_id=task_id, detail=err)
            return {"status": "FAILED", "reason": err}

        started_wall = time.monotonic()
        self._active_task = task
        self._cancel_requested = False
        self._cancel_target_id = None
        self._window_observations = []
        self._obs_window_active = False

        run_dir = self.results_dir / task_id
        log_lines = [f"task_received id={task_id} room={room_key} class={obj_class}"]

        room_cfg = rooms[room_key]
        inventory = Inventory(
            object_class=obj_class,
            room_polygon=room_cfg["boundary_polygon"],
            gate_m=self.gate_m,
            min_hits=self.min_hits,
            room_margin_m=self.room_margin_m,
        )

        # 1. NAVIGATING to room entrance
        self._emit_state("NAVIGATING", task_id=task_id, detail=f"entrance:{room_key}")
        ex, ey, eyaw = [float(v) for v in room_cfg["entrance_pose"]]
        entrance_res, entrance_confirmed = self._navigate_with_retry(ex, ey, eyaw)
        entrance_ok = bool(entrance_res is not None and entrance_res.succeeded)
        cancel_confirmed = entrance_confirmed
        ent_msg = f"entrance outcome={getattr(entrance_res, 'outcome', None)} ok={entrance_ok} confirmed={entrance_confirmed}"
        log_lines.append(ent_msg)
        self.logger(ent_msg)

        viewpoint_records = []
        perception_overall_ok = True

        # 2. SEARCHING planned viewpoints (never stops early on first detection)
        if entrance_ok and not self._cancel_requested:
            self._emit_state("SEARCHING", task_id=task_id, detail=f"room:{room_key}")
            planned = flatten_viewpoints(room_cfg)
            for idx, pose in enumerate(planned):
                if self._cancel_requested or self._nav_blocked:
                    break
                res, confirmed = self._navigate_with_retry(pose["x"], pose["y"], pose["yaw"])
                if not confirmed:
                    cancel_confirmed = False
                nav_ok = bool(res is not None and res.succeeded)
                vp_rec = {
                    "index": idx,
                    "point_index": pose["point_index"],
                    "yaw_index": pose["yaw_index"],
                    "target_pose": [pose["x"], pose["y"], pose["yaw"]],
                    "nav_succeeded": nav_ok,
                    "nav_outcome": getattr(res, "outcome", None),
                    "nav_reason": getattr(res, "reason", None),
                    "valid_frames": 0,
                    "empty_valid_frames": 0,
                    "invalid_frames": 0,
                    "perception_ok": True,
                }
                if self._cancel_requested or self._nav_blocked:
                    viewpoint_records.append(vp_rec)
                    break

                if nav_ok:
                    self._wait_sim_or_wall(self.settle_sec)
                    if self._cancel_requested:
                        viewpoint_records.append(vp_rec)
                        break

                    self._window_observations = []
                    window_start_sim = self.clock_now_sec()
                    self._obs_window_active = True
                    self._wait_sim_or_wall(self.dwell_sec)
                    self._obs_window_active = False

                    for obs in self._window_observations:
                        obs_stamp = obs.get("stamp")
                        if (
                            window_start_sim is not None
                            and obs_stamp is not None
                            and float(obs_stamp) < window_start_sim - 0.1
                        ):
                            continue
                        if obs.get("frame_id") != self.map_frame:
                            vp_rec["invalid_frames"] += 1
                            continue
                        if not obs.get("valid_frame", False):
                            vp_rec["invalid_frames"] += 1
                            continue
                        vp_rec["valid_frames"] += 1
                        if len(obs.get("detections", [])) == 0:
                            vp_rec["empty_valid_frames"] += 1
                        inventory.update(obs)

                    p_status = self._latest_perception_status
                    if p_status is not None and p_status.get("stale", False):
                        vp_rec["perception_ok"] = False
                        perception_overall_ok = False
                    if vp_rec["valid_frames"] < self.min_frames_per_dwell:
                        vp_rec["perception_ok"] = False
                        perception_overall_ok = False

                vp_msg = (
                    f"vp[{idx}] nav={vp_rec['nav_outcome']} valid={vp_rec['valid_frames']} "
                    f"invalid={vp_rec['invalid_frames']} count_now={inventory.count()}"
                )
                log_lines.append(vp_msg)
                self.logger(vp_msg)
                viewpoint_records.append(vp_rec)

        if self._latest_perception_status is not None and self._latest_perception_status.get("stale", False):
            perception_overall_ok = False

        # 3. SUMMARIZING: save & read-back verify first, then decide final status
        self._emit_state("SUMMARIZING", task_id=task_id)
        snapshot = inventory.snapshot()
        elapsed_s = time.monotonic() - started_wall

        prelim_status, prelim_reason = decide_status(
            viewpoint_records,
            perception_overall_ok,
            True,
            self._cancel_requested,
            entrance_ok=entrance_ok,
            cancel_confirmed=cancel_confirmed,
            min_frames_per_dwell=self.min_frames_per_dwell,
        )
        status_record = {
            "task_id": task_id,
            "status": prelim_status,
            "reason": prelim_reason,
            "elapsed_s": round(elapsed_s, 3),
            "count": snapshot["count"],
            "perception_ok": perception_overall_ok,
            "canceled": self._cancel_requested,
            "cancel_confirmed": cancel_confirmed,
        }

        verify_report = save_run_results(
            run_dir,
            task=task,
            inventory_snapshot=snapshot,
            viewpoints=viewpoint_records,
            status_record=status_record,
            map_yaml_path=self.map_yaml_path,
            log_lines=log_lines,
        )
        save_ok = bool(verify_report.get("ok", False))
        final_status, final_reason = decide_status(
            viewpoint_records,
            perception_overall_ok,
            save_ok,
            self._cancel_requested,
            entrance_ok=entrance_ok,
            cancel_confirmed=cancel_confirmed,
            min_frames_per_dwell=self.min_frames_per_dwell,
        )
        if final_status != prelim_status or final_reason != prelim_reason:
            status_record["status"] = final_status
            status_record["reason"] = final_reason
            from task4_bringup.result_io import atomic_write_json

            atomic_write_json(run_dir / "status.json", status_record)

        summary_text = format_terminal_summary(task, snapshot, final_status, final_reason)
        self.logger(summary_text)
        self._emit_state(final_status, task_id=task_id, detail=final_reason)
        self._active_task = None
        return {
            "status": final_status,
            "reason": final_reason,
            "count": snapshot["count"],
            "run_dir": str(run_dir),
            "verify": verify_report,
            "summary_text": summary_text,
        }


def main(args=None):
    from collections import deque
    import rclpy
    from rclpy.node import Node
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String
    from task4_bringup.navigation import NavigationClient

    class SearchManagerNode(Node):
        def __init__(self):
            super().__init__("search_manager")
            self.declare_parameter("rooms_file", "src/task4_bringup/config/rooms.yaml")
            self.declare_parameter("objects_file", "src/task4_bringup/config/objects.yaml")
            self.declare_parameter("map_file", "maps/task4_home_v1.yaml")
            self.declare_parameter("results_dir", "results/runs")
            self.declare_parameter("map_frame", "map")
            self.declare_parameter("dwell_sec", 2.0)
            self.declare_parameter("settle_sec", 0.5)
            self.declare_parameter("nav_timeout_sec", 90.0)
            self.declare_parameter("max_retries", 1)
            self.declare_parameter("min_frames_per_dwell", 3)
            self.declare_parameter("gate_m", 0.35)
            self.declare_parameter("min_hits", 3)
            self.declare_parameter("room_margin_m", 0.1)

            rooms_path = resolve_workspace_path(
                self.get_parameter("rooms_file").value, "config/rooms.yaml"
            )
            objects_path = resolve_workspace_path(
                self.get_parameter("objects_file").value, "config/objects.yaml"
            )
            map_path = Path(self.get_parameter("map_file").value)
            if not map_path.is_absolute():
                map_path = Path.cwd() / map_path
            results_dir = Path(self.get_parameter("results_dir").value)
            if not results_dir.is_absolute():
                results_dir = Path.cwd() / results_dir

            rooms_cfg = yaml.safe_load(rooms_path.read_text(encoding="utf-8"))
            objects_cfg = yaml.safe_load(objects_path.read_text(encoding="utf-8"))

            self.status_pub = self.create_publisher(String, "/task4/status", 10)
            self.task_queue = deque()
            self.latest_clock_s = None

            def spin_drain(dt):
                rclpy.spin_once(self, timeout_sec=dt)
                for _ in range(20):
                    rclpy.spin_once(self, timeout_sec=0.0)

            self.executor_engine = SearchExecutor(
                rooms_cfg=rooms_cfg,
                objects_cfg=objects_cfg,
                map_yaml_path=map_path,
                results_dir=results_dir,
                nav_client_factory=lambda: NavigationClient(self),
                spin_step=spin_drain,
                clock_now_sec=lambda: self.latest_clock_s,
                status_publisher=self._publish_status,
                logger=lambda text: self.get_logger().info(text),
                params={
                    "dwell_sec": self.get_parameter("dwell_sec").value,
                    "settle_sec": self.get_parameter("settle_sec").value,
                    "nav_timeout_sec": self.get_parameter("nav_timeout_sec").value,
                    "max_retries": self.get_parameter("max_retries").value,
                    "min_frames_per_dwell": self.get_parameter("min_frames_per_dwell").value,
                    "gate_m": self.get_parameter("gate_m").value,
                    "min_hits": self.get_parameter("min_hits").value,
                    "room_margin_m": self.get_parameter("room_margin_m").value,
                    "map_frame": self.get_parameter("map_frame").value,
                },
            )

            self.create_subscription(String, "/task4/task", self._on_task, 10)
            self.create_subscription(String, "/task4/cancel", self._on_cancel, 10)
            self.create_subscription(String, "/task4/observations", self._on_obs, 20)
            self.create_subscription(String, "/task4/perception_status", self._on_pstatus, 10)
            self.create_subscription(Clock, "/clock", self._on_clock, 10)
            self.get_logger().info("search_manager ready; waiting for /task4/task")

        def _publish_status(self, payload):
            msg = String()
            msg.data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            self.status_pub.publish(msg)

        def _on_clock(self, msg):
            self.latest_clock_s = float(msg.clock.sec) + float(msg.clock.nanosec) / 1_000_000_000.0

        def _on_task(self, msg):
            try:
                self.task_queue.append(json.loads(msg.data))
            except Exception as exc:
                self.get_logger().error(f"Invalid /task4/task JSON: {exc}")

        def _on_cancel(self, msg):
            self.executor_engine.request_cancel(msg.data)

        def _on_obs(self, msg):
            try:
                self.executor_engine.on_observation(json.loads(msg.data))
            except Exception:
                pass

        def _on_pstatus(self, msg):
            try:
                self.executor_engine.on_perception_status(json.loads(msg.data))
            except Exception:
                pass

    rclpy.init(args=args)
    node = SearchManagerNode()
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
            if node.task_queue:
                task = node.task_queue.popleft()
                node.executor_engine.execute_task(task)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
