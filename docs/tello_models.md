# Tello models and networks

## Which Tello do I have?

| | Tello (basic) | Tello EDU | Tello Talent / RoboMaster TT |
|---|---|---|---|
| config `"model"` | `tello` | `tello_edu` | `tello_talent` |
| SDK | 1.3 | 2.0 (3.0 with firmware ≥ 02.05.01.17) | 3.0 |
| fly, rc, flips, `go`, `curve`, video, telemetry | ✓ | ✓ | ✓ |
| `stop` (hover now), `sdk?`, `sn?` | | ✓ | ✓ |
| mission pads (`mission_pad` telemetry, `goto_mission_pad`, `jump`) | | ✓ | ✓ |
| station mode: joins your Wi-Fi (`tools.set_tello_wifi`), several drones | | ✓ | ✓ |
| downward camera, motor-on (cooling), throw-fly, video fps/bitrate | | new firmware | ✓ |
| expansion kit: RGB LED, 8x8 dot matrix, forward ToF sensor, multi-wifi | | | ✓ |

Set it in `config/mydrone.json`:

```json
{ "drone_1": { "drone_type": "dji_tello", "drone_id": "drone1", "model": "tello_edu", "ip": "192.168.10.1" } }
```

Aliases work too: `basic`, `edu`, `talent`, `rmtt`, `tt`. Without `"model"` DFU sends everything and the drone itself
answers `error` to what it can't do. With it, DFU answers `error NotSupported` right away, says which model is needed,
and sends nothing.

Examples for each: `projects/examples/tello_*` and `more_examples/tello_*` run on every model, `more_examples/edu_*`
need EDU/Talent, `more_examples/talent_*` the Talent with its expansion kit.
[more_examples](../more_examples/README.md)

## Hotspot or station mode

**Hotspot (all models, default):** the Tello opens its own Wi-Fi `TELLO-xxxxxx`, your PC joins it, the Tello is at
`192.168.10.1`. One drone per PC, and the PC has no other Wi-Fi meanwhile.

**Station mode (EDU, Talent):** the Tello joins *your* router. Several drones, the PC and e.g. the Vicon system
share one network.

```bash
# PC on the Tello's hotspot, then:
python -m tools.set_tello_wifi --ssid LAB_WIFI --password secret123
```

The Tello reboots onto the router. Find its IP in the router (best: reserve a fixed IP for its MAC address), put it
in `config/mydrone.json`, connect the PC to the router. **Back to hotspot mode:** hold the power button ~5 s until
the LED blinks.

## Several Tellos at once

Needs EDU / Talent, all in station mode on the same router (steps above, one drone at a time). Each drone in
`config/mydrone.json` needs **its own PC ports**:

```json
{
  "drone_1": { "drone_type": "dji_tello", "drone_id": "drone1", "model": "tello_edu", "ip": "192.168.10.133",
               "cmd_pc_port": 9000, "state_port": 8890, "video_port": 11111 },
  "drone_2": { "drone_type": "dji_tello", "drone_id": "drone2", "model": "tello_edu", "ip": "192.168.10.134",
               "cmd_pc_port": 9001, "state_port": 8891, "video_port": 11112 }
}
```

On `connect` DFU tells each drone where to send its telemetry and video (`port 8891 11112`). Allow all these ports
(inbound UDP) in the firewall. Video from several drones at once costs a lot of Wi-Fi bandwidth; start with video off.

In code, one drone object per entry and everything else per `drone_id`:

```python
self.drones = [self.create_drone(key) for key in sorted(self.drone_config) if key.startswith("drone_")]
patterns = [get_patterns(d.drone_id, self.bus) for d in self.drones]
for p in patterns:
    p.start(p.square(100))              # all fly at the same time
```

Ready-made: `python run.py run -m -n edu_multi_tello` (one keyboard flies all drones, key 9 = all fly a square).
