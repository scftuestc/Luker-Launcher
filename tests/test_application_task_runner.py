import threading
import unittest
from unittest.mock import patch

from luker_launcher.application.lifecycle_state import LifecycleState
from luker_launcher.application.task_runner import TaskRunner


class TaskRunnerTests(unittest.TestCase):
    def test_runs_function_in_daemon_thread(self):
        finished = threading.Event()
        runner = TaskRunner()

        self.assertTrue(runner.run(finished.set, name="TestTask"))
        self.assertTrue(finished.wait(timeout=2))

    def test_thread_failure_returns_false_and_logs(self):
        runner = TaskRunner()

        with (
            patch("luker_launcher.application.task_runner.Thread") as thread_cls,
            self.assertLogs("luker_launcher.application.task_runner", level="ERROR"),
        ):
            thread_cls.side_effect = RuntimeError("can't start new thread")
            self.assertFalse(runner.run(lambda: None))


class LifecycleStateTests(unittest.TestCase):
    def test_defaults_to_running(self):
        self.assertFalse(LifecycleState().exiting)

    def test_instances_do_not_share_state(self):
        first = LifecycleState()
        second = LifecycleState()

        first.exiting = True

        self.assertTrue(first.exiting)
        self.assertFalse(second.exiting)


if __name__ == "__main__":
    unittest.main()
