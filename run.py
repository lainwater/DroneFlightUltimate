"""
run.py - single entry point for DroneFlightUltimate.

Usage:
    python run.py create <project_name>    (shorthand c)
        Creates a new project dir scaffolded with provided name, defaults to "new_project" if none provided.

    python run.py run <project_name>    (shorthand: r)
        Run a project (will create it if it doesn't exist.)
"""

import asyncio
import sys
from pathlib import Path

from projects import get_project

ROOT = Path(__file__).resolve().parent

ERROR_MSG = """You did something wrong calling run.py
    Usage:

        `python run.py create <project_name>`    (shorthand c)
            Creates a new project dir scaffolded with provided name, defaults to "new_project" if none provided.

        `python run.py run <project_name>`    (shorthand: r)
            Run a project (will create it if it doesn't exist.)
"""


def main() -> None:
    args = sys.argv
    if len(args) < 2 or len(args) > 3:
        raise SyntaxError(ERROR_MSG)

    name = "new_project"
    if len(args) == 3:
        name = args[2]

    if args[1] == "create" or args[1] == "c":
        print(f"Starting project '{name}'...")
        project = get_project(name)
        return
    if args[1] == "run" or args[1] == "r":
        print(f"Starting project '{name}'...")
        project = get_project(name)
        asyncio.run(project.run())

    if args[1] != "run" or args[1] != "create":
        raise SyntaxError(ERROR_MSG)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
