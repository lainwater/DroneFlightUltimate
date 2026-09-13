# Drone Flight Ultimate

Short Description

---

## Table of Contents
- [About](#about)
- [File Structure](#file-structure)

---

## About
blahblah

---

## File Structure

```
.
├── .gitignore
├── LICENSE
├── README.md
├── pyproject.toml
├── run.py
|
|
├── app/
│   ├── __init__.py
│   ├── app_conf/
│   │   └── active_project.toml
│   └── main.py
|
│
├── core/
│   ├── bus/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── __init__.py
│   │       └── simple_bus.py
│   │ 
│   ├── bus_player_recorder/
│   │   ├── __init__.py
│   │   ├── player_base.py
│   │   ├── recorder_base.py
│   │   └── implementations/
│   │       └── jsonl/
│   │           ├── __init__.py
│   │           ├── bus_player.py
│   │           └── bus_recorder.py
│   │ 
│   ├── controller/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── keyboard_controller/
│   │       │   ├── __init__.py
│   │       │   ├── get_layout.py
│   │       │   ├── keyboard_controller.py
│   │       │   └── qwertz.json
│   │       └── repl_controller/
│   │           ├── __init__.py
│   │           ├── repl_controller.json
│   │           └── repl_controller.py
│   │ 
│   ├── drone/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── DJI/
│   │       │   └── tello/
│   │       │       ├── __init__.py
│   │       │       ├── commands.json
│   │       │       ├── stats.json
│   │       │       └── tello.py
│   │       └── Sim/
│   │           └── simdrone/
│   │               ├── __init__.py
│   │               ├── commands.json
│   │               ├── simdrone.py
│   │               ├── simdronesdk.py
│   │               └── stats.json
│   │ 
│   ├── fileops/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── __init__.py
│   │       └── win_64x82.py
│   │ 
│   ├── logger/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── __init__.py
│   │       ├── jsonl_logger.py
│   │       ├── live_console.py
│   │       └── no_logger.py
│   │ 
│   ├── video/
│       ├── __init__.py
│       ├── base.py
│       ├── rec.py
│       ├── snapshot.py
│       └── implementations/
│           ├── __init__.py
│           ├── cv2_display.py
│           └── tkinter_display.py
│
|
├── projects/
│   └── examples/
│       ├── __init__.py
│       ├── base.py
│       ├── single_drone_kb_and_vid/
│           ├── commander/
│           │   ├── __init__.py
│           │   └── main.py
│           ├── config/
│           │   ├── app_config/
│           │   │   └── defaults.toml
│           │   └── drone_config/
│           │       └── mydrone.json
│           └── logs/
│               ├── bus_logs/
│               │   └── flight.jsonl
│               ├── debug_logs/
│               │   └── session.jsonl
│               ├── pictures/
│               └── videos/
|
├── tests/
│   └── core/
│       ├── bus/
│       │   └── bus_test.py
│       ├── controller/
│       │   └── controller_test.py
│       ├── drone/
│       │   ├── DJI/
│       │   │   └── tello/
│       │   │       └── tello_test.py
│       │   └── Sim/
│       │       └── simdrone/
│       │           └── simdrone_test.py
│       ├── fileops/
│       │   └── fileops_test.py
│       ├── logger/
│       │   └── logger_test.py
│       ├── player/
│       │   └── player_test.py
│       └── video/
│           └── video_test.py
|
├── droneflightultimate.egg-info/
│   └── generated metadata files
|
└── .venv/
    └── project environment
```

---

### [Go to Top](#drone-flight-ultimate)