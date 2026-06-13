from __future__ import annotations

import unittest

from madcli.event_bus import EventBus, WORKFLOW_STARTED, TASK_COMPLETED


class EventBusTests(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        EventBus.reset_instance()

    def test_subscriber_receives_published_event(self) -> None:
        events: list[dict] = []

        def cb(event_type: str, payload: dict) -> None:
            events.append({"type": event_type, "payload": payload})

        bus = EventBus.instance()
        bus.subscribe(WORKFLOW_STARTED, cb)
        bus.publish(WORKFLOW_STARTED, {"workflow_id": "wf-1"})

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], WORKFLOW_STARTED)
        self.assertEqual(events[0]["payload"]["workflow_id"], "wf-1")

    def test_unsubscriber_does_not_receive_events(self) -> None:
        events: list[dict] = []

        def cb(event_type: str, payload: dict) -> None:
            events.append(payload)

        bus = EventBus.instance()
        bus.subscribe(TASK_COMPLETED, cb)
        bus.publish(TASK_COMPLETED, {"task_id": "t1"})
        self.assertEqual(len(events), 1)

        bus.unsubscribe(TASK_COMPLETED, cb)
        bus.publish(TASK_COMPLETED, {"task_id": "t2"})
        self.assertEqual(len(events), 1)

    def test_multiple_subscribers_receive_same_event(self) -> None:
        count = [0]

        def cb1(event_type, payload):
            count[0] += 1

        def cb2(event_type, payload):
            count[0] += 1

        bus = EventBus.instance()
        bus.subscribe(WORKFLOW_STARTED, cb1)
        bus.subscribe(WORKFLOW_STARTED, cb2)
        bus.publish(WORKFLOW_STARTED, {})

        self.assertEqual(count[0], 2)

    def test_publish_with_no_subscribers_does_not_crash(self) -> None:
        bus = EventBus.instance()
        bus.publish("unknown.event", {})

    def test_callback_exception_does_not_block_other_callbacks(self) -> None:
        count = [0]

        def crashing_cb(event_type, payload):
            raise RuntimeError("boom")

        def normal_cb(event_type, payload):
            count[0] += 1

        bus = EventBus.instance()
        bus.subscribe(TASK_COMPLETED, crashing_cb)
        bus.subscribe(TASK_COMPLETED, normal_cb)
        bus.publish(TASK_COMPLETED, {})

        self.assertEqual(count[0], 1)

    def test_singleton_returns_same_instance(self) -> None:
        bus1 = EventBus.instance()
        bus2 = EventBus.instance()
        self.assertIs(bus1, bus2)


if __name__ == "__main__":
    unittest.main()
