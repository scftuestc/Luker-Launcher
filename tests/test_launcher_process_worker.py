import unittest
from unittest.mock import Mock

from launcher_app import LukerLauncher


class ProcessWorkerTests(unittest.TestCase):
    @staticmethod
    def _make_launcher() -> LukerLauncher:
        launcher = object.__new__(LukerLauncher)
        launcher._process_busy = False
        return launcher

    def test_thread_start_failure_resets_busy(self):
        launcher = self._make_launcher()
        failures = []

        def fail(_worker: object) -> None:
            raise RuntimeError("can't start new thread")

        launcher._run_async = fail

        with self.assertLogs("launcher_app", level="ERROR"):
            started = launcher._start_process_worker(
                lambda: None,
                on_failure=lambda: failures.append("fallback"),
                context="测试",
            )

        self.assertFalse(started)
        self.assertFalse(launcher._process_busy)
        self.assertEqual(failures, ["fallback"])

    def test_success_keeps_busy_until_finish(self):
        launcher = self._make_launcher()
        workers = []
        launcher._run_async = workers.append

        started = launcher._start_process_worker(lambda: None)

        self.assertTrue(started)
        self.assertTrue(launcher._process_busy)
        self.assertEqual(len(workers), 1)

    def test_process_action_failure_is_logged_and_finishes(self):
        launcher = self._make_launcher()
        launcher._exiting = False
        launcher._ensure_process_manager = lambda: object()
        launcher._on_log = Mock()
        launcher._finish_process_action = Mock()
        launcher._post_ui = lambda callback, key=None, control=False: callback() or True
        launcher._run_async = lambda worker: worker()

        def action(_manager: object) -> None:
            raise RuntimeError("boom")

        with self.assertLogs("launcher_app", level="ERROR"):
            launcher._do_process_action(action)

        launcher._finish_process_action.assert_called_once()
        self.assertTrue(
            any("进程操作失败" in call.args[0] for call in launcher._on_log.call_args_list)
        )


if __name__ == "__main__":
    unittest.main()
