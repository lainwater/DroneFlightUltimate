"""
public API of core.patterns - predefined flight patterns over the bus.

    from core.patterns import get_patterns
    patterns = get_patterns("drone1", bus)
    await patterns.square(100)
    patterns.start(patterns.orbit(radius_cm=100)); await patterns.cancel()
"""

from .flight_patterns import FlightPatterns, PatternAborted, orbit_rc, polygon_edges, split_go


def get_patterns(drone_id: str, bus: object, **kwargs) -> FlightPatterns:
    """Flight patterns for one drone (kwargs: rc_rate_hz)."""
    return FlightPatterns(drone_id, bus, **kwargs)


__all__ = ["FlightPatterns", "PatternAborted", "get_patterns", "orbit_rc", "polygon_edges", "split_go"]
