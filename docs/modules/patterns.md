# core.patterns

Predefined flight patterns. They fly by publishing normal drone commands on the bus (`cmd.<drone_id>`), so they
work with every drone (Tello of any model, simdrone) and every move is in the flight log.

```python
from core.patterns import get_patterns

patterns = get_patterns("drone1", bus)

await patterns.square(side_cm=100)                    # wait until done (drone must be flying)

patterns.start(patterns.orbit(radius_cm=100))         # or in the background - bus handlers return at once
await patterns.cancel()                               # stop: the drone stops and hovers
patterns.busy                                         # a background pattern is running
patterns.detach()                                     # in end_run()
```

## Patterns

| Method | Flies with | |
|---|---|---|
| `square(side_cm=100)`, `triangle(side_cm=100)`, `hexagon(side_cm=60)` | `goto` | regular polygon, first edge straight ahead, nose keeps its direction |
| `polygon(sides, side_cm)` | `goto` | any regular polygon |
| `rectangle(length_cm=150, width_cm=80)` | `goto` | length ahead, width to the right (clockwise) |
| `circle(radius_cm=80, segments=12)` | `goto` | precise circle as a 12-gon, centre to the right |
| `waypoints([(x, y, z), ...])` | `goto` | points relative to the start: x forward, y left, z up (cm) |
| `lawnmower(lane_length_cm=150, lane_spacing_cm=40, lanes=4, shift_right=False, turn=True)` | steps + rotate | search pattern; `turn=True` turns 180° at each lane end (camera ahead) |
| `spin(degrees=360)` | rotate | turn on the spot |
| `orbit(radius_cm=100, speed_cms=20, laps=1)` | `rc` | circle around a point ahead, **nose to the centre** |
| `dance(amplitude=0.4)` | `rc` | wiggle, sway, bob, nod, shake |
| `hover(seconds)` | `rc` 0 | holds position; keeps the Tello from auto-landing (it does after 15 s without commands) |
| `go(x, y, z)`, `rc_for(x, y, z, yaw, seconds)` | | building blocks for your own patterns |

All have `speed=30` (cm/s, `goto` patterns) and `clockwise=True` where it makes sense.

`goto` patterns are precise (the drone measures the distance itself). `rc` patterns depend on how fast the drone flies
per stick unit: calibrate `orbit(cms_per_rc=..., deg_per_s_per_rc=...)` for your drone.
`goto` moves must be valid Tello moves: each axis ±500 cm (longer moves are split automatically), and **not all
axes within ±20 cm**, so a hexagon side must be at least 24 cm. Invalid patterns raise `ValueError` before the first move.

## Stopping and errors

- `cancel()` cancels the background pattern and sends `stop`, which interrupts a running Tello move at once.
- A pattern stops with `PatternAborted` when the drone reports an error during it (landed, not connected,
  Tello refused a move). In the background the status says `aborted`.
- Status on the bus: `ack.patterns.<drone_id>` `{"pattern", "status": "started" | "done" | "cancelled" | "aborted", "info"?}`.
- Every command carries `"source": "patterns"`, so your project can tell them from keyboard commands
  (see `more_examples/edu_search_and_rescue`).

## Examples

`more_examples/tello_patterns` (key 9 = next pattern), `edu_search_and_rescue` (lawnmower + interrupt),
`edu_multi_tello` (several drones at once), `edu_pad_pose_orbit` (orbit + dance).

## Your own pattern

```python
async def zigzag(patterns, legs=4, cm=60):
    for i in range(legs):
        await patterns.go(cm, cm if i % 2 == 0 else -cm)    # forward + left/right

patterns.start(zigzag(patterns))
```
