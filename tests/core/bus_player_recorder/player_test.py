"""Flight recorder (.jsonl) and replay."""

import asyncio
import json

import numpy as np

from core.bus import get_bus
from core.bus_player_recorder import get_player, get_recorder
from core.bus_player_recorder.schema import BusLogEntry


def _record(path, events, exclude=None):
    async def scenario():
        bus = get_bus()
        rec = get_recorder(path)
        if exclude is not None:
            rec.exclude_topics = exclude
        rec.attach(bus)
        for topic, data in events:
            await bus.publish(topic, data)
        rec.detach(bus)

    asyncio.run(scenario())
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_recorder_writes_one_line_per_message(tmp_path):
    lines = _record(tmp_path / "logs" / "f.jsonl", [("cmd.d", {"action": "takeoff"}), ("ack.d", {"cmd": "takeoff", "ack": "True"})])
    assert [(entry["topic"], entry["data"]) for entry in lines] == [("cmd.d", {"action": "takeoff"}), ("ack.d", {"cmd": "takeoff", "ack": "True"})]
    assert all(isinstance(entry["ts"], float) for entry in lines)


def test_recorder_skips_frames_and_non_json(tmp_path):
    lines = _record(
        tmp_path / "f.jsonl",
        [("frame.d", {"frame": "x"}), ("data.d", {"m": np.zeros(3)}), ("display.d", {"a": 1}), ("ack.d", {"ack": "True"})],
        exclude=("frame.*", "display.*"),
    )
    assert [entry["topic"] for entry in lines] == ["ack.d"]


def test_player_replays_in_order_and_steps(tmp_path):
    path = tmp_path / "f.jsonl"
    entries = [BusLogEntry(100.0, "cmd.d", {"action": "connect"}), BusLogEntry(100.05, "cmd.d", {"action": "takeoff"})]
    path.write_text("\n".join(e.to_line() for e in entries) + "\nnot json\n")

    async def scenario():
        bus = get_bus()
        got = []
        bus.subscribe("*", lambda t, d: got.append(d["action"]))
        await get_player(path).play(bus, speed=10.0)
        stepped = []
        bus2 = get_bus()
        bus2.subscribe("*", lambda t, d: stepped.append(d["action"]))
        player = get_player(path)
        await player.step(bus2)
        return got, stepped

    played, stepped = asyncio.run(scenario())
    assert played == ["connect", "takeoff"]  # the broken line is skipped
    assert stepped == ["connect"]
