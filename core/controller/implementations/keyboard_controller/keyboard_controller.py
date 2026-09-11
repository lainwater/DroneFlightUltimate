'''
KeyboardController - Operate drone via keyboard.
'''

from core.controller.base import ControllerBase
from core.controller.implementations.keyboard_controller.get_layout import current_keyboard_layout_as_json_path

class KeyboardController(ControllerBase):
    def load_config(self):
        layoutpath = current_keyboard_layout_as_json_path()
        self.fops.read_json(layoutpath)
    
    def publish_parser(self):
        return