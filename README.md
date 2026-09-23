# Drone Flight Ultimate
> <...>

---

## Table of Contents
- [About](#about)
    - [What for?](#what-for)
    - [Core ideas](#core-ideas)
    - [Module descriptions](#module-descriptions)
    - [Module interactions](#module-interactions)
    - [File Structure](#file-structure)

- [How to use](#how-to-use)
    - [Setup](#setup)
    - [Make a project](#make-a-project)
    - [Run a project](#run-a-project)
    - [Hints](#hints)

- [Contribute](#contribute)
    - [Setup VSCode](#setup-vscode)
    - [Lint and Test](#lint-and-test)
    - [What can be edited easily](#what-can-be-edited-easily)

- [To-Do](#to-do)
    - [Important](#important)
    - [Less Important](#less-important)
    - [Future](#future)
    - [Known Issues](#known-issues)

- [Contributors & Licensing](#contributors--licensing)

---
---

# About
> <...>

### In this section
- [What for?](#what-for)
- [Core ideas](#core-ideas)
- [Module descriptions](#module-descriptions)
- [Module interactions](#module-interactions)
- [File Structure](#file-structure)
    - [Tree](#tree)

## What for?
<...>

## Core ideas
<...>

## Module descriptions
<...>

## Module interactions
<...>

## File Structure
> Core, Projects - tests, top-level

### Tree
```text
.
├── DFU.code-profile
├── LICENSE
├── pyproject.toml
├── README.md
├── run.py
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
│   │   ├── schema.py
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
│   │       ├── joystick_controller/
│   │       │   ├── __init__.py
│   │       │   ├── joystick_controller.py
│   │       │   └── t8l.json
│   │       │
│   │       ├── keyboard_controller/
│   │       │   ├── __init__.py
│   │       │   ├── get_layout.py
│   │       │   ├── keyboard_controller.py
│   │       │   ├── qwerty.json
│   │       │   └── qwertz.json
│   │       │
│   │       └── repl_controller/
│   │           ├── __init__.py
│   │           ├── repl_controller.py
│   │           ├── simdrone.json
│   │           └── tello.json
│   │
│   ├── drone/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── position_and_attitude.py
│   │   └── implementations/
│   │       ├── DJI/
│   │       │   └── tello/
│   │       │       ├── __init__.py
│   │       │       ├── commands.json
│   │       │       ├── stats.json
│   │       │       ├── tello.py
│   │       │       └── tellosdk.py
│   │       │
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
│   │   ├── errors.py
│   │   └── implementations/
│   │       ├── __init__.py
│   │       ├── common.py
│   │       ├── darwin.py
│   │       ├── linux.py
│   │       └── windows.py
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
│   └── video/
│       ├── __init__.py
│       ├── base.py
│       ├── rec.py
│       ├── snapshot.py
│       └── implementations/
│           ├── cv2_display.py
│           └── tkinter_display.py
│
├── projects/
│   ├── __init__.py
│   ├── base.py
│   ├── example_project/
│       ├── commander/
│       │   ├── __init__.py
│       │   └── main.py
│       └── config/
│           ├── defaults.toml
│           └── mydrone.json
│       └── logs/
│           ├── bus_logs/
│           │   └── <date>.jsonl
│           ├── videos/
│           └── pictures/ 
│
├── tests/
│   └── core/
│       ├── bus/
│       │   └── bus_test.py
│       ├── bus_player_recorder/
│       │   └── player_test.py
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
│       └── video/
│           └── video_test.py
```

---
---

# How to use
> <...>

### In this section
- [Setup](#setup)
- [Make a project](#make-a-project)
- [Run a project](#run-a-project)
- [Hints](#hints)

## Setup
1. Clone the rep (you need to be logged into GitHub on VSCode while DFU is a private rep!)
    -> Run `git clone https://github.com/lainwater/DroneFlightUltimate` where you want to install it.

2. Setup env by
    -> run `pip install -e .` in your env

## Make a project
->  create a new project by running python `run.py create <project_name>`
    -> Navigate to `projects/<project_name>/commander/main.py`
    -> There you can edit `setup()` `main()` and `end_run()` to your needs

## Run a project
in the folder open the terminal and type
    `python run.py run <project_name>`

## Hints
<...>

---
---

# Contribute
> How to contribute

### In this section
- [Setup VSCode](#setup-vscode)
- [Lint and Test](#lint-and-test)
- [What can be edited easily](#what-can-be-edited-easily)

## Setup VSCode
1. Clone the rep (you need to be logged into GitHub on VSCode while DFU is a private rep!)
    -> Run `git clone -b dev https://github.com/lainwater/DroneFlightUltimate` where you want to install it.

2. Import code profile: `DFU.code-profile` by
    -> clicking bottom left on `Gear-wheel-icon` -> `Profile` -> `Profiles`
    -> Click on `More actions` (arrow down) next to `Import Profile` -> `Import Profile...`
    -> Select the file and continue
    -> Make sure all extensions are loaded correctly. Restart VSCode to make sure.

3. Create a Python virtual enviorment by
    -> `CTRL + Shift + P` and type `Python: Create Enviorment` and hit `Quick Create`.
    -> This will install all dependencies and setup your venv.
    -> If it did not get all dependencies run `pip install -e ".[dev]"` in your project path

## Lint and Test
`ruff check . --fix && ruff format . && pytest`

## What can be edited easily
Adding implementations in core/.../implementations should be easy as long as you add it to its `__init__.py.get<...>` by adding another case there.
It must fullfill its `base.py` and work in the way other files expect it to, at least listening and publishing to bus.

---
---

# To-Do
> Here you find everything i want to add, issues and similar.

### In this section
- [Important](#important)
- [Less Important](#less-important)
- [Future](#future)
- [Known Issues](#known-issues)

## Important
### Features
- [ ] add video/stream output
    -> [ ] to web server
    -> [ ] vr mode (jsut the screen twice for a cardbox vr or similar)
    -> [ ] idk what else output cv2?
- [ ] implement video output for(start/stop stream)
    -> [ ] simdrone
    -> [ ] tello
- [ ] add/edit example projects:
    - [ ] ~~tello repl,~~
    - [x] simdrone keyboard,
    - [ ] ~~simdrone repl,~~
    - [x] simdrone t8l,
    - [ ] multi tello/simdrone with keyboard,
    - [ ] all with video support
- [ ] add premade flight patterns (new core module)
    - [ ] fly shapes: square, circle, triangle, hexagon
    - [ ] fly waypoints (dict of xyz + speed);
    - [ ] search grids of shapes: square, circle, triangle, hexagon (resolution, how small grid-areas are) (single, multi)
    - [ ] tests for it
- [x] add linux fops

### Utils
- [ ] a scafhold/template drone.py
- [ ] implement tests for each core module
- [ ] look over everything
    - [x] remove deadcode, reduency, overcomplicated things
    - [x] prettyfie (linter :))
    - [ ] add standardized and simple docstrings
- [ ] write docs for each core module and for the whole project in /docs/...
- [ ] Finish the readme fully


## Less Important
### Features
- [ ] add repl controller

### Utils
- [ ] get a proper license
- [ ] setup github for colabreation ()
    - [ ] CI (lint+run tests)
    - [ ] issue tags
    - [ ] versions
- [ ] add pdf or powerpoint/similar presentations (for non-tech people, for techy people, for using, for collabing)
- [ ] present to my profs
- [ ] make github public


## Future
- [ ] web ui for handling projects or an app (other repo, make a project)
- [ ] more controllers (joystick ones mainly)
- [ ] more drones (parrot mambo,..)

## Known Issues
- There is some weird async timing bug i havent been able to recreate.


---
---

# Contributors & Licensing
> Owned, innitated, maintained and licensed by `Valerie Lain`.

---
---

[Go to Top](#drone-flight-ultimate)