import unittest
from types import SimpleNamespace
from unittest.mock import patch

import log.pipeline
from log.pipeline import ACTIVE_POLL_MS, BoundedLogQueue, LogController, LogReplay


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


def make_controller(
    *,
    viewable: bool = True,
    exists: bool = True,
    removed: int = 0,
    query: bool = False,
):
    state = SimpleNamespace(
        viewable=viewable,
        exists=exists,
        removed=removed,
        query=query,
    )
    scheduled = []
    cancelled = []
    resets = []
    batches = []
    adjusted = []
    reruns = []

    def schedule(delay: int, callback) -> str:
        scheduled.append((delay, callback))
        return f"job-{len(scheduled)}"

    def add_entries(entries) -> int:
        batches.append(list(entries))
        return state.removed

    controller = LogController(
        schedule=schedule,
        cancel=cancelled.append,
        exists=lambda: state.exists,
        viewable=lambda: state.viewable,
        reset_display=lambda: resets.append(True),
        add_entries=add_entries,
        adjust_search=adjusted.append,
        has_query=lambda: state.query,
        on_search_rerun=lambda: reruns.append(True),
    )
    return SimpleNamespace(
        controller=controller,
        state=state,
        scheduled=scheduled,
        cancelled=cancelled,
        resets=resets,
        batches=batches,
        adjusted=adjusted,
        reruns=reruns,
    )


def seed(fixture, *lines: str) -> None:
    for line in lines:
        fixture.controller.add_log(line)
    fixture.controller.drain_once()


class LogControllerReplayTests(unittest.TestCase):
    def test_refresh_schedules_chunks_without_bulk_insert(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "a", "b", "c")
        fixture.state.viewable = True

        with patch.object(log.pipeline, "REPLAY_BATCH_SIZE", 2):
            fixture.controller.refresh()

            self.assertTrue(fixture.controller.replaying)
            self.assertEqual(fixture.batches, [])
            self.assertEqual(len(fixture.scheduled), 1)

            delay, first_chunk = fixture.scheduled.pop(0)
            self.assertEqual(delay, log.pipeline.REPLAY_YIELD_MS)
            first_chunk()
            self.assertEqual([entry.text for entry in fixture.batches[0]], ["a", "b"])

            fixture.scheduled.pop(0)[1]()
            self.assertEqual([entry.text for entry in fixture.batches[1]], ["c"])
            self.assertFalse(fixture.controller.replaying)

    def test_live_logs_wait_in_tail_during_replay(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "old")
        fixture.state.viewable = True
        fixture.controller.refresh()

        fixture.controller.add_log("live")
        fixture.controller.drain_once()

        self.assertEqual([entry.text for entry in fixture.controller._replay.tail], ["live"])
        self.assertEqual(fixture.batches, [])

        while fixture.scheduled:
            fixture.scheduled.pop(0)[1]()

        self.assertEqual([entry.text for entry in fixture.batches[-1]], ["live"])
        self.assertFalse(fixture.controller.replaying)

    def test_hide_cancels_replay_and_marks_dirty(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "a")
        fixture.state.viewable = True
        fixture.controller.refresh()

        fixture.controller.on_hide()

        self.assertFalse(fixture.controller.replaying)
        self.assertTrue(fixture.controller.needs_rebuild)
        self.assertEqual(fixture.cancelled, ["job-1"])

    def test_show_after_hide_rebuilds_interrupted_replay(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "a", "b")
        fixture.state.viewable = True
        fixture.controller.refresh()
        self.assertTrue(fixture.controller.replaying)

        fixture.controller.on_hide()
        fixture.scheduled.clear()
        resets_before = len(fixture.resets)

        fixture.controller.on_show()

        self.assertEqual(len(fixture.resets), resets_before + 1)
        self.assertTrue(fixture.controller.replaying)
        while fixture.scheduled:
            fixture.scheduled.pop(0)[1]()
        self.assertEqual([entry.text for entry in fixture.batches[-1]], ["a", "b"])
        self.assertFalse(fixture.controller.needs_rebuild)

    def test_on_show_refreshes_when_needed(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "a")
        fixture.state.viewable = True
        resets_before = len(fixture.resets)

        fixture.controller.on_show()

        self.assertEqual(len(fixture.resets), resets_before + 1)
        self.assertTrue(fixture.controller.replaying)

    def test_finish_replay_runs_search_only_when_query_exists(self):
        fixture = make_controller(viewable=False, query=True)
        seed(fixture, "a")
        fixture.state.viewable = True
        fixture.controller.refresh()

        while fixture.scheduled:
            fixture.scheduled.pop(0)[1]()

        self.assertEqual(fixture.reruns, [True])

    def test_finish_replay_skips_search_without_query(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "a")
        fixture.state.viewable = True
        fixture.controller.refresh()

        while fixture.scheduled:
            fixture.scheduled.pop(0)[1]()

        self.assertEqual(fixture.reruns, [])

    def test_trimmed_lines_adjust_search(self):
        fixture = make_controller(viewable=True, removed=0)
        seed(fixture, "old")
        fixture.state.removed = 2

        fixture.controller.add_log("new")
        fixture.controller.drain_once()

        self.assertEqual(fixture.adjusted, [2])

    def test_clear_empties_stores_and_queues(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "a")
        fixture.controller.add_log("queued")
        resets_before = len(fixture.resets)

        fixture.controller.clear()

        self.assertEqual(fixture.controller._stores["luker"].snapshot(), [])
        self.assertEqual(fixture.controller._stores["gcl"].snapshot(), [])
        self.assertTrue(fixture.controller._queues["luker"].empty())
        self.assertTrue(fixture.controller._queues["gcl"].empty())
        self.assertFalse(fixture.controller.needs_rebuild)
        self.assertEqual(len(fixture.resets), resets_before + 1)

    def test_set_gcl_enabled_false_switches_back_to_luker(self):
        fixture = make_controller()
        fixture.controller.toggle_source()
        self.assertEqual(fixture.controller.source, "gcl")

        fixture.controller.set_gcl_enabled(False)

        self.assertEqual(fixture.controller.source, "luker")

    def test_start_is_idempotent(self):
        fixture = make_controller()

        fixture.controller.start()
        fixture.controller.start()

        self.assertEqual(len(fixture.scheduled), 1)

    def test_stop_cancels_pump_and_replay(self):
        fixture = make_controller()
        seed(fixture, "a")
        fixture.controller.start()
        fixture.controller.refresh()

        fixture.controller.stop()

        self.assertFalse(fixture.controller.replaying)
        self.assertFalse(fixture.controller._started)
        self.assertIsNone(fixture.controller._pump_job)
        self.assertEqual(fixture.cancelled, ["job-2", "job-1"])

    def test_pump_uses_fast_interval_with_backlog(self):
        fixture = make_controller()
        for index in range(11):
            fixture.controller.add_log(str(index))

        fixture.controller.start()

        self.assertEqual(fixture.scheduled[-1][0], ACTIVE_POLL_MS)

    def test_pump_stops_after_window_destroyed(self):
        fixture = make_controller()
        fixture.controller.start()
        fixture.state.exists = False

        fixture.scheduled.pop(0)[1]()

        self.assertFalse(fixture.controller._started)
        self.assertEqual(fixture.scheduled, [])

    def test_add_gcl_log_drains_into_gcl_store(self):
        fixture = make_controller(viewable=False)
        fixture.controller.add_gcl_log("gcl line")

        fixture.controller.drain_once()

        self.assertEqual(
            [entry.text for entry in fixture.controller._stores["gcl"].snapshot()],
            ["gcl line"],
        )

    def test_drain_skips_destroyed_window(self):
        fixture = make_controller(viewable=False, exists=False)
        fixture.controller.add_log("pending")

        fixture.controller.drain_once()

        self.assertFalse(fixture.controller._queues["luker"].empty())

    def test_drain_rebuilds_when_visible(self):
        fixture = make_controller(viewable=False)
        seed(fixture, "a")
        fixture.state.viewable = True

        fixture.controller.drain_once()

        self.assertTrue(fixture.controller.replaying)

    def test_refresh_without_logs_reruns_query(self):
        fixture = make_controller(query=True)

        fixture.controller.refresh()

        self.assertEqual(fixture.reruns, [True])


class LogReplayCancelTests(unittest.TestCase):
    def test_missing_window_cancels_replay(self):
        schedules = []
        finished = []
        replay = LogReplay(
            schedule=lambda _delay, callback: schedules.append(callback) or "job",
            cancel=lambda _job: None,
            add_entries=lambda _entries: None,
            exists=lambda: False,
            on_finished=lambda: finished.append(True),
        )

        replay.start([])
        schedules[0]()

        self.assertFalse(replay.active)
        self.assertEqual(replay.entries, [])
        self.assertEqual(finished, [])

    def test_cancel_replay_clears_snapshot_and_tail(self):
        cancel_calls = []
        replay = LogReplay(
            schedule=lambda _delay, _callback: "job-9",
            cancel=cancel_calls.append,
            add_entries=lambda _entries: None,
            exists=lambda: True,
            on_finished=lambda: None,
        )
        replay.job = "job-9"
        replay.active = True
        replay.entries = [object()]
        replay.index = 1
        replay.tail.append(object())

        replay.cancel()

        self.assertEqual(cancel_calls, ["job-9"])
        self.assertFalse(replay.active)
        self.assertEqual(replay.entries, [])
        self.assertEqual(replay.index, 0)
        self.assertEqual(len(replay.tail), 0)


if __name__ == "__main__":
    unittest.main()
