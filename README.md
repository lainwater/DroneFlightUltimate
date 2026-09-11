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
├── .venv/
├── DroneFlightUltimate.toml
├── LICENESE
├── README.md
├── run.py
| 
├── app/
│   ├── main.py
│   └── app_conf/
│       ├── __init__.py
│       └── current.toml
| 
├── core/
│   ├── bus/
│   │   ├── __init__.py
│   │   └── base.py
|   |
│   ├── controller/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── keyboard_controller/
│   │       │   ├── keyboard_controller.py
│   │       │   └── qwertz.json
│   │       └── repl_controller/
│   │           ├── repl_controller.json
│   │           └── repl_controller.py
|   | 
│   ├── drone/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── DJI/
│   │       │   └── tello/
│   │       │       ├── commands.json
│   │       │       ├── stats.json
│   │       │       └── tello.py
│   │       └── Sim/
│   │           └── simdrone/
│   │               ├── commands.json
│   │               ├── sim.py
│   │               └── stats.json
│   ├── fileops/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       └── win_64x82.py
|   |
│   ├── logger/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
│   │       ├── gui_logger.py
│   │       ├── live.py
│   │       └── record.py
|   |
│   ├── player/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── jsonl_playe.py
|   |
│   └── video/
│       ├── __init__.py
│       ├── base.py
│       ├── rec.py
│       ├── snapshot.py
│       └── impementations/
│           ├── cv2_display.py
│           └── tkinter_display.py
|
├── projects/
│   └── examples/
│       ├── replay_flight/
│       │   ├── commander/
│       │   │   └── main.py
│       │   ├── config/
│       │   │   ├── app_config/
│       │   │   │   ├── __init__.py
│       │   │   │   └── defaults.toml
│       │   │   └── drone_config/
│       │   └── logs/
│       │       ├── bus_logs/
│       │       │   ├── .gitkeep
│       │       │   └── .jsonl
│       │       ├── debug_logs/
│       │       │   ├── .gitkeep
│       │       │   └── .log
│       │       ├── pictures/
│       │       │   └── .gitkeep
│       │       └── videos/
│       │           └── .gitkeep
|       |
│       ├── single_drone_kb_and_vid/
│       │   ├── commander/
│       │   │   └── main.py
│       │   ├── config/
│       │   │   ├── app_config/
│       │   │   │   ├── __init__.py
│       │   │   │   └── conf.toml
│       │   │   └── drone_config/
│       │   │       └── my_tello_conf.json
│       │   └── logs/
│       │       ├── bus_logs/
│       │       │   └── .jsonl
│       │       ├── debug_logs/
│       │       │   └── .log
│       │       ├── pictures/
│       │       └── videos/
|       |
│       └── template/
│           ├── commander/
│           │   └── main.py
│           ├── config/
│           │   ├── app_config/
│           │   │   ├── __init__.py
│           │   │   └── defaults.toml
│           │   └── drone_config/
│           └── logs/
│               ├── bus_logs/
│               │   ├── .gitkeep
│               │   └── .jsonl
│               ├── debug_logs/
│               │   ├── .gitkeep
│               │   └── .log
│               ├── pictures/
│               │   └── .gitkeep
│               └── videos/
│                   └── .gitkeep
└── tests/
    └── core/
        ├── bus/
        │   └── bus_test.py
        ├── controller/
        │   └── controller_test.py
        ├── drone/
        │   ├── DJI/
        │   │   └── tello/
        │   │       └── tello_test.py
        │   └── Sim/
        │       └── simdrone/
        │           └── simdrone_test.py
        ├── fileops/
        │   └── fileops_test.py
        ├── logger/
        │   └── logger_test.py
        ├── player/
        │   └── player_test.py
        └── video/
            └── video_test.py
```

---

### [Go to Top](#drone-flight-ultimate)