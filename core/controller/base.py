'''
ControllerBase - Interface for drone operations.
'''

from abc import ABC, abstractmethod
from core.fileops import get_fileops

class ControllerBase(ABC):
    def __init__(self):
        self.fops = get_fileops()
        self.load_config()
    
    @abstractmethod
    def load_config(self):
        return
    
    @abstractmethod
    def publish_parser(self):
        return