"""Deadline/acceptance races that are difficult to force against live Nav2."""

from concurrent.futures import Future
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Time

from task4_bringup.navigation import NavigationClient


class NavigationDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.action = Mock()
        self.action.server_is_ready.return_value = True
        self.acceptance = Future()
        self.action.send_goal_async.return_value = self.acceptance
        action_patch = patch("task4_bringup.navigation.ActionClient", return_value=self.action)
        clock_patch = patch("task4_bringup.navigation.time.monotonic", return_value=0.0)
        action_patch.start()
        self.clock = clock_patch.start()
        self.addCleanup(action_patch.stop)
        self.addCleanup(clock_patch.stop)

        clock = Mock()
        clock.now.return_value.to_msg.return_value = Time()
        self.client = NavigationClient(SimpleNamespace(get_clock=lambda: clock))

    def test_late_acceptance_requests_cancel_and_reports_terminal(self):
        self.client.start(1.0, 2.0, 0.0, response_timeout=1.0, cancel_timeout=3.0)
        self.assertIsNone(self.client.poll())
        identifier = self.action.send_goal_async.call_args.kwargs["goal_uuid"]

        self.clock.return_value = 1.0
        self.assertIsNone(self.client.poll())
        handle = Mock(accepted=True)
        result_future, cancel_future = Future(), Future()
        handle.get_result_async.return_value = result_future
        handle.cancel_goal_async.return_value = cancel_future

        self.clock.return_value = 1.4
        self.acceptance.set_result(handle)
        self.assertIsNone(self.client.poll())
        handle.cancel_goal_async.assert_called_once()
        cancel_future.set_result(SimpleNamespace(
            return_code=0, goals_canceling=[SimpleNamespace(goal_id=identifier)],
        ))
        result_future.set_result(SimpleNamespace(status=GoalStatus.STATUS_CANCELED))
        result = self.client.poll()

        self.assertEqual(result.outcome, "ACCEPTANCE_TIMEOUT")
        self.assertEqual(result.action_status, "CANCELED")
        self.assertTrue(result.cancel_accepted)
        self.assertTrue(result.terminal_confirmed)
        self.assertFalse(result.goal_may_be_active)
        self.client.start(3.0, 2.0, 0.0)

    def test_unanswered_dispatch_blocks_the_next_goal(self):
        self.client.start(1.0, 2.0, 0.0, response_timeout=1.0, cancel_timeout=2.0)
        self.assertIsNone(self.client.poll())
        self.clock.return_value = 1.0
        self.assertIsNone(self.client.poll())
        self.clock.return_value = 3.0
        result = self.client.poll()

        self.assertEqual(result.outcome, "ACCEPTANCE_TIMEOUT")
        self.assertIsNone(result.accepted)
        self.assertFalse(result.terminal_confirmed)
        self.assertTrue(result.goal_may_be_active)
        with self.assertRaises(RuntimeError):
            self.client.start(3.0, 2.0, 0.0)
        self.action.send_goal_async.assert_called_once()
