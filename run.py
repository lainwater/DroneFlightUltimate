"""
# run.py - single entry point for DroneFlightUltimate.

## Usage:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="DroneFlightUltimate project manager")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # create
    create_parser = subparsers.add_parser("create", aliases=["c"], help="Create a new project")
    create_parser.add_argument("-n", "--name", default="new_project", help="Name of the project")

    # run
    run_parser = subparsers.add_parser("run", aliases=["r"], help="Run a project")
    run_parser.add_argument("-n", "--name", default=None, help="Name of the project")

    location = run_parser.add_mutually_exclusive_group()
    location.add_argument("-e", "--example", action="store_true", help="Use a project from projects/examples")
    location.add_argument("-p", "--path", type=Path, help="Path to the project without project name")

    args = parser.parse_args()

    # check
    if args.command in ("create", "c"):
        path = PROJECTS
        print(f"Creating project '{args.name}' at {path}...")
        get_project(args.name, path)
        return

    if args.command in ("run", "r"):
        if args.example:
            examples = get_examples()
            if args.name is None:
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


def get_examples() -> list[str]:
    if not EXAMPLES.exists():
        return []

    return sorted(project.name for project in EXAMPLES.iterdir() if project.is_dir())


if __name__ == "__main__":
    main()
