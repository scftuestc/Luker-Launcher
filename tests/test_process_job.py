import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import process.job as job


class JobObjectTests(unittest.TestCase):
    def setUp(self):
        job._job_handle = None
        self.kernel32 = Mock()
        self.patcher = patch.object(job, "_kernel32", self.kernel32)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(setattr, job, "_job_handle", None)
        self.last_error_patcher = patch.object(job.ctypes, "get_last_error", return_value=5)
        self.last_error_patcher.start()
        self.addCleanup(self.last_error_patcher.stop)

    def test_create_failure_returns_none(self):
        self.kernel32.CreateJobObjectW.return_value = 0

        self.assertIsNone(job._get_job_handle())

    def test_set_information_failure_closes_handle_and_does_not_cache(self):
        self.kernel32.CreateJobObjectW.return_value = 123
        self.kernel32.SetInformationJobObject.return_value = 0

        self.assertIsNone(job._get_job_handle())

        self.kernel32.CloseHandle.assert_called_once_with(123)
        self.assertIsNone(job._job_handle)

    def test_successful_handle_is_cached(self):
        self.kernel32.CreateJobObjectW.return_value = 123
        self.kernel32.SetInformationJobObject.return_value = 1

        self.assertEqual(job._get_job_handle(), 123)
        self.assertEqual(job._get_job_handle(), 123)
        self.kernel32.CreateJobObjectW.assert_called_once_with(None, None)
        self.assertEqual(job._job_handle, 123)

    def test_assign_without_job_returns_false(self):
        process = SimpleNamespace(pid=4242)
        with patch.object(job, "_get_job_handle", return_value=None):
            self.assertFalse(job.assign_to_job(process))

        self.kernel32.OpenProcess.assert_not_called()

    def test_open_process_failure_returns_false(self):
        self.kernel32.OpenProcess.return_value = 0

        self.assertFalse(job.assign_to_job(SimpleNamespace(pid=4242)))

    def test_assign_failure_closes_process_handle(self):
        self.kernel32.OpenProcess.return_value = 456
        self.kernel32.AssignProcessToJobObject.return_value = 0

        self.assertFalse(job.assign_to_job(SimpleNamespace(pid=4242)))

        self.kernel32.CloseHandle.assert_called_once_with(456)

    def test_assign_success_closes_process_handle(self):
        self.kernel32.OpenProcess.return_value = 456
        self.kernel32.AssignProcessToJobObject.return_value = 1

        self.assertTrue(job.assign_to_job(SimpleNamespace(pid=4242)))

        self.kernel32.OpenProcess.assert_called_once_with(
            job.PROCESS_SET_QUOTA | job.PROCESS_TERMINATE,
            False,
            4242,
        )
        self.kernel32.CloseHandle.assert_called_once_with(456)


if __name__ == "__main__":
    unittest.main()
