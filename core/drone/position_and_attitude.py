"""
Hold dataclasses for position and attitude data and
an util class to interpolate two of the same dataclasses objects.
"""

import copy
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    """Hold position data.
    x y z vx vy vz and a timestamp."""

    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    timestamp: datetime | None

    def get_position_as_dict(self) -> dict:
        """Get the postion as dict: { 'x': x, 'y': y, 'z': z }"""
        return {"x": self.x, "y": self.y, "z": self.z}

    def get_velocity_as_dict(self) -> dict:
        """Get the velocity as dict: { 'vx': vx, 'vy': vy, 'vz': vz }"""
        return {"vx": self.vx, "vy": self.vy, "vz": self.vz}

    def update_position_as_dict(self, pos: dict) -> None:
        """Update the postion with dict input: { 'x': x, 'y': y, 'z': z }"""
        self.x, self.y, self.z = pos["x"], pos["y"], pos["z"]

    def update_velocity_as_dict(self, pos: dict) -> None:
        """Update the velocity with dict input: { 'vx': vx, 'vy': vy, 'vz': vz }"""
        self.vx, self.vy, self.vz = pos["vx"], pos["vy"], pos["vz"]

    def copy(self) -> "Position":
        """Return a copy of the dataclass unrelated to original object."""
        return copy.deepcopy(self)


@dataclass
class Attitude:
    """Hold attitude data.
    pitch roll yaw vpitch vroll vyaw and a timestamp."""

    pitch: float
    roll: float
    yaw: float
    vpitch: float
    vroll: float
    vyaw: float
    timestamp: datetime | None

    def get_attitude_as_dict(self) -> dict:
        """Get the attitude as dict: { 'pitch': pitch, 'roll': roll, 'yaw': yaw }"""
        return {"pitch": self.pitch, "roll": self.roll, "yaw": self.yaw}

    def get_velocity_as_dict(self) -> dict:
        """Get the attitude-velocity as dict: { 'vpitch': vpitch, 'vroll': vroll, 'vyaw': vyaw }"""
        return {"vpitch": self.vpitch, "vroll": self.vroll, "yaw": self.vyaw}

    def update_attitude_as_dict(self, att: dict) -> None:
        """Update the attitude with dict input: { 'pitch': pitch, 'roll': roll, 'yaw': yaw }"""
        self.pitch, self.roll, self.yaw = att["pitch"], att["roll"], att["yaw"]

    def update_velocity_as_dict(self, att: dict) -> None:
        """Update the attitude-velocity with dict input: { 'vpitch': vpitch, 'vroll': vroll, 'vyaw': vyaw }"""
        self.vpitch, self.vroll, self.vyaw = att["vpitch"], att["vroll"], att["vyaw"]

    def copy(self) -> "Attitude":
        return copy.deepcopy(self)


class PosAttUtil:
    def interpolate_attitude(self, p1: Attitude, p2: Attitude, t: float) -> tuple:
        """Interpolate two points of attitude object type with interpolation factor t (0.0 = P1, 0.5 = Halfway, 1.0 = P2)
        Returns a tuple (pitch, roll, yaw)"""
        x1, y1, z1 = p1.pitch, p1.roll, p1.yaw
        x2, y2, z2 = p2.pitch, p2.roll, p2.yaw
        pitch = (1 - t) * x1 + t * x2
        roll = (1 - t) * y1 + t * y2
        yaw = (1 - t) * z1 + t * z2
        return (pitch, roll, yaw)

    def interpolate_position(self, p1: Position, p2: Position, t: float) -> tuple:
        """Interpolate two points of position object type with interpolation factor t (0.0 = P1, 0.5 = Halfway, 1.0 = P2)
        Returns a tuple (x, y, z)"""
        x1, y1, z1 = p1.x, p1.y, p1.z
        x2, y2, z2 = p2.x, p2.y, p2.z
        x = (1 - t) * x1 + t * x2
        y = (1 - t) * y1 + t * y2
        z = (1 - t) * z1 + t * z2
        return (x, y, z)
