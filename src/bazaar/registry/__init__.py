"""Agent registry module."""

from .register import register_agent
from .benchmark import run_benchmark

__all__ = ["register_agent", "run_benchmark"]
