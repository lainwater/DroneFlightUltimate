# core.vicon

Reads one subject (rigid body) from a Vicon DataStream server and publishes its pose on the bus.

```python
from core.vicon import get_vicon

vicon = get_vicon(drone_id="drone1", bus=bus, host="192.168.10.1:801", subject="tello-1", rate_hz=20)
await vicon.start()      # returns at once; connection result comes as ack.vicon.* / error.vicon.*
...
await vicon.stop()
```

Needs `vicon_dssdk` (not on PyPI). Install it from the Vicon DataStream SDK folder: `install_vicon_dssdk.bat`,
or `pip install "<SDK>\Python\vicon_dssdk"`.

| Argument | | |
|---|---|---|
| `host` | `"192.168.10.1:801"` | DataStream server `ip:port` (Vicon Tracker PC) |
| `subject` | `"tello-1"` | subject name in Vicon Tracker |
| `segment` | = subject | for single-segment objects the segment has the subject's name |
| `rate_hz` | `20` | how often the pose is published (Vicon itself runs at 100+ Hz) |

## Output

```python
# vicon.drone1
{"ts": 1762771200.1, "frame": 1234, "subject": "tello-1", "occluded": False,
 "x": 1234.5, "y": -250.0, "z": 800.0,              # mm, Vicon world frame
 "roll": 0.0, "pitch": 0.0, "yaw": 45.0,            # deg, extrinsic xyz
 "qx": 0.0, "qy": 0.0, "qz": 0.383, "qw": 0.924}
# not visible: {"ts", "frame", "subject", "occluded": True}
```

`vicon.latest` always holds the newest pose (independent of `rate_hz`), handy in a control loop.

## Never lags behind

The SDK calls block, so they run in their own thread. Two things keep the data fresh even when video and YOLO keep
the event loop busy:

- the server is asked for the **newest** frame only (ClientPull mode, buffer size 1)
- at most **one** publish is waiting on the event loop. Newer samples overwrite older ones, so old data is dropped.

Measured with a deliberately overloaded loop: < 50 ms behind. The earlier version queued every sample and fell 27 s behind.

## Tips

- Keep `vicon.*` out of the console logger (`exclude_topics=("frame.*", "vicon.*", "display.*")`); 20 lines/s is unreadable and slow.
- Example: `projects/examples/feature_vicon`.
- The Vicon PC is often `192.168.10.1`, the same as the Tello's hotspot address. On the lab network the Tello has
  another IP (station mode), so don't leave a project's drone IP at `192.168.10.1` there.
