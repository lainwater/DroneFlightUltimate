'''
REPLController - Operate drone via REPL.
'''

from core.controller.base import ControllerBase
from pathlib import Path

class REPLController(ControllerBase):
    def load_config(self):
        self.fops.read_json(f"{Path(__file__).parent}repl_controller.json")
    
    def publish_parser(self):
        return