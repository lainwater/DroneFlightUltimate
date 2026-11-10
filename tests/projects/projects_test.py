"""projects loader, ProjectBase helpers, run.py and every example's config."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
import toml

import run
from core.controller.implementations.keyboard_controller.get_layout import available_layouts
from core.drone import DroneType
from core.drone.implementations.DJI.tello.tello import normalize_model
from core.logger import LogLevel
from projects import get_project

ROOT = Path(__file__).resolve().parents[2]
JOYSTICK_LAYOUTS = {p.stem for p in (ROOT / "core/controller/implementations/joystick_controller").glob("*.json")}
ALL_PROJECTS = [(ROOT / "projects/examples", n) for n in run.get_examples()] + [(ROOT / "more_examples", n) for n in run.get_more_examples()]


def test_examples_are_listed():
    assert len(run.get_examples()) == 12
    assert "tello_patterns" in run.get_more_examples() and len(run.get_more_examples()) == 11


@pytest.mark.parametrize("folder, name", ALL_PROJECTS, ids=lambda x: x if isinstance(x, str) else "")
def test_every_example_loads_and_is_configured(folder, name):
    project = get_project(name, folder)
    main = (folder / name / "commander" / "main.py").read_text()
    assert main.startswith('"""') and "## Run" in main, "docstring with how to run"
    assert isinstance(project.log_level, LogLevel)
    layout = project.app_config.get("controller", {}).get("layout")
    if layout is not None:
        assert layout in set(available_layouts()) | JOYSTICK_LAYOUTS
    for key, conf in project.drone_config.items():
        assert key.startswith("drone_")
        assert DroneType[conf["drone_type"].upper()]
        normalize_model(conf.get("model"))  # raises if unknown
    calib = project.app_config.get("video", {}).get("calibration")
    if calib:
        assert (ROOT / "core/video/calibration" / f"{calib}.npz").exists()


def test_scaffold_new_project(tmp_path):
    project = get_project("mytest", tmp_path)
    for p in ("commander/main.py", "commander/__init__.py", "config/defaults.toml", "config/mydrone.json", "logs/bus_logs", "logs/media"):
        assert (tmp_path / "mytest" / p).exists()
    assert project.app_config["controller"]["layout"] == "keyboard"
    assert type(project).__name__ == "mytest"


def test_create_drone_passes_every_field(tmp_path):
    project = get_project("p", tmp_path)
    (tmp_path / "p/config/mydrone.json").write_text(
        json.dumps({"drone_1": {"drone_type": "dji_tello", "drone_id": "x", "ip": "10.0.0.5", "model": "edu", "cmd_pc_port": 9123}})
    )
    project.drone_config = project.load_drone_config()
    drone = project.create_drone()
    assert (drone.drone_id, drone.ip, drone.model, drone.cmd_pc_port) == ("x", "10.0.0.5", "tello_edu", 9123)


def test_log_level(tmp_path):
    project = get_project("p", tmp_path)
    project.app_config["logging"]["level"] = "debug"
    assert project.log_level == LogLevel.DEBUG
    project.app_config["logging"]["level"] = "LOUD"
    with pytest.raises(ValueError):
        project.log_level


def test_shutdown_drone_lands_and_disconnects(tmp_path):
    project = get_project("p", tmp_path)

    async def scenario():
        drone = project.create_drone()
        drone.sdk._wait_time = 0.0
        for action in ("connect", "set_arm", "takeoff"):
            await project.bus.publish(f"cmd.{drone.drone_id}", {"action": action})
        await project.shutdown_drone(drone)
        return drone.flight_state.value, drone.con_state.value

    assert asyncio.run(scenario()) == ("landed", "disconnected")


def test_helper_files_and_same_named_helpers(tmp_path):
    for name, value in (("a", 1), ("b", 2)):
        get_project(name, tmp_path)
        (tmp_path / name / "commander" / "helper.py").write_text(f"VALUE = {value}\n")
        main = tmp_path / name / "commander" / "main.py"
        main.write_text(main.read_text().replace("import asyncio\n", "import asyncio\n\nfrom helper import VALUE\n", 1))
    assert sys.modules[type(get_project("a", tmp_path)).__module__].VALUE == 1
    assert sys.modules[type(get_project("b", tmp_path)).__module__].VALUE == 2  # not a's cached helper


def test_class_name_fallback(tmp_path):
    get_project("folder_name", tmp_path)
    main = tmp_path / "folder_name" / "commander" / "main.py"
    main.write_text(main.read_text().replace("class folder_name(", "class OtherName("))
    assert type(get_project("folder_name", tmp_path)).__name__ == "OtherName"


def test_cli_lists_and_never_scaffolds_into_examples(monkeypatch, capsys):
    for argv in (["run.py", "run", "-e"], ["run.py", "run", "-m", "-n", "typo"]):
        monkeypatch.setattr(sys, "argv", argv)
        run.cli_usage()
    out = capsys.readouterr().out
    assert "simdrone_keyboard" in out and "No example 'typo'" in out and "tello_patterns" in out
    assert not (ROOT / "more_examples" / "typo").exists()


def test_toml_configs_parse():
    for path in list(ROOT.glob("projects/examples/*/config/defaults.toml")) + list(ROOT.glob("more_examples/*/config/defaults.toml")):
        toml.load(path)
