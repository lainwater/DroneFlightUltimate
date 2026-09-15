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
        self.data_gen_task = None
        
    @property
    def config_dir(self) -> Path:
        return Path(__file__).parent

    async def connect(self):
        self.con_state = DroneConState.CONNECTING
        ack = await self.sdk.connect()
        self.con_state = DroneConState.CONNECTED
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def disconnect(self):
        if not await self._require_connected("takeoff"): return
        self.con_state = DroneConState.DISCONNECTING
        await self.stop_state_reciever()
        ack = await self.sdk.disconnect()
        self.con_state = DroneConState.DISCONNECTED
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

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
            
    async def _move(self, direction: str, distance: float):
        '''Shared Guard + SDK Call + state-update + ack posting for move commands'''
        if not await self._require_connected("_move"): return
        if self.flight_state != DroneFlightState.INAIR:
            return
        self.flight_state = DroneFlightState.MOVING
        ack = await self.sdk.move(direction, distance)
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
                
    async def emergency(self):
        if not await self._require_connected("emergency"): return
        ack = await self.sdk.motor_off()
        self.flight_state = DroneFlightState.EMERGENCY
        await self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
        self.flight_state = DroneFlightState.LANDED

    async def get_battery(self) -> int:
        if not await self._require_connected("get_battery"): return
        battery_level = await self.sdk.get_battery_level()
        await self.publish_parser(PublishType.DATA, {"battery": battery_level})

    async def get_gps(self) -> tuple[float, float]:
        if not await self._require_connected("gps"): return
        gps_coordinates = await self.sdk.get_gps_coordinates()
        await self.publish_parser(PublishType.DATA, {"gps": gps_coordinates})

    async def get_ip(self) -> tuple[float, float]:
        if not await self._require_connected("get_ip"): return
        await self.publish_parser(PublishType.DATA, {"ip": self.ip})
    
    async def start_state_reciever(self):
        """Starts a background task that publishes every item the SDK's
        data_generator yields, until stop_state_reciever() cancels it."""
        if not await self._require_connected("start_state_reciever"): return
        self.data_gen_task = asyncio.create_task(self._consume_state_stream())

    async def stop_state_reciever(self):
        """Cancel the background task and wait for it to actually stop,
        so we don't leave an unhandled CancelledError floating around."""
        if not await self._require_connected("stop_state_reciever"): return
        if self.data_gen_task:
            self.data_gen_task.cancel()
            try:
                await self.data_gen_task
            except asyncio.CancelledError:
                pass
            self.data_gen_task = None

    async def _consume_state_stream(self):
        """The actual loop: as soon as the SDK yields a data point, publish it."""
        async for i in self.sdk.data_generator():
            await self.publish_parser(PublishType.STATE, i)