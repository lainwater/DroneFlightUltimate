import asyncio

class SimDroneSDK:
    def __init__(self, data_gen_limit: int = 1000):
        self.connected = False
        self.data_gen_limit = data_gen_limit

    async def connect(self) -> bool:
        
        self.connected = True
        return True

    async def disconnect(self) -> bool:
        self.connected = False
        return True
    
    async def takeoff(self) -> bool:
        await asyncio.sleep(1)  # Simulate time taken to take off
        return True

    async def land(self) -> bool:
        await asyncio.sleep(1)  # Simulate time taken to land
        return True

    async def move(self, direction: str, distance: float) -> bool:
        await asyncio.sleep(1)  # Simulate time taken to move
        return True

    async def get_battery_level(self) -> int:
        return 100  # Simulated battery level
    
    async def get_gps_coordinates(self) -> tuple[float, float]:
        return (0.0, 0.0)  # Simulated GPS coordinates
    
    async def motor_off(self) -> bool:
        return True  # Simulated motor off command
    
    async def data_generator(self):
        i = 0
        while self.connected or i > self.data_gen_limit:
            i += 1
            await asyncio.sleep(0.1)  # Simulate data generation interval
            yield {
                "battery": await self.get_battery_level(),
                "gps": await self.get_gps_coordinates(),
                "timestamp": asyncio.get_event_loop().time()
            }
        return