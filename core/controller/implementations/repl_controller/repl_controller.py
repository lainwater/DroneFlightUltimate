'''
REPLController - Operate drone via REPL.

On start it asks which drone type you are flying, loads that type's command
map from repl_commands/<type>.json and turns every typed command into a
message on the bus.

    Drone type: tello
    repl> takeoff
    repl> steps_move_forward distance=50
    repl> rc x=20 yaw=-10
'''

import asyncio
import difflib
import shlex
import threading
import traceback
from pathlib import Path
from typing import Optional

from core.controller.base import ControllerBase

try:
    import readline  # tab completion; not available on every platform
except ImportError:
    readline = None


class REPLController(ControllerBase):
    COMMANDS_DIR = Path(__file__).parent  # <drone_type>.json
    PROMPT = "repl> "

    def __init__(self, drone_id, bus, layout=None):
        super().__init__(drone_id, bus, layout)
        self._task = None
        self._completions = []

    async def start_controller(self):
        self.loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._repl())
        self._task.add_done_callback(self._log_task_exception)

    async def stop_controller(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    def _load_layout(self, layout: str = "simdrone") -> None:
        layout_path = Path(__file__).parent / f"{layout}.json"
        self.config = self.fops.read_json(layout_path)

    async def _publish_parser(self, type: str, data: dict) -> None:
        if self.bus:
            if type == "cmd":
                await self.bus.publish(f"cmd.{self.drone_id}", data)
            elif type == "stream":
                await self.bus.publish(f"stream.{self.drone_id}", data)
            elif type == "state":
                await self.bus.publish(f"state.REPL", data)

    # ------------------------------------------------------------ REPL loop
    async def _repl(self) -> None:
        self._setup_completion()
        drone_type = await self._choose_drone_type()
        if drone_type is None:
            return
        self._load_layout(drone_type)
        self._completions = sorted(self.config) + ["help", "exit"]
        print(f"Loaded {len(self.config)} commands for '{drone_type}'. Type 'help'.")

        while True:
            line = await self._ask(self.PROMPT)
            if line is None or not await self._handle_line(line):
                break
        print("REPL closed.")

    async def _choose_drone_type(self) -> Optional[str]:
        types = sorted(p.stem for p in self.COMMANDS_DIR.glob("*.json"))
        if not types:
            print(f"No drone command files found in {self.COMMANDS_DIR}")
            return None
        self._completions = types
        print("Drone types: " + ", ".join(types))
        while True:
            answer = await self._ask("Drone type: ")
            if answer is None or answer.strip() in ("exit", "quit"):
                return None
            answer = answer.strip().lower()
            if answer in types:
                return answer
            print(f"Unknown drone type '{answer}'.")

    async def _handle_line(self, line: str) -> bool:
        """Run one input line. Returns False when the REPL should exit."""
        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"Parse error: {e}")
            return True
        if not parts:
            return True
        name, tokens = parts[0], parts[1:]

        if name in ("exit", "quit"):
            return False
        if name == "help":
            self._print_help()
            return True
        if name not in self.config:
            close = difflib.get_close_matches(name, self.config, n=3)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            print(f"Unknown command '{name}'.{hint}")
            return True

        try:
            data = self._build_message(name, tokens)
        except ValueError as e:
            print(f"{name}: {e}")
            return True

        print(f"-> cmd.{self.drone_id} {data}")
        try:
            await self._publish_parser("cmd", data)
        except Exception:
            traceback.print_exc()  # a bus hiccup shouldn't kill the REPL
        return True

    # ------------------------------------------------------------- commands
    def _build_message(self, name: str, tokens: list) -> dict:
        """{"action": name}, or with key=value overrides
        {"action": name, "args": <JSON default args with overrides applied>}."""
        defaults = self.config[name].get("args", {})
        data = {"action": name}
        if not tokens:
            return data

        args = dict(defaults)
        for token in tokens:
            key, eq, raw = token.partition("=")
            if not eq:
                raise ValueError(f"expected key=value, got '{token}'")
            if key not in defaults:
                allowed = ", ".join(defaults) or "no arguments"
                raise ValueError(f"unknown argument '{key}' (takes: {allowed})")
            args[key] = self._coerce(raw, defaults[key])
        data["args"] = args
        return data

    @staticmethod
    def _coerce(raw: str, default):
        """Convert typed text to the type of the JSON default value."""
        if isinstance(default, bool):  # before int: bool is an int subclass
            low = raw.lower()
            if low in ("true", "1", "yes", "on"):
                return True
            if low in ("false", "0", "no", "off"):
                return False
            raise ValueError(f"'{raw}' is not a boolean")
        if isinstance(default, (int, float)):
            try:
                return type(default)(raw)
            except ValueError:
                raise ValueError(f"'{raw}' is not a valid {type(default).__name__}")
        return raw

    def _print_help(self) -> None:
        width = max(map(len, self.config)) + 2
        for name, spec in self.config.items():
            args = " ".join(f"{k}={v}" for k, v in spec.get("args", {}).items())
            print(f"  {name:<{width}}{args}")
        print(f"  {'help':<{width}}show this list")
        print(f"  {'exit':<{width}}leave the REPL")

    # ------------------------------------------------------------------ I/O
    def _ask(self, prompt: str):
        """input() in a daemon thread: never blocks the event loop and never
        keeps the process alive on shutdown (asyncio.to_thread would)."""
        fut = self.loop.create_future()

        def worker():
            try:
                line = input(prompt)
            except EOFError:
                line = None
            try:
                self.loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(line))
            except RuntimeError:  # loop already closed
                pass

        threading.Thread(target=worker, daemon=True).start()
        return fut

    def _setup_completion(self) -> None:
        if readline is None:
            return
        readline.set_completer(self._complete)
        if "libedit" in (readline.__doc__ or ""):  # macOS
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")

    def _complete(self, text: str, state: int):
        if " " in readline.get_line_buffer().lstrip():  # only complete the command name
            return None
        matches = [c for c in self._completions if c.startswith(text)]
        return matches[state] if state < len(matches) else None

    @staticmethod
    def _log_task_exception(task) -> None:
        """Background tasks swallow exceptions unless someone looks at them."""
        if not task.cancelled() and task.exception() is not None:
            exc = task.exception()
            traceback.print_exception(type(exc), exc, exc.__traceback__)