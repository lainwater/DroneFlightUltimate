# core.logger and core.bus_player_recorder

## Console logger

```python
from core.logger import LoggerType, LogLevel, get_logger

logger = get_logger(LoggerType.LIVE_CONSOLE, min_level=LogLevel.INFO,
                    exclude_topics=("frame.*", "data.stream.*", "display.*"))
bus.subscribe("*", logger.log_bus_event)
```

| `LoggerType` | |
|---|---|
| `LIVE_CONSOLE` | prints `<time>: [LEVEL] - <topic>: <data>` |
| `JSONL` | writes the same to a file (`log_path=`) |
| `NOLOGGER` | nothing |

- `min_level`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. In projects use `self.log_level` (= `[logging] level` in defaults.toml).
- `exclude_topics`: patterns (`fnmatch`), default `("frame.*",)`. Exclude everything that comes many times per second.
- `exclude_data`: hides messages whose `action` (commands) or `cmd` (acks) matches, default `("rc", "rc *")` (stick spam).

## Flight recorder

Every project has `self.recorder`, writing **every bus message** (except `frame.*`) to
`logs/bus_logs/flight_<date>.jsonl`. One line per message:

```json
{"ts": 1762771200.123, "topic": "cmd.drone1", "data": {"action": "takeoff"}}
```

```python
self.recorder.attach(self.bus)                        # in setup()
self.recorder.exclude_topics = ("frame.*", "display.*")   # optional
self.recorder.detach(self.bus)                        # in end_run()
```

Data that isn't JSON (numpy arrays, ...) is skipped for that message.

## Replay

```python
from core.bus import get_bus
from core.bus_player_recorder import get_player

bus = get_bus()
bus.subscribe("*", lambda t, d: print(t, d))
player = get_player("projects/my_project/logs/bus_logs/flight_2026-11-10_12-00-00.jsonl")
await player.play(bus, speed=2.0)     # original timing, 2x faster;  player.pause() / resume() / step(bus)
```

Replaying onto a bus with a drone attached flies the same commands again. Use the simdrone for that.
