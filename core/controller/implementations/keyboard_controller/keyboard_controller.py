'''
KeyboardController - Operate drone via keyboard.
'''

import asyncio
from core.controller.base import ControllerBase
from core.controller.implementations.keyboard_controller.get_layout import current_keyboard_layout_as_json_path
from pynput import keyboard

class KeyboardController(ControllerBase):
    def __init__(self, drone_id, bus, layout):
          super().__init__(drone_id, bus, layout)
          self.kb_listener = keyboard.Listener(
              on_press=self.on_press,
              on_release=self.on_release
          )
    
    def load_config(self, layout: str) -> None:
        layoutpath = current_keyboard_layout_as_json_path(layout)
        self.config = self.fops.read_json(layoutpath)
    
    async def publish_parser(self, data: dict) -> None:
        if self.bus:
            await self.bus.publish(f"cmd.{self.drone_id}", data)
    
    async def start_controller(self):
        self.loop = asyncio.get_running_loop()
        self.kb_listener.start()
    
    async def stop_controller(self):
        self.kb_listener.stop()

    def on_press(self, key):
        entry = self._resolve(key)
        if entry:
            data = {"action": entry["to_publish"]}
            if "amount" in entry:
                data["distance"] = entry["amount"]
            asyncio.run_coroutine_threadsafe(self.publish_parser(data), self.loop)

    def on_release(self, key):
        pass

    def _resolve(self, key) -> dict | None:
        lookup_key = key.char if hasattr(key, "char") and key.char else getattr(key, "name", None)
        return self.config.get(lookup_key)