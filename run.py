"""
# run.py - single entry point for DroneFlightUltimate. Provides entry by command line interface (CLI) or by function call.

## Programmatic Usage:
    ### Create a project:
        create_project(project_name: str, path: Path | None = None) -> None
            Creates a new project with the given name at the given path.
            If no path is provided, the project will be created in the default projects directory.

    ### Run a project:
        run_project(project_name: str, path: Path | None = None, _type: str | None = None) -> None
            Runs the project with the given name at the given path.
            If no path is provided, the project will be run from the default projects directory.
            The `_type` parameter can be used to specify the type of project to run ("example" or None)

    ### Get a list of examples:
        get_examples() -> list[str]

## CLI Usage:
    ### Create a project:
        python run.py create
        python run.py create -n <project_name>

    ### Run a project:
        python run.py run -n <project_name>
        python run.py run -n <example_name> -e
        python run.py run -n <project_name> -p <path>

    ### Short aliases:
        create -> c
        run    -> r
        example -> e
        path    -> p

    Examples:
        python run.py create
            Creates "projects/new_project".

        python run.py create -n myproject
            Creates "projects/myproject".

        python run.py run -n myproject
            Runs "projects/myproject".

        python run.py run -n tello_t8l -e
            Runs "projects/examples/tello_t8l".

        python run.py run -e
            Gives you list of examples in "project/examples/"

        python run.py run -n myproject -p /some/path
            Runs "/some/path/myproject".

    Note:
        --example (-e) and --path (-p) cannot be used together.
"""

import argparse
import asyncio
from pathlib import Path

from projects import get_project

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
EXAMPLES = PROJECTS / "examples"


######################################################
##### Functions for programmatic usage of run.py #####
######################################################


def create_project(project_name: str, path: Path | None = None) -> None:
    if path is None:
        path = PROJECTS
    get_project(project_name, path)


def run_project(project_name: str, path: Path | None = None, _type: str | None = None) -> None:
    if path is None:
        path = PROJECTS
    if _type is not None and type(_type) is str:
        if _type.lower() == "example":
            path = EXAMPLES
    project = get_project(project_name, path)
    try:
        asyncio.run(project.run())
    except KeyboardInterrupt:
        pass


######################################################
#####  Functions for both programmatic and CLI   #####
######################################################


def get_examples() -> list[str]:
    if not EXAMPLES.exists():
        return []

    return sorted(project.name for project in EXAMPLES.iterdir() if project.is_dir())


######################################################
#####   Entry point and Functions for CLI usage  #####
######################################################


def cli_usage() -> None:
    # get args
    parser = argparse.ArgumentParser(description="DroneFlightUltimate project manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create arg parse
    create_parser = subparsers.add_parser("create", aliases=["c"], help="Create a new project")
    create_parser.add_argument("-n", "--name", default="new_project", help="Name of the project")

    # run arg parse
    run_parser = subparsers.add_parser("run", aliases=["r"], help="Run a project")
    run_parser.add_argument("-n", "--name", default=None, help="Name of the project")
    location = run_parser.add_mutually_exclusive_group()
    location.add_argument("-e", "--example", action="store_true", help="Use a project from projects/examples")
    location.add_argument("-p", "--path", type=Path, help="Path to the project without project name")

    # get args
    args = parser.parse_args()

    # check args for create
    if args.command in ("create", "c"):
        path = PROJECTS
        print(f"Creating project '{args.name}' at {path}...")
        get_project(args.name, path)
        return

    # check args for run
    if args.command in ("run", "r"):
        if args.example:
            examples = get_examples()
            if args.name is None:  # print list of examples if no name is provided
                print("Available examples:")
                for example in examples:
                    print(f"  - {example}")
                return
            path = EXAMPLES
        elif args.path is not None:
            path = args.path.resolve()
        else:
            path = PROJECTS
        print(f"Running project '{args.name}' at {path}...")
        project = get_project(args.name, path)
        try:
            asyncio.run(project.run())
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    cli_usage()
