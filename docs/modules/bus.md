# core.bus

The async publish/subscribe bus. Every module talks only through it. Topic list: [Concepts](../concepts.md#bus-topics).

```python
from core.bus import get_bus

bus = get_bus()                          # a NEW bus each call - one per run, ProjectBase makes it

async def on_ack(topic: str, data) -> None:     # sync functions work too
    print(topic, data)

bus.subscribe("ack.drone1", on_ack)      # exact topic
bus.subscribe("*", on_ack)               # every topic (the only wildcard)
await bus.publish("cmd.drone1", {"action": "connect"})
bus.unsubscribe("ack.drone1", on_ack)    # no error if it wasn't subscribed
```

## Behaviour

- `publish()` calls all subscribers of that exact topic plus all `"*"` subscribers, concurrently, and
  returns when **all of them are done**. A slow handler slows down the publisher, so keep handlers
  short and move heavy work to `asyncio.to_thread`.
- A handler that raises does not stop the other handlers; the exceptions are published on `error.bus` as `{"topic", "errors"}`.
- Topics are plain strings. `"error.*"` is *not* a pattern on the bus (it is in logger/recorder exclude lists).

## From another thread

Threads (pynput keyboard, Vicon SDK) must not call `publish` directly. Hand it to the loop:

```python
asyncio.run_coroutine_threadsafe(bus.publish(topic, data), loop)
```

## Implementations

`SimpleBus` (`implementations/simple_bus.py`). A new one implements `BusBase` (`subscribe`, `unsubscribe`, `publish`).
