# Contributing

## Setup (VS Code)

1. `git clone -b dev https://github.com/lainwater/DroneFlightUltimate` (private repo: be logged in to GitHub in VS Code).
2. Import the profile `DFU.code-profile`: gear icon (bottom left) → *Profiles* → *Import Profile...* → restart VS Code.
3. `CTRL+Shift+P` → *Python: Create Environment* → *Quick Create*, then `pip install -e ".[all]"` (dev tools + YOLO).

## Lint and test

```bash
ruff check . --fix && ruff format . && pytest
```

Line length 150, rules E/F/I (`pyproject.toml`). Tests live in `tests/` mirroring `core/`, plus `tests/projects`,
`tests/tools`, `tests/more_examples`. They need **no hardware, no window, no network** beyond localhost:

- `tests/conftest.py` has a fake Tello (real UDP on 127.0.0.1): answers commands, sends state packets, can take time for moves
- the Vicon SDK is faked per test, the video window functions are replaced (`display_test.py`)
- every example and more_example is loaded and its config checked (`projects_test.py`)

Run `pytest` after editing a layout, a commands.json or an example config.

## Rules of the codebase

- **Modules only talk via the bus.** No `core.X` imports `core.Y`'s implementation. Factories (`get_*`) in each module's `__init__.py` are the public API.
- **Interfaces in `base.py`**, implementations in `implementations/`, capabilities in `commands.json` (action → method + default args).
- **Never block the event loop**: blocking SDK calls go in `asyncio.to_thread` or their own thread; threads publish via `asyncio.run_coroutine_threadsafe`.
- **Fail loudly on the bus**: publish `error.<...>` with `{"error", "message"}` instead of raising inside handlers.
- New bus topics: add them to the table in [concepts.md](concepts.md#bus-topics).

## Adding things

| What | Where |
|---|---|
| drone | [drone.md → Adding a drone](modules/drone.md#adding-a-drone) |
| keyboard / joystick layout | a `.json` next to the others, see [controller.md](modules/controller.md) |
| controller type | implement `ControllerBase` (incl. `controls_text()`), add to `ControllerType` + `get_controller` |
| video command | method on `CV2Display` + entry in `core/video/implementations/cv2/commands.json` |
| video output | implement `VideoBase`, add to `get_videostream` |
| camera calibration | `python -m tools.calibration ...`, commit the `.npz` |
| example | `projects/examples/<name>/` (basics/features) or `more_examples/<name>/` (task-style, prefix = drone needed), same structure as the others, add it to [examples.md](examples.md) |
| flight pattern | method on `FlightPatterns` (`core/patterns/flight_patterns.py`), built from `send` / `go` / `rc_for`; add a test in `tests/core/patterns` |
| Tello capability | `"models"` in `core/drone/implementations/DJI/tello/commands.json` |

## GitHub

Work on the `dev` branch (see setup) and open pull requests against it.
