import datetime
import unittest

from log_store import LogStore


class LogStoreTests(unittest.TestCase):
    def test_capacity_drops_oldest_entries(self):
        store = LogStore(max_entries=3)
        for index in range(5):
            store.append(f"line-{index}")

        self.assertEqual(len(store), 3)
        self.assertEqual(
            [entry.text for entry in store.snapshot()],
            ["line-2", "line-3", "line-4"],
        )

    def test_append_preserves_timestamp(self):
        store = LogStore()
        timestamp = datetime.datetime(2026, 1, 2, 3, 4, 5)
        store.append("hello", timestamp)
        self.assertEqual(store.snapshot()[0].timestamp, timestamp)

    def test_snapshot_is_detached_from_later_writes(self):
        store = LogStore()
        store.append("first")
        snapshot = store.snapshot()
        store.append("second")
        self.assertEqual([entry.text for entry in snapshot], ["first"])

    def test_clear_removes_all_entries(self):
        store = LogStore()
        store.append("first")
        store.clear()
        self.assertEqual(len(store), 0)
        self.assertEqual(store.snapshot(), [])


if __name__ == "__main__":
    unittest.main()
