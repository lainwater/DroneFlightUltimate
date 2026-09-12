'''
ControllerBase - Interface for drone operations.
'''

from abc import ABC, abstractmethod
from core.fileops import get_fileops

class ControllerBase(ABC):
    def __init__(self, drone_id: str, bus: object, layout: str):
        self.fops = get_fileops()
        self.config = None
        self.drone_id = drone_id
        self.layout = layout
        self.bus = bus
        self.load_config(layout)
    
    @abstractmethod
    def load_config(self, layout:str = None):
        raise NotImplementedError
    
    @abstractmethod
    async def publish_parser(self, data: dict) -> None:
        raise NotImplementedError
    
    @abstractmethod
    async def start_controller(self) -> None:
        raise NotImplementedError