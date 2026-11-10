"""
# run.py - single entry point for DroneFlightUltimate: create and run projects.

## CLI
    python run.py create -n <name>              new project in projects/<name> (template)
    python run.py run -n <name>                 run projects/<name>
    python run.py run -e                        list projects/examples
    python run.py run -e -n <example>           run projects/examples/<example>
    python run.py run -m                        list more_examples
    python run.py run -m -n <example>           run more_examples/<example>
    python run.py run -n <name> -p <folder>     run <folder>/<name>

    Short forms: c = create, r = run.  -e, -m and -p can't be combined.

## From Python
    create_project(name, path=None)
    run_project(name, path=None, _type=None)    _type: None, "example" or "more"
    get_examples() / get_more_examples()        names
"""

import argparse
import asyncio
from pathlib import Path

from projects import get_project

ROOT = Path(__file__).resolve().parent
PROJECTS = ROOT / "projects"
EXAMPLES = PROJECTS / "examples"
MORE_EXAMPLES = ROOT / "more_examples"

_SOURCES = {"example": EXAMPLES, "more": MORE_EXAMPLES}


def _list(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return sorted(p.name for p in folder.iterdir() if (p / "commander" / "main.py").exists())


def get_examples() -> list[str]:
    return _list(EXAMPLES)


def get_more_examples() -> list[str]:
    return _list(MORE_EXAMPLES)


def create_project(project_name: str, path: Path | None = None) -> None:
    get_project(project_name, path or PROJECTS)


def run_project(project_name: str, path: Path | None = None, _type: str | None = None) -> None:
    if isinstance(_type, str) and _type.lower() in _SOURCES:
        path = _SOURCES[_type.lower()]
    project = get_project(project_name, path or PROJECTS)
    try:
        asyncio.run(project.run())
    except KeyboardInterrupt:
        pass


def _print_list(title: str, names: list[str]) -> None:
    print(title)
    for name in names:
        print(f"  - {name}")


def cli_usage() -> None:
    parser = argparse.ArgumentParser(
        description="DroneFlightUltimate project manager", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", aliases=["c"], help="create a new project in projects/")
    create.add_argument("-n", "--name", default="new_project", help="name of the project")

    run = sub.add_parser("run", aliases=["r"], help="run a project")
    run.add_argument("-n", "--name", default=None, help="name of the project")
    where = run.add_mutually_exclusive_group()
    where.add_argument("-e", "--example", action="store_true", help="from projects/examples")
    where.add_argument("-m", "--more", action="store_true", help="from more_examples")
    where.add_argument("-p", "--path", type=Path, help="folder that contains the project")

    args = parser.parse_args()

    if args.command in ("create", "c"):
        print(f"Creating project '{args.name}' in {PROJECTS} ...")
        create_project(args.name)
        return

    if args.example or args.more:
        folder, names, title = (EXAMPLES, get_examples(), "examples") if args.example else (MORE_EXAMPLES, get_more_examples(), "more_examples")
        if args.name is None or args.name not in names:  # never scaffold an empty project inside an examples folder
            if args.name is not None:
                print(f"No example '{args.name}'.")
            _print_list(f"Available {title}:", names)
            return
        path = folder
    elif args.path is not None:
        path = args.path.resolve()
    else:
        path = PROJECTS
        if args.name is None:
            parser.error("run needs -n <name> (or -e / -m to list examples)")

    print(f"Running project '{args.name}' from {path} ...")
    run_project(args.name, path)


if __name__ == "__main__":
    cli_usage()
