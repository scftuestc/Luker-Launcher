import unittest

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


if __name__ == "__main__":
    unittest.main()
