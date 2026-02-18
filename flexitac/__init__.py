"""Public package interface for flexitac."""

from flexitac.sensor import FlexiTacSensor
from flexitac.types import FlexiTacFrame, ProcessingConfig, SensorGeometry

__all__ = [
    "FlexiTacFrame",
    "FlexiTacSensor",
    "ProcessingConfig",
    "SensorGeometry",
]

__version__ = "0.1.0"
