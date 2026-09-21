"""
Tests for core.bus.

Run with: pytest tests/core/bus/bus_test.py -v
"""

import asyncio

from core.bus import get_bus


def test_single_subscriber_receives_published_data():
    bus = get_bus()
    received = []

    def on_event(topic, data):
        received.append((topic, data))

    bus.subscribe("cmd.drone1", on_event)
    asyncio.run(bus.publish("cmd.drone1", {"action": "forward"}))

    assert received == [("cmd.drone1", {"action": "forward"})]


def test_subscriber_on_different_topic_is_not_called():
    bus = get_bus()
    received = []

    bus.subscribe("cmd.drone1", lambda t, d: received.append((t, d)))
    asyncio.run(bus.publish("cmd.drone2", {"action": "forward"}))

    assert received == []


def test_multiple_subscribers_on_same_topic_all_receive_it():
    bus = get_bus()
    calls = []

    bus.subscribe("state.drone1", lambda t, d: calls.append("a"))
    bus.subscribe("state.drone1", lambda t, d: calls.append("b"))
    asyncio.run(bus.publish("state.drone1", {"battery": 87}))

    assert sorted(calls) == ["a", "b"]


def test_async_callback_is_awaited():
    bus = get_bus()
    received = []

    async def on_event(topic, data):
        await asyncio.sleep(0)  # simulate real async work (e.g. I/O)
        received.append((topic, data))

    bus.subscribe("video.drone1", on_event)
    asyncio.run(bus.publish("video.drone1", {"frame_id": 42}))

    assert received == [("video.drone1", {"frame_id": 42})]


def test_wildcard_subscriber_receives_every_topic():
    bus = get_bus()
    seen_topics = []

    bus.subscribe("*", lambda t, d: seen_topics.append(t))

    async def publish_both():
        await bus.publish("cmd.drone1", {"action": "forward"})
        await bus.publish("state.drone2", {"battery": 50})

    asyncio.run(publish_both())

    assert seen_topics == ["cmd.drone1", "state.drone2"]


def test_wildcard_and_specific_subscriber_both_fire():
    bus = get_bus()
    specific_calls = []
    wildcard_calls = []

    bus.subscribe("cmd.drone1", lambda t, d: specific_calls.append(d))
    bus.subscribe("*", lambda t, d: wildcard_calls.append((t, d)))
    asyncio.run(bus.publish("cmd.drone1", {"action": "land"}))

    assert specific_calls == [{"action": "land"}]
    assert wildcard_calls == [("cmd.drone1", {"action": "land"})]


def test_unsubscribe_stops_further_delivery():
    bus = get_bus()
    received = []

    def on_event(topic, data):
        received.append(data)

    bus.subscribe("cmd.drone1", on_event)

    async def publish_twice():
        await bus.publish("cmd.drone1", {"n": 1})
        bus.unsubscribe("cmd.drone1", on_event)
        await bus.publish("cmd.drone1", {"n": 2})

    asyncio.run(publish_twice())

    assert received == [{"n": 1}]


def test_unsubscribe_unknown_callback_is_a_noop():
    bus = get_bus()

    def never_subscribed(topic, data):
        pass

    # Must not raise, even though never_subscribed was never subscribed.
    bus.unsubscribe("cmd.drone1", never_subscribed)


def test_publish_with_no_subscribers_does_not_raise():
    bus = get_bus()
    asyncio.run(bus.publish("cmd.drone1", {"action": "forward"}))


def test_publish_default_data_is_none():
    bus = get_bus()
    received = []

    bus.subscribe("cmd.drone1", lambda t, d: received.append(d))
    asyncio.run(bus.publish("cmd.drone1"))

    assert received == [None]


def test_get_bus_returns_a_fresh_instance_each_time():
    bus_a = get_bus()
    bus_b = get_bus()

    received_a = []
    bus_a.subscribe("cmd.drone1", lambda t, d: received_a.append(d))

    # Publishing on bus_b must NOT reach a subscriber on bus_a - each
    # session/example is expected to own an isolated bus instance.
    asyncio.run(bus_b.publish("cmd.drone1", {"action": "forward"}))

    assert received_a == []