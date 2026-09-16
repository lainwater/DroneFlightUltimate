'''
Simulated Drone Implementation
'''
import asyncio
from pathlib import Path

from core.drone.base import DroneBase, DroneFlightState, DroneConState, DroneType, PublishType
from core.drone.implementations.Sim.simdrone.simdronesdk import SimDroneSDK

class SimDrone(DroneBase):
    def __init__(self,
                 drone_type: DroneType,
                 drone_id: str,
                 bus: object,
                 **kwargs):
        super().__init__(drone_type, drone_id, bus, **kwargs)
        self.sdk = SimDroneSDK()
        self.ip = self.init_kwargs["ip"]
        self.port = self.init_kwargs["port"]
        self.data_gen_task = None
        
    @property
    def config_dir(self) -> Path:
        return Path(__file__).parent

# General
    async def connect(self):
        self.con_state = DroneConState.CONNECTING
        ack = await self.sdk.connect(self.ip, self.port)
        self.con_state = DroneConState.CONNECTED
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def disconnect(self):
        if not await self._require_connected("disconnect"): return
        await self.stop_state_reciever()
        self.con_state = DroneConState.DISCONNECTING
        ack = await self.sdk.disconnect()
        self.con_state = DroneConState.DISCONNECTED
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
        
# Movement
    async def takeoff(self):
        if not await self._require_connected("takeoff"): return
        if self.flight_state == DroneFlightState.LANDED:
            ack = await self.sdk.takeoff()
            self.flight_state = DroneFlightState.INAIR
            await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def land(self):
        if not await self._require_connected("land"): return
        if self.flight_state != DroneFlightState.LANDED:
            ack = await self.sdk.land()
            self.flight_state = DroneFlightState.LANDED
            await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
    
    async def emergency(self):
        if not await self._require_connected("emergency"): return
        ack = await self.sdk.emergency()
        self.flight_state = DroneFlightState.EMERGENCY
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
        self.flight_state = DroneFlightState.LANDED

    # rc movement
    async def rc(self, x: int, y: int, z: int, yaw: int):
        if not await self._require_connected(f"rc"): return
        if self.flight_state != DroneFlightState.INAIR:
            return
        self.flight_state = DroneFlightState.MOVING
        ack = await self.sdk.rc(x, y, z, yaw)
        self.flight_state = DroneFlightState.INAIR
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    # Goto Pos Movement
    async def goto(self, x: float, y:float, z: float):
        if not await self._require_connected("goto"): return
        if self.flight_state != DroneFlightState.INAIR:
            return
        self.flight_state = DroneFlightState.MOVING
        ack = await self.sdk.goto_pos(x, y, z)
        self.flight_state = DroneFlightState.INAIR
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    # Step Movement            
    async def _move(self, direction: str, distance: float):
        if not await self._require_connected(f"_move {direction}"): return
        if self.flight_state != DroneFlightState.INAIR:
            return
        self.flight_state = DroneFlightState.MOVING
        ack = await self.sdk.move_step(direction, distance)
        self.flight_state = DroneFlightState.INAIR
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
                        
    async def move_forward(self, distance: float):
            await self._move("forward", distance)
    
    async def move_backward(self, distance: float):
            await self._move("backward", distance)
    
    async def move_up(self, distance: float):
            await self._move("up", distance)
            
    async def move_down(self, distance: float):
            await self._move("down", distance)
    
    async def move_left(self, distance: float):
            await self._move("left", distance)
                
    async def move_right(self, distance: float):
            await self._move("right", distance)


# Set
    async def set(self, what: str, **kwargs):
        if not await self._require_connected(f"set_{what}"): return
        ack = False
        if what == "flight_mode":
            return_val = await self.sdk.set_flight_mode(**kwargs)
        if what == "rc_speed":
            return_val = await self.sdk.set_rc_speed(**kwargs)
        if what == "takeoff_height":
            return_val = await self.sdk.set_takeoff_height(**kwargs)
        if what == "ip_and_port":
            return_val = await self.sdk.set_ip_and_port(**kwargs)
            self.ip = kwargs["ip"]
            self.port = kwargs["port"]
            self.disconnect()
        if what == "arm":
            return_val = await self.sdk.arm()
        if what == "disarm":
            return_val = await self.sdk.disarm()
        if not ack:
            await self.publish_parser(PublishType.ACK, f"{what} set to {kwargs if kwargs else 'Not applicable. No kwargs.'}")
        else:
            await self.publish_parser(PublishType.ERROR, f"Could not set {what}")

# GET
    async def get(self, what: str):
        if not await self._require_connected(f"get_{what}"): return
        return_val = None
        if what == "armed_status":
            return_val = await self.sdk.get_armed_status()
        if what == "state_gen_status":
            return_val = await self.sdk.get_state_gen_status()
        if what == "flight_mode":
            return_val = await self.sdk.get_flight_mode()
        if what == "ip_and_port":
            return_val = await self.sdk.get_ip_and_port()
        if what == "rc_speed":
            return_val = await self.sdk.get_rc_speed()
        if what == "takeoff_height":
            return_val = await self.sdk.get_takeoff_height()
        if what == "position":
            return_val = await self.sdk.get_position()
        if what == "attitude":
            return_val = await self.sdk.get_attitude()
        if what == "battery":
            return_val = await self.sdk.get_battery()
        if what == "temperature":
            return_val = await self.sdk.get_temperature()
        if return_val != None:
            await self.publish_parser(PublishType.DATA, {f"{what}": return_val})
        else:
            await self.publish_parser(PublishType.ERROR, {f"Could not get {what}"})

# Other
    async def start_state_reciever(self):
        """Starts a background task that publishes every item the SDK's
        data_generator yields, until stop_state_reciever() cancels it."""
        if not await self._require_connected("start_state_reciever"): return
        self.data_gen_task = asyncio.create_task(self._consume_state_stream())

    async def stop_state_reciever(self):
        """Cancel the background task and wait for it to actually stop,
        so we don't leave an unhandled CancelledError floating around."""
        if self.data_gen_task:
            self.data_gen_task.cancel()
            try:
                await self.data_gen_task
            except asyncio.CancelledError:
                pass
            self.data_gen_task = None

    async def _consume_state_stream(self):
        """The actual loop: as soon as the SDK yields a data point, publish it."""
        async for i in self.sdk.state_stream():
            await self.publish_parser(PublishType.STATE, i)