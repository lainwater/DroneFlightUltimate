"""
KeyboardController - Controller implementation for keyboard control unsing pynput.keyboard.
"""

import asyncio

from pynput import keyboard

from core.controller.base import ControllerBase
from core.controller.implementations.keyboard_controller.get_layout import current_keyboard_layout_as_json_path


class KeyboardController(ControllerBase):
    def __init__(self, drone_id, bus, layout):
        super().__init__(drone_id, bus, layout)
        self.kb_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._held_axes = {"x": 0.0, "y": 0.0, "z": 0.0, "yaw": 0.0}

    async def start_controller(self):
        self.loop = asyncio.get_running_loop()
        self.kb_listener.start()

    async def stop_controller(self):
        self.kb_listener.stop()

    def _load_layout(self, layout: str) -> None:
        layoutpath = current_keyboard_layout_as_json_path(layout)
        self.config = self.fops.read_json(layoutpath)

    async def _publish_parser(self, data: dict) -> None:
        if self.bus:
            if hasattr(data, "error"):
                await self.bus.publish(f"error.Keyboard.{self.drone_id}", data)
            else:
                await self.bus.publish(f"cmd.{self.drone_id}", data)

    def _on_press(self, key):
        """Method done on 'on_press' event. Publishes action to bus specified in layout set at creation."""
        entry = self._resolve(key)
        if not entry:
            return
        if entry.get("on_press") is not None:
            data = {"action": entry["on_press"]}
        elif (entry.get("rc_axis") is not None) and (entry.get("rc_sign") is not None):
            self._held_axes[entry["rc_axis"]] = entry["rc_sign"]
            data = {"action": "rc", "args": self._compute_rc_vector()}
        else:
            return
        future = asyncio.run_coroutine_threadsafe(self._publish_parser(data), self.loop)
        future.add_done_callback(self._log_future_exception)

    def _on_release(self, key):
        """Method done on 'on_release' event. Publishes action to bus specified in layout set at creation."""
        entry = self._resolve(key)
        if not entry:
            return
        if entry.get("on_release") is not None:
            data = {"action": entry["on_release"]}
        elif (entry.get("rc_axis") is not None) and (entry.get("rc_sign") is not None):
            if self._held_axes[entry.get("rc_axis")] == entry.get("rc_sign"):
                self._held_axes[entry.get("rc_axis")] = 0.0
            data = {"action": "rc", "args": self._compute_rc_vector()}
        else:
            return
        future = asyncio.run_coroutine_threadsafe(self._publish_parser(data), self.loop)
        future.add_done_callback(self._log_future_exception)

    def _compute_rc_vector(self) -> dict:
        return {
            "x": self._held_axes.get("x", 0.0),
            "y": self._held_axes.get("y", 0.0),
            "z": self._held_axes.get("z", 0.0),
            "yaw": self._held_axes.get("yaw", 0.0),
        }

    @staticmethod
    def _log_future_exception(future) -> None:
        """run_coroutine_threadsafe() futures swallow exceptions unless
        someone checks .result()/.exception() on them - without this,
        a bug anywhere downstream just looks like 'nothing happened'."""
        exc = future.exception()
        if exc is not None:
            import traceback

            traceback.print_exception(type(exc), exc, exc.__traceback__)

    def _resolve(self, key) -> dict | None:
        """Gets layout sub-dictionary from pressed char/key-name."""
        try:
            lookup_key = key.char if hasattr(key, "char") and key.char else getattr(key, "name", None)
            return self.config.get(lookup_key)
        except Exception as e:
            self._publish_parser({"error": {"in": "_resolve", "exception": e}})
