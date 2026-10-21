import unittest

from log_queue import BoundedLogQueue


class BoundedLogQueueTests(unittest.TestCase):
    def test_line_limit_drops_oldest(self):
        log_queue = BoundedLogQueue(max_lines=2, max_bytes=100)
        for line in ("a", "b", "c"):
            log_queue.put(line)

        self.assertEqual(log_queue.get_nowait(), "b")
        self.assertEqual(log_queue.get_nowait(), "c")
        self.assertIsNone(log_queue.get_nowait())

    def test_byte_limit_drops_oldest(self):
        log_queue = BoundedLogQueue(max_lines=10, max_bytes=10)
        for line in ("12345", "67890", "abcde"):
            log_queue.put(line)

        self.assertEqual(log_queue.get_nowait(), "67890")
        self.assertEqual(log_queue.get_nowait(), "abcde")

    def test_single_oversized_line_is_dropped(self):
        log_queue = BoundedLogQueue(max_lines=10, max_bytes=4)
        log_queue.put("12345")

        self.assertTrue(log_queue.empty())

    def test_utf8_bytes_are_counted(self):
        log_queue = BoundedLogQueue(max_lines=10, max_bytes=3)
        log_queue.put("中")
        log_queue.put("a")

        self.assertEqual(log_queue.get_nowait(), "a")
        self.assertIsNone(log_queue.get_nowait())

    def test_clear_discards_pending_lines(self):
        log_queue = BoundedLogQueue(max_lines=10, max_bytes=100)
        log_queue.put("a")

        log_queue.clear()

        self.assertTrue(log_queue.empty())
        self.assertIsNone(log_queue.get_nowait())


if __name__ == "__main__":
    unittest.main()
