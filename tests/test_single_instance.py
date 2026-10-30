import unittest
from unittest.mock import Mock, patch

import process.single_instance as single_instance


class SingleInstanceTests(unittest.TestCase):
    def setUp(self):
        single_instance._mutex_handle = None
        self.kernel32 = Mock()
        self.patcher = patch.object(single_instance, "_kernel32", self.kernel32)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.addCleanup(setattr, single_instance, "_mutex_handle", None)
        self.last_error_patcher = patch.object(
            single_instance.ctypes, "get_last_error", return_value=0
        )
        self.last_error_patcher.start()
        self.addCleanup(self.last_error_patcher.stop)

    def test_acquire_creates_mutex(self):
        self.kernel32.CreateMutexW.return_value = 123

        self.assertTrue(single_instance.acquire())

        self.kernel32.CreateMutexW.assert_called_once_with(
            None,
            False,
            single_instance.MUTEX_NAME,
        )
        self.assertEqual(single_instance._mutex_handle, 123)

    def test_acquire_reuses_cached_handle(self):
        single_instance._mutex_handle = 123

        self.assertTrue(single_instance.acquire())

        self.kernel32.CreateMutexW.assert_not_called()

    def test_acquire_fails_open_when_create_fails(self):
        self.kernel32.CreateMutexW.return_value = 0

        self.assertTrue(single_instance.acquire())

        self.assertIsNone(single_instance._mutex_handle)

    def test_acquire_returns_false_when_already_exists(self):
        self.kernel32.CreateMutexW.return_value = 123
        single_instance.ctypes.get_last_error.return_value = single_instance.ERROR_ALREADY_EXISTS

        self.assertFalse(single_instance.acquire())

        self.kernel32.CloseHandle.assert_called_once_with(123)

    def test_release_closes_and_clears_handle(self):
        single_instance._mutex_handle = 123

        single_instance.release()

        self.kernel32.CloseHandle.assert_called_once_with(123)
        self.assertIsNone(single_instance._mutex_handle)

    def test_release_without_handle_is_noop(self):
        single_instance.release()

        self.kernel32.CloseHandle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
