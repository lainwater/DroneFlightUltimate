"""
DroneBase — Interface for drone operations.
"""

from abc import ABC, abstractmethod
from enum import Enum
import asyncio

from fileops import get_fileops


class DroneType(Enum):
    """Enum for different drone types."""
    SIM_SIMDRONE = "core/drone/implementations/Sim/simdrone/"
    DJI_TELLO = "core/drone/implementations/DJI/tello/"

class DroneFlightState(Enum):
    """Enum for different drone states."""
    LANDED = "landed"
    INAIR = "inair"
    HOVER = "hover"
    MOVING = "moving"
    EMERGENCY = "emergency"

class DroneConState(Enum):
    """Enum for different drone connection states."""
    CONNECTED = "connected"
    CONNECTING = "connecting"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"

class PublishType(Enum):
    """Enum for different types of publish events."""
    INFO = "info"
    STATE = "state"
    DATA = "data"
    ACK = "ack"
    ERROR = "error"

class DroneBase(ABC):
    """Abstract base class for drone operations."""
    def __init__(self,
                 drone_type: DroneType,
                 drone_id: str,
                 bus: object = None,
                 **kwargs):
        self.drone_type = drone_type
        self.drone_id = drone_id
        self.flight_state = DroneFlightState.LANDED
        self.con_state = DroneConState.DISCONNECTED
        self.init_kwargs = kwargs
        self.bus = bus
        self.fops = get_fileops()
        self.fops.ensure_dir(f"logs/debug_logs/{self.drone_id}_log.jsonl")
        
        self.command_map = self._initialize_command_map()
        self.stats = self._initialize_stats()
        self._attach()

    def _initialize_command_map(self) -> dict:
        """Initialize the command map for the drone."""
        return self.fops.read_json(f"{self.drone_type.value}/commands.json")

    def _initialize_stats(self) -> dict:
        """Initialize the stats for the drone."""
        return self.fops.read_json(f"{self.drone_type.value}/stats.json")
        
    def _attach(self) -> None:
        """Start recording every cmd.{self.drone_id} event published on `bus`."""
        self.bus.subscribe(f"cmd.{self.drone_id}", self.parse_bus_event)
    
    def detach(self) -> None:
        """Stop recording events from `bus`. Safe to call even if never attached."""
        self.bus.unsubscribe(f"cmd.{self.drone_id}", self.parse_bus_event)
    
    async def publish_parser(self, topic: PublishType, data: dict) -> None:
            """Publish the drone's stats and command map to the bus."""
            if self.bus:
                self.bus.publish(f"{topic.value}.{self.drone_id}", data)
    
    async def parse_bus_event(self, topic: str, data: dict) -> None:
        """Parse the bus event and execute the corresponding command."""
        action = data.get("action")
        if action:
            await self.execute(action, **data)
        else:
            raise ValueError(f"No action specified in data: {data}")
    
    async def execute(self, action: str, **kwargs) -> None:
        '''Execute the command corresponding to the action."""'''
        if action not in self.command_map:
            raise ValueError(f"{action} not in {self.drone_id}'s capabilities")
        entry = self.command_map[action]
        method = getattr(self.sdk, entry["method"])
        await method(**kwargs)

    async def get_state(self):
        """Get the current state of the drone."""
        self.publish_parser(PublishType.STATE, {"flight_state": self.flight_state.value, "con_state": self.con_state.value})
    
    async def get_stats(self):
        """Get the current stats of the drone."""
        self.publish_parser(PublishType.INFO, self.stats)

    async def get_command_map(self):
        """Get the command map of the drone."""
        self.publish_parser(PublishType.INFO, self.command_map)

    @abstractmethod
    async def start_state_reciever(self):
        "Starts continues State reciever"
        pass
    
    @abstractmethod
    async def stop_state_reciever(self):
        "Stops continues State reciever"
        pass

    @abstractmethod
    async def connect(self):
        """Connect to the drone."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the drone."""
        pass
    
    @abstractmethod
    async def takeoff(self):
        """Command the drone to take off."""
        pass
    
    @abstractmethod
    async def land(self):
        """Command the drone to land."""
        pass
    
    @abstractmethod
    async def emergency(self):
        """Command the drone to perform an emergency stop."""
        pass