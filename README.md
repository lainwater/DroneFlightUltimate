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
└── DroneFlightUltimate/
    ├── .gitignore
    ├── LICENSE
    ├── README.md
    ├── DOCS
    ├── xxxxxxxxxxxxxxxxxxxxxx xxxxxxxxxxxxxxxxxxxxxx 
    ├── app/
    │   ├── main.py
    │   └── app_conf/
    │       ├── __init__.py
    │       └── current.toml
    ├── xxxxxxxxxxxxxxxxxxxxxx xxxxxxxxxxxxxxxxxxxxx
    ├── projects/
    │   ├── examples/
    │   │   └── template/
    │   │       ├── commander
    │   │       ├── main.py
    │   │       ├── config/
    │   │       │   ├── app_config/
    │   │       │   │   ├── __init__.py
    │   │       │   │   └── defaults.toml
    │   │       │   └── drone_config/
    │   │       │       └── .json
    │   │       └── logs/
    │   │           ├── bus_logs/
    │   │           │   └── .jsonl
    │   │           ├── debug_logs/
    │   │           │   └── .log
    │   │           ├── pictures
    │   │           └── videos
    │   └── tests
    ├── xxxxxxxxxxxxxxxxxxxxxx xxxxxxxxxxxxxxxxxxxxxx     
    └── core/
        ├── drone/
        │   ├── __init__.py
        │   ├── base.py
        │   └── implementations/
        │       ├── DJI/
        │       │   └── Tello/
        │       │       ├── tello.py
        │       │       ├── stats.json
        │       │       └── mapping/?
        │       └── Sim/
        │           └── simdrone/
        │               ├── sim.py
        │               ├── stats.json
        │               └── mapping/?
        ├── xxxxxxxxxxxxxxxxxxxxxx         
        ├── controller/
        │   ├── __init__.py
        │   ├── base.py
        │   └── implementations/
        │       ├── repl_controller.py
        │       └── keyboard_controller/
        │           └── qwertz.py
        ├── xxxxxxxxxxxxxxxxxxxxxx     
        ├── video/
        │   ├── __init__.py
        │   ├── base.py
        │   └── implementations/
        │       ├── cv2_imp.py
        │       └── tkinter_imp.py
        ├── xxxxxxxxxxxxxxxxxxxxxx 
        ├── bus/
        │   ├── __init__.py
        │   └── base.py
        ├── xxxxxxxxxxxxxxxxxxxxxx 
        ├── fileops/
        │   ├── __init__.py
        │   ├── base.py
        │   └── implementations/
        │       └── win_64x82.py
        ├── xxxxxxxxxxxxxxxxxxxxxx 
        └── logger/
            ├── __init__.py
            ├── base.py
            └── implementations/
                ├── gui_logger.py
                ├── live.py
                └── record.py
```

---

### [Go to Top](#drone-flight-ultimate)