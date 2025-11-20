"""Application orchestration layer.

This package contains the top-level application orchestrator that coordinates
all services, manages application lifecycle, and coordinates multiple UIs.

The orchestrator is responsible for:
- Initializing and managing services (Player, Editor, SetManager)
- Coordinating multiple UI implementations (TUI, LED, web)
- Managing application state and lifecycle
- Firing application-level events
"""

from .orchestrator import Orchestrator

__all__ = ["Orchestrator"]
