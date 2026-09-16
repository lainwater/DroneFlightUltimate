from dataclasses import dataclass
from datetime import datetime
import copy

@dataclass
class position:
    x: float
    y: float
    z: float
    vx: float
    vy: float
    vz: float
    timestamp: datetime | None
    
    def get_position_as_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z}
    
    def get_velocity_as_dict(self) -> dict:
        return {"vx": self.vx, "vy": self.vy, "vz": self.vz}
    
    def update_position_as_dict(self, pos: dict) -> None:
        self.x, self.y, self.z = pos["x"], pos["y"], pos["z"]
    
    def update_velocity_as_dict(self, pos: dict) -> None:
        self.vx, self.vy, self.vz = pos["vx"], pos["vy"], pos["vz"]
        
    def copy(self) -> object:
        return copy.deepcopy(self)

@dataclass
class attidute:
    pitch: float
    roll: float
    yaw: float
    vpitch: float
    vroll: float
    vyaw: float
    timestamp: datetime | None
    
    def get_attidute_as_dict(self) -> dict:
        return {"pitch": self.pitch, "roll": self.roll, "yaw": self.yaw}
    
    def get_velocity_as_dict(self) -> dict:
        return {"vpitch": self.vpitch, "vroll": self.vroll, "yaw": self.vyaw}
    
    def update_attidute_as_dict(self, att: dict) -> None:
        self.pitch, self.roll, self.yaw = att["pitch"], att["roll"], att["yaw"]
    
    def update_velocity_as_dict(self, att: dict) -> None:
        self.vpitch, self.vroll, self.vyaw = att["vpitch"], att["vroll"], att["vyaw"]
            
    def copy(self) -> object:
        return copy.deepcopy(self)

class pos_att_util:
    def interpolate_attitude(self, p1: attidute, p2: attidute, t: float) -> tuple: 
        "Interpolate two points with interpolation factor t (0.0 = P1, 0.5 = Halfway, 1.0 = P2)"
        x1, y1, z1 = p1.pitch, p1.roll, p1.yaw
        x2, y2, z2 = p2.pitch, p2.roll, p2.yaw
        x = (1 - t) * x1 + t * x2
        y = (1 - t) * y1 + t * y2
        z = (1 - t) * z1 + t * z2
        return (x, y, z)
        
    def interpolate_position(self, p1: position, p2: position, t: float) -> tuple: 
        "Interpolate two points with interpolation factor t (0.0 = P1, 0.5 = Halfway, 1.0 = P2)"
        x1, y1, z1 = p1.x, p1.y, p1.z
        x2, y2, z2 = p2.x, p2.y, p2.z
        x = (1 - t) * x1 + t * x2
        y = (1 - t) * y1 + t * y2
        z = (1 - t) * z1 + t * z2
        return (x, y, z)
    