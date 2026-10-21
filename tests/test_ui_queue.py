import unittest

from ui_dispatch import UI_QUEUE_POLL_MS, UiDispatcher


def make_dispatcher(**kwargs) -> UiDispatcher:
    dispatcher = UiDispatcher(lambda _delay, _callback: None, **kwargs)
    dispatcher.start()
    return dispatcher


class UiDispatcherTests(unittest.TestCase):
    def test_coalesced_key_keeps_latest_callback(self):
        dispatcher = make_dispatcher()
        calls = []

        dispatcher.post(lambda: calls.append("first"), "visibility")
        dispatcher.post(lambda: calls.append("second"), "visibility")
        dispatcher.pump()

        self.assertEqual(calls, ["second"])

    def test_plain_events_keep_fifo_order(self):
        dispatcher = make_dispatcher()
        calls = []

        for index in range(3):
            dispatcher.post(lambda i=index: calls.append(i))
        dispatcher.pump()

        self.assertEqual(calls, [0, 1, 2])

    def test_pump_limits_events_per_tick(self):
        dispatcher = make_dispatcher(events_per_tick=2)
        calls = []

        for index in range(5):
            dispatcher.post(lambda i=index: calls.append(i))

        dispatcher.pump()
        self.assertEqual(calls, [0, 1])
        dispatcher.pump()
        self.assertEqual(calls, [0, 1, 2, 3])
        dispatcher.pump()
        self.assertEqual(calls, [0, 1, 2, 3, 4])

    def test_full_queue_drops_oldest_event(self):
        dispatcher = make_dispatcher(maxsize=2)
        calls = []

        for index in range(3):
            dispatcher.post(lambda i=index: calls.append(i))

        dispatcher.pump()
        self.assertEqual(calls, [1, 2])

    def test_post_ignored_after_stop(self):
        dispatcher = make_dispatcher()
        calls = []

        dispatcher.stop()
        dispatcher.post(lambda: calls.append("event"))
        dispatcher.post(lambda: calls.append("state"), "settings")
        dispatcher.pump()

        self.assertEqual(calls, [])

    def test_state_callbacks_run_before_events(self):
        dispatcher = make_dispatcher()
        calls = []

        dispatcher.post(lambda: calls.append("event"))
        dispatcher.post(lambda: calls.append("state"), "settings")
        dispatcher.pump()

        self.assertEqual(calls, ["state", "event"])

    def test_exit_state_survives_full_queue(self):
        dispatcher = make_dispatcher(maxsize=1)
        calls = []

        dispatcher.post(lambda: calls.append("event"), "exit")
        dispatcher.post(lambda: calls.append("queued-1"))
        dispatcher.post(lambda: calls.append("queued-2"))
        dispatcher.pump()

        self.assertEqual(calls, ["event", "queued-2"])

    def test_stop_during_event_skips_remaining_callbacks(self):
        dispatcher = make_dispatcher()
        calls = []

        def stop() -> None:
            calls.append("stop")
            dispatcher.stop()

        dispatcher.post(stop, "exit")
        dispatcher.post(lambda: calls.append("after-exit"))
        dispatcher.pump()

        self.assertEqual(calls, ["stop"])

    def test_start_schedules_poll(self):
        scheduled = []
        dispatcher = UiDispatcher(lambda delay, callback: scheduled.append((delay, callback)))

        dispatcher.start()

        self.assertEqual([delay for delay, _ in scheduled], [UI_QUEUE_POLL_MS])

    def test_backlog_reschedules_immediately(self):
        scheduled = []
        dispatcher = UiDispatcher(
            lambda delay, callback: scheduled.append((delay, callback)),
            events_per_tick=1,
        )
        dispatcher.start()
        calls = []

        dispatcher.post(lambda: calls.append(1))
        dispatcher.post(lambda: calls.append(2))
        dispatcher.pump()

        self.assertEqual(calls, [1])
        self.assertEqual(scheduled[-1][0], 1)

    def test_stop_does_not_reschedule(self):
        scheduled = []
        dispatcher = UiDispatcher(lambda delay, callback: scheduled.append(delay))
        dispatcher.start()
        scheduled.clear()

        dispatcher.stop()
        dispatcher.pump()

        self.assertEqual(scheduled, [])

    def test_pump_without_start_does_nothing(self):
        scheduled = []
        dispatcher = UiDispatcher(lambda delay, callback: scheduled.append(delay))

        dispatcher.pump()

        self.assertEqual(scheduled, [])


if __name__ == "__main__":
    unittest.main()
