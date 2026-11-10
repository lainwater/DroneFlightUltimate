"""core.drone.telemetry - one set of key names and units."""

import pytest

from core.drone.telemetry import mission_pad_from_tello, parse_key_values, tello_query, tello_state, to_number

RAW = parse_key_values(
    "mid:-1;x:-100;y:-100;z:-100;mpry:0,0,0;pitch:0;roll:-1;yaw:45;vgx:1;vgy:2;vgz:3;templ:60;temph:63;tof:10;h:80;bat:87;baro:1.25;time:5;agx:1.0;agy:2.0;agz:-1000.0;"
)


def test_state_names():
    s = tello_state(RAW, {"x": 1, "y": 2, "z": 80})
    assert s == {
        "battery": 87,
        "height": 80,
        "temperature": 63,
        "temperature_low": 60,
        "tof": 10,
        "barometer": 1.25,
        "flight_time": 5,
        "attitude": {"pitch": 0, "roll": -1, "yaw": 45},
        "speed": {"x": 1, "y": 2, "z": 3},
        "acceleration": {"x": 1, "y": 2, "z": -1000},
        "position": {"x": 1, "y": 2, "z": 80},
        "mission_pad": {"id": -1},
    }


def test_basic_tello_has_no_mission_pad():
    raw = {k: v for k, v in RAW.items() if k not in ("mid", "x", "y", "z", "mpry")}
    assert "mission_pad" not in tello_state(raw)


def test_mission_pad_seen():
    assert mission_pad_from_tello({"mid": 3, "x": 10, "y": -5, "z": 90, "mpry": "1,30,2"}) == {
        "id": 3,
        "x": 10,
        "y": -5,
        "z": 90,
        "mpry": [1, 30, 2],
        "yaw": 30,
    }


@pytest.mark.parametrize(
    "what, raw, value",
    [
        ("height", "10dm", 100),
        ("tof", "100mm", 10),
        ("ext_tof", "tof 1234", 123.4),
        ("temperature", "60~63C", 63),
        ("flight_time", "12s", 12),
        ("battery", "87", 87),
        ("attitude", "pitch:1;roll:2;yaw:3;", {"pitch": 1, "roll": 2, "yaw": 3}),
        ("acceleration", "agx:1.00;agy:2.00;agz:-999.00;", {"x": 1, "y": 2, "z": -999}),
        ("serial_number", "0TQZK7", "0TQZK7"),
    ],
)
def test_query_units(what, raw, value):
    assert tello_query(what, raw) == value


def test_to_number():
    assert to_number("7") == 7 and to_number("7.5") == 7.5 and to_number("x") == "x"
