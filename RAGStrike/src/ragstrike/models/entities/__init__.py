"""Domain entities."""

from ragstrike.models.entities.scan import PluginResult, ScanSession
from ragstrike.models.entities.target import Authorization, Target

__all__ = ["Authorization", "PluginResult", "ScanSession", "Target"]
