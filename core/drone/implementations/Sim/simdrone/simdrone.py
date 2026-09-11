'''
Simulated Drone Implementation
'''
import asyncio
from core.drone.base import DroneBase, DroneFlightState, DroneConState, DroneType, PublishType
from core.drone.implementations.Sim.simdrone.simdronesdk import SimDroneSDK

class SimDrone(DroneBase):
    def __init__(self,
                 drone_type: DroneType,
                 drone_id: str,
                 bus: object = None,
                 **kwargs):
        super().__init__(drone_type, drone_id, bus, **kwargs)
        self.sdk = SimDroneSDK()
        self.ip = self.init_kwargs["ip"]

    async def connect(self):
        self.con_state = DroneConState.CONNECTING
        ack = await self.sdk.connect()
        self.con_state = DroneConState.CONNECTED
        self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def disconnect(self):
        self.con_state = DroneConState.DISCONNECTING
        ack = await self.sdk.disconnect()
        self.con_state = DroneConState.DISCONNECTED
        self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def takeoff(self):
        if self.flight_state == DroneFlightState.LANDED:
            ack = await self.sdk.takeoff()
            self.flight_state = DroneFlightState.INAIR
            self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def land(self):
        if self.flight_state != DroneFlightState.LANDED:
            ack = await self.sdk.land()
            self.flight_state = DroneFlightState.LANDED
            self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def move_forward(self, distance: float):
            if self.flight_state == DroneFlightState.INAIR:
                ack = await self.sdk.move("forward", distance)
                self.flight_state = DroneFlightState.MOVING
                self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
    
    async def move_backward(self, distance: float):
            if self.flight_state == DroneFlightState.INAIR:
                ack = await self.sdk.move("backward", distance)
                self.flight_state = DroneFlightState.MOVING
                self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
    
    async def move_up(self, distance: float):
            if self.flight_state == DroneFlightState.INAIR:
                ack = await self.sdk.move("up", distance)
                self.flight_state = DroneFlightState.MOVING
                self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def move_down(self, distance: float):
            if self.flight_state == DroneFlightState.INAIR:
                ack = await self.sdk.move("down", distance)
                self.flight_state = DroneFlightState.MOVING
                self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
    
    async def move_left(self, distance: float):
            if self.flight_state == DroneFlightState.INAIR:
                ack = await self.sdk.move("left", distance)
                self.flight_state = DroneFlightState.MOVING
                self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
                
    async def move_right(self, distance: float):
            if self.flight_state == DroneFlightState.INAIR:
                ack = await self.sdk.move("right", distance)
                self.flight_state = DroneFlightState.MOVING
                self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})
                
    async def emergency(self):
        ack = await self.sdk.motor_off()
        self.flight_state = DroneFlightState.EMERGENCY
        self.publish_parser(PublishType.ACK, {"ack": f"{ack}"})

    async def get_battery(self) -> int:
        battery_level = await self.sdk.get_battery_level()
        self.publish_parser(PublishType.DATA, {"battery": battery_level})

    async def get_gps(self) -> tuple[float, float]:
        gps_coordinates = await self.sdk.get_gps_coordinates()
        self.publish_parser(PublishType.DATA, {"gps": gps_coordinates})
        
    async def get_ip(self) -> tuple[float, float]:
            gps_coordinates = await self.sdk.get_gps_coordinates()
            self.publish_parser(PublishType.DATA, {"gps": gps_coordinates})
    
    async def start_state_reciever(self):
         self.data_gen_task = asyncio.create_task(self.data_generator())
         async for i in self.data_gen_task:
             self.publish_parser(PublishType.STATE, i)
