"""
Simulated Drone Implementation
"""

import asyncio
from pathlib import Path

from core.drone.base import DroneArmState, DroneBase, DroneConState, DroneFlightState, DroneType, PublishType, requires
from core.drone.implementations.Sim.simdrone.simdronesdk import SimDroneSDK, _FlightMode


class SimDrone(DroneBase):
    def __init__(self, drone_type: DroneType, drone_id: str, bus: object, **kwargs):
        super().__init__(drone_type, drone_id, bus, **kwargs)
        self.sdk = SimDroneSDK()
        self.ip = self.init_kwargs["ip"]
        self.port = self.init_kwargs["port"]
        self.data_gen_task = None
        self.flightmode = _FlightMode.NONE_SET

    @property
    def config_dir(self) -> Path:
        return Path(__file__).parent

    # General
    async def connect(self):
        self.con_state = DroneConState.CONNECTING
        ack = await self.sdk.connect(self.ip, self.port)
        if ack:
            self.con_state = DroneConState.CONNECTED
        else:
            self.con_state = DroneConState.DISCONNECTED
        await self.publish_parser(PublishType.ACK, {"cmd": "connect", "ack": f"{ack}"})

    @requires(DroneConState.CONNECTED)
    async def disconnect(self):
        await self.stop_state_reciever()
        await self.set("disarm")
        self.con_state = DroneConState.DISCONNECTING
        ack = await self.sdk.disconnect()
        if ack:
            self.con_state = DroneConState.DISCONNECTED
        else:
            self.con_state = DroneConState.CONNECTED
        await self.publish_parser(PublishType.ACK, {"cmd": "disconnect", "ack": f"{ack}"})

    # Movement
    @requires(DroneConState.CONNECTED, DroneFlightState.LANDED, DroneArmState.ARMED)
    async def takeoff(self):
        ack = await self.sdk.takeoff()
        if not ack:
            await self.publish_parser(
                PublishType.ERROR, {"cmd": "takeoff", "info": f"takeoff returned {ack}. Try arming drone first", "error": "takeoffFailed"}
            )
        else:
            await self.publish_parser(PublishType.ACK, {"cmd": "takeoff", "ack": f"{ack}"})
            self.flight_state = DroneFlightState.INAIR

    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def land(self):
        ack = await self.sdk.land()
        if not ack:
            await self.publish_parser(
                PublishType.ERROR, {"cmd": "land", "info": f"land returned {ack}. Try getting drone in air first", "error": "landFailed"}
            )
        else:
            await self.publish_parser(PublishType.ACK, {"cmd": "land", "ack": f"{ack}"})
            self.flight_state = DroneFlightState.LANDED

    @requires(DroneConState.CONNECTED)
    async def emergency(self):
        ack = await self.sdk.emergency()
        if not ack:
            await self.publish_parser(PublishType.ERROR, {"cmd": "emergency", "info": f"emergency returned {ack}.", "error": "emergencyFailed"})
        else:
            await self.publish_parser(PublishType.ACK, {"cmd": "emergency", "ack": f"{ack}"})
            self.flight_state = DroneFlightState.LANDED

    # rc movement
    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def rc(self, x: int, y: int, z: int, yaw: int):
        ack = await self.sdk.rc(x, y, z, yaw)
        if not ack:
            await self.publish_parser(
                PublishType.ERROR,
                {"cmd": f"rc {x} {y} {z} {yaw}", "info": f"rc returned {ack}. Try setting drone in 'RC' mode first.", "error": "rcFailed"},
            )
        else:
            await self.publish_parser(PublishType.ACK, {"cmd": f"rc {x} {y} {z} {yaw}", "ack": f"{ack}"})

    # goto pos movement
    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def goto(self, x: float, y: float, z: float):
        ack = await self.sdk.goto_pos(x, y, z)
        if not ack:
            await self.publish_parser(
                PublishType.ERROR,
                {"cmd": f"goto {x} {y} {z}", "info": f"goto returned {ack}. Try setting drone in 'GOTO' mode first.", "error": "gotoFailed"},
            )
        else:
            await self.publish_parser(PublishType.ACK, {"cmd": f"goto {x} {y} {z}", "ack": f"{ack}"})

    # Step Movement
    @requires(DroneConState.CONNECTED, DroneFlightState.INAIR)
    async def steps_move(self, direction: str, distance: float):
        ack = await self.sdk.move_step(direction, distance)
        if not ack:
            await self.publish_parser(
                PublishType.ERROR,
                {
                    "cmd": f"_move {direction} {distance}",
                    "info": f"_move returned {ack}. Try setting drone in 'STEPS' mode first.",
                    "error": "_moveFailed",
                },
            )
        else:
            await self.publish_parser(PublishType.ACK, {"cmd": f"_move {direction} {distance}", "ack": f"{ack}"})

    # Set
    @requires(DroneConState.CONNECTED)
    async def set(self, what: str, **kwargs) -> None:
        ack = None
        if what == "flight_mode":
            ack = await self.sdk.set_flight_mode(**kwargs)
            if ack:
                self.flightmode = _FlightMode[f"{kwargs['flight_mode']}".upper()]
        elif what == "rc_speed":
            ack = await self.sdk.set_rc_speed(**kwargs)
        elif what == "takeoff_height":
            ack = await self.sdk.set_takeoff_height(**kwargs)
        elif what == "ip_and_port":
            ack = await self.sdk.set_ip_and_port(**kwargs)
            if ack:
                self.ip = kwargs["ip"]
                self.port = kwargs["port"]
                await self.disconnect()
        elif what == "arm":
            ack = await self.sdk.arm()
            if ack:
                self.arm_state = DroneArmState.ARMED
        elif what == "disarm":
            ack = await self.sdk.disarm()
            if ack:
                self.arm_state = DroneArmState.DISARMED
        else:
            await self.publish_parser(PublishType.ERROR, {"error": "NotExist", "message": f"{what} does not exist in simdrone."})

        if not ack:
            await self.publish_parser(PublishType.ERROR, {"cmd": f"set {what} {kwargs}", "info": f"set returned {ack}.", "error": "setFailed"})
        else:
            await self.publish_parser(PublishType.ACK, {"cmd": f"set {what} {kwargs}", "ack": f"{ack}"})

    # GET
    @requires(DroneConState.CONNECTED)
    async def get(self, what: str):
        return_val = None
        if what == "armed_status":
            return_val = await self.sdk.get_armed_status()
        elif what == "state_gen_status":
            return_val = await self.sdk.get_state_gen_status()
        elif what == "flight_mode":
            return_val = await self.sdk.get_flight_mode()
        elif what == "ip_and_port":
            return_val = await self.sdk.get_ip_and_port()
        elif what == "rc_speed":
            return_val = await self.sdk.get_rc_speed()
        elif what == "takeoff_height":
            return_val = await self.sdk.get_takeoff_height()
        elif what == "position":
            return_val = await self.sdk.get_position()
        elif what == "attitude":
            return_val = await self.sdk.get_attitude()
        elif what == "battery":
            return_val = await self.sdk.get_battery()
        elif what == "temperature":
            return_val = await self.sdk.get_temperature()
        else:
            await self.publish_parser(PublishType.ERROR, {"error": "NotExist", "message": f"{what} does not exist in simdrone."})

        if return_val is not None:
            await self.publish_parser(PublishType.DATA, {f"{what}": return_val})
        else:
            await self.publish_parser(PublishType.ERROR, {"error": "NotFound", "message": f"Could not get {what}"})

    # Other
    @requires(DroneConState.CONNECTED)
    async def start_state_reciever(self):
        """Starts a background task that publishes every item the SDK's
        data_generator yields, until stop_state_reciever() cancels it."""
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
