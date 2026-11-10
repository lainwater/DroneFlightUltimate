"""
Unified telemetry - ONE set of key names and units for every drone.

state.<drone_id> (start_state_receiver, ~10 Hz) and data.<drone_id> (answers
of get_*) use the same keys, whatever the drone calls them internally:

    battery          %
    height           cm above ground (Tello: its height sensor)
    temperature      degC (Tello: the higher of its two board sensors)
    temperature_low  degC (Tello only: the lower one)
    attitude         {"pitch", "roll", "yaw"}   degrees
    position         {"x", "y", "z"}            cm, x right, y forward, z up
                     (Tello: dead-reckoning ESTIMATE from the commands sent, z = height;
                      simdrone: the simulated position)
    speed            {"x", "y", "z"}            as reported by the drone
    acceleration     {"x", "y", "z"}            as reported by the drone (Tello: 0.001 g)
    tof              cm, downward distance sensor
    barometer        barometer reading (Tello: m)
    flight_time      s, motors-on time
    mission_pad      {"id"}  -1 = no pad seen, -2 = detection off;
                     with a pad: + "x", "y", "z" (cm) and "yaw" (= mpry[1]), "mpry" - exactly as the
                     Tello reports them (its pad frame: rocket = +x, y right, yaw clockwise; the frame
                     goto_mission_pad uses). Standard right-handed conversion: see
                     more_examples/edu_pad_pose_orbit/commander/pose.py (Tello EDU / Talent only)
    flight_mode      simdrone only

Only keys the drone actually reports are present.
"""

import re
from typing import Any

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def to_number(value: Any) -> Any:
    """'87' -> 87, '12.5' -> 12.5; anything else unchanged."""
    if isinstance(value, (int, float)):
        return value
    try:
        f = float(value)
    except (TypeError, ValueError):
        return value
    return int(f) if f.is_integer() else f


def _numbers(text: str) -> list[float]:
    return [float(n) for n in _NUMBER.findall(str(text))]


def _xyz(raw: dict, kx: str, ky: str, kz: str) -> dict | None:
    if kx in raw and ky in raw and kz in raw:
        return {"x": to_number(raw[kx]), "y": to_number(raw[ky]), "z": to_number(raw[kz])}
    return None


def parse_key_values(raw: str) -> dict[str, Any]:
    """Tello 'pitch:0;roll:0;yaw:0;...;' -> {"pitch": 0, ...} (raw names)."""
    out: dict[str, Any] = {}
    for field in str(raw).strip().rstrip(";").split(";"):
        if ":" not in field:
            continue
        key, _, value = field.partition(":")
        out[key.strip()] = to_number(value.strip())
    return out


def mission_pad_from_tello(raw: dict) -> dict | None:
    """Tello mid/x/y/z/mpry -> {"id", ...}. None if the drone reports no pad fields (basic Tello)."""
    if "mid" not in raw:
        return None
    pad_id = int(to_number(raw["mid"]))
    pad: dict[str, Any] = {"id": pad_id}
    if pad_id >= 0:
        pad.update({k: to_number(raw[k]) for k in ("x", "y", "z") if k in raw})
        mpry = [int(v) for v in _numbers(raw.get("mpry", ""))]
        if len(mpry) == 3:
            pad["mpry"] = mpry
            pad["yaw"] = mpry[1]  # yaw is the 2nd value - checked on a Tello EDU
    return pad


def tello_state(raw: dict, position: dict | None = None) -> dict:
    """One Tello state packet (raw names) -> unified telemetry."""
    out: dict[str, Any] = {}
    for src, dst in (("bat", "battery"), ("h", "height"), ("temph", "temperature"), ("templ", "temperature_low"), ("tof", "tof")):
        if src in raw:
            out[dst] = to_number(raw[src])
    if "baro" in raw:
        out["barometer"] = to_number(raw["baro"])
    if "time" in raw:
        out["flight_time"] = to_number(raw["time"])
    if all(k in raw for k in ("pitch", "roll", "yaw")):
        out["attitude"] = {"pitch": to_number(raw["pitch"]), "roll": to_number(raw["roll"]), "yaw": to_number(raw["yaw"])}
    speed = _xyz(raw, "vgx", "vgy", "vgz")
    if speed:
        out["speed"] = speed
    acc = _xyz(raw, "agx", "agy", "agz")
    if acc:
        out["acceleration"] = acc
    if position is not None:
        out["position"] = dict(position)
    pad = mission_pad_from_tello(raw)
    if pad is not None:
        out["mission_pad"] = pad
    return out


def _length_cm(text: str) -> float | None:
    """'10dm' -> 100, '100mm' -> 10, 'tof 1234' (mm) -> 123.4, '55' (cm) -> 55."""
    nums = _numbers(text)
    if not nums:
        return None
    value, t = nums[-1], str(text).lower()
    if "mm" in t or t.startswith("tof"):
        value /= 10
    elif "dm" in t:
        value *= 10
    return to_number(round(value, 1))


def tello_query(what: str, raw: str) -> Any:
    """Answer of a Tello '?' query -> value in unified units (key = `what`)."""
    if what in ("height", "tof", "ext_tof"):
        return _length_cm(raw)
    if what == "temperature":  # '60~63C' -> 63 (the higher one, like state 'temperature')
        nums = _numbers(raw)
        return to_number(max(nums)) if nums else raw
    if what == "flight_time":  # '12s'
        nums = _numbers(raw)
        return to_number(nums[0]) if nums else raw
    if what == "attitude":
        kv = parse_key_values(raw)
        return {k: kv.get(k) for k in ("pitch", "roll", "yaw")}
    if what == "acceleration":
        kv = parse_key_values(raw)
        return _xyz(kv, "agx", "agy", "agz") or kv
    return to_number(str(raw).strip())


__all__ = ["mission_pad_from_tello", "parse_key_values", "tello_query", "tello_state", "to_number"]
