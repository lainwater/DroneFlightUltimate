"""
run.py - single entry point for DroneFlightUltimate.

Usage:
    python run.py
        Runs whichever project app/app_conf/active_project.toml points at.

    python run.py <project_name>
        Runs that project explicitly, overriding active_project.toml.
        If it doesn't exist yet under projects/examples/, it gets
        scaffolded (see projects.get_project()).
"""

import asyncio
import sys
import tomllib
from pathlib import Path

from projects import get_project

ROOT = Path(__file__).resolve().parent
ACTIVE_PROJECT_PATH = ROOT / "app" / "app_conf" / "active_project.toml"


def resolve_project_name() -> str:
    """A CLI argument always wins. Otherwise fall back to whatever
    active_project.toml points at."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    try:
        with open(ACTIVE_PROJECT_PATH, "rb") as f:
            config = tomllib.load(f)
        return config["active"]["project"]
    except KeyError:
        return "new_project"


def main() -> None:
    name = resolve_project_name()
    print(f"Starting project '{name}'...")
    project = get_project(name)
    asyncio.run(project.run())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")