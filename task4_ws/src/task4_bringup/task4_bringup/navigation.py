"""Executor-driven NavigateToPose client for sequential room search."""

from dataclasses import dataclass, field
import math
import time
from uuid import uuid4

from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from unique_identifier_msgs.msg import UUID


_TERMINAL_STATUS = {
    GoalStatus.STATUS_SUCCEEDED: "SUCCEEDED",
    GoalStatus.STATUS_CANCELED: "CANCELED",
    GoalStatus.STATUS_ABORTED: "ABORTED",
}


def _seconds(stamp):
    return stamp.sec + stamp.nanosec / 1_000_000_000


def _feedback_summary(message):
    feedback = message.feedback
    pose = feedback.current_pose
    orientation = pose.pose.orientation
    yaw = math.atan2(
        2 * (orientation.w * orientation.z + orientation.x * orientation.y),
        1 - 2 * (orientation.y ** 2 + orientation.z ** 2),
    )
    return {
        "frame_id": pose.header.frame_id,
        "stamp_s": _seconds(pose.header.stamp),
        "x": pose.pose.position.x,
        "y": pose.pose.position.y,
        "yaw": yaw,
        "distance_remaining_m": (feedback.distance_remaining
                                 if math.isfinite(feedback.distance_remaining) else None),
        "navigation_time_s": _seconds(feedback.navigation_time),
        "estimated_time_remaining_s": _seconds(feedback.estimated_time_remaining),
        "recoveries": feedback.number_of_recoveries,
    }


@dataclass
class NavigationResult:
    goal: dict
    outcome: str = ""
    reason: str = ""
    goal_id: str | None = None
    accepted: bool | None = None
    status_code: int | None = None
    action_status: str | None = None
    terminal_confirmed: bool = False
    cancellation_reason: str | None = None
    cancel_accepted: bool | None = None
    cancel_return_code: int | None = None
    cancel_error: str | None = None
    goal_may_be_active: bool = False
    feedback: dict | None = None
    elapsed_s: float = 0.0
    phase_seconds: dict = field(default_factory=dict)

    @property
    def succeeded(self):
        return self.outcome == "SUCCEEDED"


class NavigationClient:
    """Call start() and poll() from one executor thread. The caller spins ROS.

    Timeouts use monotonic wall time. The execution budget begins at acceptance.
    If dispatch may have occurred and the terminal status is unknown, this
    instance refuses another goal. The caller must reconcile the old goal first.
    """

    def __init__(self, node):
        self._node = node
        self._client = ActionClient(node, NavigateToPose, "navigate_to_pose")
        self._report = None
        self._blocked = False

    def start(self, x, y, yaw, *, timeout=120.0, cancel_after=None,
              discovery_timeout=8.0, response_timeout=8.0, cancel_timeout=8.0):
        if self._report is not None or self._blocked:
            raise RuntimeError("Previous navigation is active or lacks a confirmed terminal status.")
        if not all(math.isfinite(value) for value in (x, y, yaw)):
            raise ValueError("Goal coordinates and heading must be finite.")
        limits = [timeout, discovery_timeout, response_timeout, cancel_timeout]
        if cancel_after is not None:
            limits.append(cancel_after)
        if any(not math.isfinite(value) or value <= 0 for value in limits):
            raise ValueError("Timeouts and cancellation delay must be positive finite seconds.")

        self._report = NavigationResult(goal={"frame_id": "map", "x": x, "y": y, "yaw": yaw})
        self._started = time.monotonic()
        self._phase_started = self._started
        self._phase = "discovery"
        self._deadline = self._started + discovery_timeout
        self._response_timeout = response_timeout
        self._execution_timeout = timeout
        self._cancel_timeout = cancel_timeout
        self._cancel_after = cancel_after
        self._cancel_requested = False
        self._send_future = None
        self._handle = None
        self._result_future = None
        self._cancel_future = None
        self._lost_since = None

    def cancel(self):
        """Ask poll() to cancel. Returns False when there is no attempt."""
        if self._report is None:
            return False
        self._cancel_requested = True
        return True

    def _enter(self, phase, now, limit):
        self._report.phase_seconds[self._phase] = now - self._phase_started
        self._phase = phase
        self._phase_started = now
        self._deadline = now + limit

    def _finish(self, outcome, reason, now):
        report = self._report
        report.outcome = outcome
        report.reason = reason
        report.elapsed_s = now - self._started
        report.phase_seconds[self._phase] = now - self._phase_started
        report.goal_may_be_active = (
            report.goal_id is not None and report.accepted is not False
            and not report.terminal_confirmed
        )
        self._blocked = report.goal_may_be_active
        self._report = None
        return report

    def _record_feedback(self, report, message):
        if self._report is report:
            report.feedback = _feedback_summary(message)

    def _send(self, now):
        report = self._report
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = report.goal["frame_id"]
        goal.pose.header.stamp = self._node.get_clock().now().to_msg()
        goal.pose.pose.position.x = report.goal["x"]
        goal.pose.pose.position.y = report.goal["y"]
        goal.pose.pose.orientation.z = math.sin(report.goal["yaw"] / 2)
        goal.pose.pose.orientation.w = math.cos(report.goal["yaw"] / 2)
        identifier = uuid4()
        report.goal_id = identifier.hex
        self._send_future = self._client.send_goal_async(
            goal, goal_uuid=UUID(uuid=list(identifier.bytes)),
            feedback_callback=lambda message: self._record_feedback(report, message),
        )
        self._enter("response", now, self._response_timeout)

    def _read_acceptance(self, now):
        self._handle = self._send_future.result()
        self._report.accepted = self._handle.accepted
        if not self._handle.accepted:
            return self._finish("REJECTED", "Nav2 rejected the goal.", now)
        self._result_future = self._handle.get_result_async()
        if self._phase != "cancellation":
            self._enter("execution", now, self._execution_timeout)
        return None

    def _stop(self, cause, now):
        self._report.cancellation_reason = cause
        self._enter("cancellation", now, self._cancel_timeout)

    def _read_result(self, now):
        report = self._report
        report.status_code = self._result_future.result().status
        report.action_status = _TERMINAL_STATUS.get(report.status_code)
        report.terminal_confirmed = report.action_status is not None
        if not report.terminal_confirmed:
            return self._finish(
                report.cancellation_reason or "RESULT_UNKNOWN",
                f"Nav2 returned status {report.status_code}; terminal status unconfirmed.", now,
            )
        cause = report.cancellation_reason
        outcome = report.action_status if cause in (None, "CANCEL_REQUESTED") else cause
        reason = f"Nav2 terminal status: {report.action_status}."
        if cause in ("ACCEPTANCE_TIMEOUT", "EXECUTION_TIMEOUT", "SERVER_LOST"):
            reason = f"{cause}: {reason}"
        return self._finish(outcome, reason, now)

    def _poll_cancellation(self, now):
        report = self._report
        if self._handle is None and self._send_future.done():
            rejected = self._read_acceptance(now)
            if rejected is not None:
                return rejected
        cancel_replied = self._cancel_future is not None and self._cancel_future.done()
        if cancel_replied:
            try:
                response = self._cancel_future.result()
            except RuntimeError as error:
                report.cancel_error = str(error)
            else:
                report.cancel_return_code = response.return_code
                report.cancel_accepted = any(
                    bytes(info.goal_id.uuid).hex() == report.goal_id for info in response.goals_canceling
                )
        if (self._result_future is not None and self._result_future.done()
                and (self._cancel_future is None or cancel_replied or now >= self._deadline)):
            return self._read_result(now)
        if now >= self._deadline:
            return self._finish(
                report.cancellation_reason,
                "Cancellation deadline elapsed; terminal status unconfirmed.", now,
            )
        if self._handle is not None and self._cancel_future is None and report.cancel_error is None:
            try:
                self._cancel_future = self._handle.cancel_goal_async()
            except RuntimeError as error:
                report.cancel_error = str(error)
        return None

    def poll(self):
        """Return a result once when the attempt finishes, otherwise None."""
        if self._report is None:
            return None
        now = time.monotonic()
        try:
            return self._poll(now)
        except (RuntimeError, ValueError) as error:
            # An exception after dispatch leaves the goal potentially active.
            cause = self._report.cancellation_reason or "ACTION_ERROR"
            return self._finish(cause, f"ROS action operation failed: {error}", now)

    def _poll(self, now):
        if self._phase == "discovery":
            if self._cancel_requested:
                return self._finish("CANCELED", "Canceled before dispatch.", now)
            if now >= self._deadline:
                return self._finish("SERVER_UNAVAILABLE", "NavigateToPose discovery timed out.", now)
            if self._client.server_is_ready():
                self._send(now)
        elif self._phase == "response":
            if self._cancel_requested or now >= self._deadline:
                cause = "CANCEL_REQUESTED" if self._cancel_requested else "ACCEPTANCE_TIMEOUT"
                self._stop(cause, now)
            elif self._send_future.done():
                return self._read_acceptance(now)
        elif self._phase == "execution":
            if self._result_future.done():
                return self._read_result(now)
            if now >= self._deadline:
                self._stop("EXECUTION_TIMEOUT", now)
            elif self._cancel_requested or (
                self._cancel_after is not None and now - self._phase_started >= self._cancel_after
            ):
                self._stop("CANCEL_REQUESTED", now)
            elif self._client.server_is_ready():
                self._lost_since = None
            elif self._lost_since is None:
                self._lost_since = now
            elif now - self._lost_since >= 1.0:
                self._stop("SERVER_LOST", now)
        if self._phase == "cancellation":
            return self._poll_cancellation(now)
        return None
