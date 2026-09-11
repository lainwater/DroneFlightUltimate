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
├── pyproject.toml
├── LICENSE
├── README.md
├── run.py
| 
├── app/
|   ├── __init__.py
│   ├── main.py
│   └── app_conf/
│       └── active_project.toml
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
|   |       |   ├── __init__.py
│   │       │   ├── keyboard_controller.py
│   │       │   └── qwertz.json
│   │       └── repl_controller/
|   |           ├── __init__.py
│   │           ├── repl_controller.json
│   │           └── repl_controller.py
|   | 
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
│   │               ├── sim.py
│   │               └── stats.json
|   |
│   ├── fileops/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
|   |       ├── __init__.py
│   │       └── win_64x82.py
|   |
│   ├── logger/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── implementations/
|   |       ├── __init__.py
│   │       ├── gui_logger.py
│   │       ├── live.py
│   │       └── record.py
|   |
│   ├── player/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── jsonl_player.py
|   |
│   └── video/
│       ├── __init__.py
│       ├── base.py
│       ├── rec.py
│       ├── snapshot.py
│       └── implementations/
|           ├── __init__.py
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
│       │   │   │   └── defaults.toml
│       │   │   └── drone_config/
│       │   │       └── mydrone.json
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
│       │   │   │   └── defaults.toml
│       │   │   └── drone_config/
│       │   │       └── mydrone.json
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
│       └── template/
│           ├── commander/
│           │   └── main.py
│           ├── config/
│           │   ├── app_config/
│           │   │   └── defaults.toml
│           │   └── drone_config/
|           |       └── mydrone.json
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