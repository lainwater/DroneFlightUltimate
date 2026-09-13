"""
public API of projects
"""

import importlib
from pathlib import Path
from .base import ProjectBase

# Corrected: .parent is a property, not a method
PROJECT_ROOT = Path(__file__).resolve().parent

project_template_layout: dict = {
    "commander/": {
        "init": "__init__.py",
        "main": "main.py"
    },
    "config/": {
        "app_config": "defaults.toml",
        "drone_config": "mydrone.json"
    },
    "logs/": {
        "pics_folder": "pictures/",
        "videos_folder": "videos/"
    }
}

project_app_defaultstoml = """
[logging]
level = "INFO"
 
[keyboard]
layout = ""
"""

project_drone_default = """
{
  "drone_type": "sim_simdrone",
  "drone_id": "drone1",
  "ip": "127.0.0.1"
}
"""

project_main_template = """
import asyncio

from projects.base import ProjectBase
from core.logger import LogLevel, LoggerType
from core.controller import ControllerType, get_controller
from core.drone import DroneType, get_drone

class new_project(ProjectBase):
    async def setup(self) -> None:
        self.recorder.attach(self.bus)
        self.bus.subscribe("*", lambda topic, data: self.live_logger.log(LogLevel.INFO, f"{topic}: {data}"))

        drone_config = self.load_drone_config(self.root_path)
        drone_type = DroneType[self.drone_config["drone_type"].upper()]
        self.drone = get_drone(
            drone_type,
            drone_config["drone_id"],
            bus=self.bus,
            ip=drone_config["ip"],
        )

        layout = self.app_config.get("keyboard", {}).get("layout") or None
        self.controller = get_controller(
            ControllerType.KEYBOARD_CONTROLLER,
            drone_id=self.drone_config["drone_id"],
            bus=self.bus,
            layout=layout,
        )

    async def main(self) -> None:
        self.debug_logger.log(LogLevel.INFO, "Session starting", drone_id=self.drone.drone_id)
        await self.controller.start_controller()

        print(f"Keyboard controller active for '{self.drone.drone_id}'. Press Ctrl+C to stop.")
        try:
            await asyncio.Event().wait()  # keep the event loop alive until interrupted
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            self.end_run()

    async def end_run(self) -> None:
        self.debug_logger.log(LogLevel.INFO, "Session ending", drone_id=self.drone.drone_id)
        self.controller.stop_controller()
        self.recorder.detach(self.bus)
        self.drone.detach()
"""

def get_project(
    name: str = "new_project",
    path: Path = PROJECT_ROOT,
    **kwargs
) -> ProjectBase:
    """Gets a project if it exists, else creates a new one."""
    project_dir = Path(path).resolve() / name

    # 1. Try dynamic import if the project already exists
    try:
        module = importlib.import_module(f"{name}.commander.main")
        project_cls = getattr(module, name)
        return project_cls(path, **kwargs)
    except (ImportError, AttributeError):
        pass

    # 2. Build the project folder structure using your fileops implementation
    from core.fileops import get_fileops
    fops = get_fileops()

    for folder_rel_path, contents in project_template_layout.items():
        # Ensure top-level directory (e.g., project_dir / "commander") exists
        target_dir = fops.ensure_dir(project_dir / folder_rel_path)
        
        for key, item_name in contents.items():
            target_path = target_dir / item_name
            
            if item_name.endswith("/"):
                # Item is a sub-directory (e.g., "logs/pictures/")
                fops.ensure_dir(target_path)
            else:
                # Item is a file (e.g., "defaults.toml")
                fops.ensure_dir(target_path.parent)
                if not target_path.exists():
                    target_path.touch()
                    
    f = Path(path) / "commander" / "main.py"
    with open(f, "w", encoding="UTF-8"):
        f.write_text(project_main_template)
    f = Path(path) / "config" / "defaults.toml"
    with open(f, "w", encoding="UTF-8"):
        f.write_text(project_app_defaultstoml)
    f = Path(path) / "commander" / "mydrone.json"
    with open(f, "w", encoding="UTF-8"):
        f.write_text(project_drone_default)
    
    # 3. Import and return the newly instantiated project object
    module = importlib.import_module(f"{name}.commander.main")
    project_cls = getattr(module, name)
    return project_cls(path, **kwargs)


__all__ = ["get_project"]