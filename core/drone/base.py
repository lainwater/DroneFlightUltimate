"""
DroneBase — Interface for drone operations.
"""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from core.fileops import get_fileops


class DroneType(Enum):
    """Enum for different drone types."""
    SIM_SIMDRONE = "Sim_simdrone"
    DJI_TELLO = "DJI_tello"

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
                 bus: object,
                 **kwargs):
        self.drone_type = drone_type
        self.drone_id = drone_id
        self.flight_state = DroneFlightState.LANDED
        self.con_state = DroneConState.DISCONNECTED
        self.init_kwargs = kwargs
        self.bus = bus
        self.fops = get_fileops()
        self.command_map = self._initialize_command_map()
        self.stats = self._initialize_stats()
        self._attach()

    def _initialize_command_map(self) -> dict:
        """Initialize the command map for the drone."""
        return self.fops.read_json(self.config_dir / "commands.json")

    def _initialize_stats(self) -> dict:
        """Initialize the stats for the drone."""
        return self.fops.read_json(self.config_dir / "stats.json")
        
    def _attach(self) -> None:
        """Start recording every cmd.{self.drone_id} event published on `bus`."""
        self.bus.subscribe(f"cmd.{self.drone_id}", self.parse_bus_event)
    
    def detach(self) -> None:
        """Stop recording events from `bus`. Safe to call even if never attached."""
        self.bus.unsubscribe(f"cmd.{self.drone_id}", self.parse_bus_event)
    
    async def publish_parser(self, topic: PublishType, data: dict) -> None:
            """Publish the drone's stats and command map to the bus."""
            if self.bus:
                await self.bus.publish(f"{topic.value}.{self.drone_id}", data)
    
    async def parse_bus_event(self, topic: str, data: dict) -> None:
        """Parse the bus event and execute the corresponding command.
 
        Deliberately never lets an exception escape back through the
        bus: a malformed or unsupported command (e.g. from a REPL
        typo, or a keyboard mapping referencing an action this drone
        doesn't support) shows up as an error.{drone_id} event instead
        of crashing whichever controller published it."""
        action = data.get("action")
        if not action:
            await self.publish_parser(PublishType.ERROR, {
                "error": "missing_action",
                "message": f"No action specified in data: {data}",
            })
            return
 
        kwargs = {k: v for k, v in data.items() if k != "action"}
        try:
            await self.execute(action, **kwargs)
        except Exception as exc:
            await self.publish_parser(PublishType.ERROR, {
                "error": type(exc).__name__,
                "message": str(exc),
                "action": action,
            })
    
    async def execute(self, action: str, **kwargs) -> None:
        """Execute the command corresponding to the action.
 
        Raises on failure (unknown action, unsupported/missing method,
        wrong arguments). Callers going through parse_bus_event get
        these turned into error events instead of a crash; callers
        invoking execute() directly (tests, a future REPL) get a real
        exception they can handle themselves."""
        if action not in self.command_map:
            raise ValueError(f"'{action}' not in {self.drone_id}'s capabilities")
 
        entry = self.command_map[action]
        method_name = entry["method"]
        method = getattr(self, method_name, None)
        if method is None:
            raise AttributeError(f"'{action}' maps to '{method_name}', but {self.drone_id} has no such method")
        try:
            await method(**kwargs)
        except TypeError as exc:
            raise TypeError(f"Bad arguments for action '{action}': {exc}") from exc

    @property
    @abstractmethod
    def config_dir(self) -> Path:
        """Directory containing this drone's commands.json/stats.json.
        Concrete implementations return Path(__file__).parent so this
        works no matter where the app was launched from."""
        raise NotImplementedError

    async def get_state(self):
        """Get the current state of the drone."""
        await self.publish_parser(PublishType.STATE, {"flight_state": self.flight_state.value, "con_state": self.con_state.value})
    
    async def get_stats(self):
        """Get the current stats of the drone."""
        await self.publish_parser(PublishType.INFO, self.stats)

    async def get_command_map(self):
        """Get the command map of the drone."""
        await self.publish_parser(PublishType.INFO, self.command_map)
    
    async def _require_connected(self, action_name: str) -> bool:
        """Shared precondition check for any command that needs a live
        connection. Returns True if connected; otherwise publishes a
        generic error naming the ACTUAL action that was blocked (not a
        copy-pasted message from some other method) and returns False,
        so callers can write:
            if not await self._require_connected("takeoff"):
                return
        """
        if self.con_state != DroneConState.CONNECTED:
            await self.publish_parser(PublishType.ERROR, {
                "error": "NotConnected",
                "message": f"'{action_name}' called before connect().",
            })
            return False
        return True

    @abstractmethod
    async def start_state_reciever(self):
        "Starts continues State reciever"
        raise NotImplementedError
    
    @abstractmethod
    async def stop_state_reciever(self):
        "Stops continues State reciever"
        raise NotImplementedError

    @abstractmethod
    async def connect(self):
        """Connect to the drone."""
        raise NotImplementedError
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the drone."""
        raise NotImplementedError
    
    @abstractmethod
    async def takeoff(self):
        """Command the drone to take off."""
        raise NotImplementedError
    
    @abstractmethod
    async def land(self):
        """Command the drone to land."""
        raise NotImplementedError
    
    @abstractmethod
    async def emergency(self):
        """Command the drone to perform an emergency stop."""
        raise NotImplementedError