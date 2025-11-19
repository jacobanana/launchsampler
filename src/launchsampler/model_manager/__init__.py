"""Generic model management framework for Pydantic models.

This package provides a complete framework for managing Pydantic models with:

- Stateful service management (ModelManagerService)
- Persistence (PydanticPersistence)
- Observer pattern (ModelEvent, ModelObserver, ObserverManager)
- CLI generation (ModelCLIBuilder)

## Public API

### Core Service

- **ModelManagerService**: Generic service for managing any Pydantic model

### Persistence

- **PydanticPersistence**: Utility for loading/saving Pydantic models to JSON

### Observer Pattern

- **ModelEvent**: Enum of model lifecycle events
- **ModelObserver**: Protocol for observing model changes
- **ObserverManager**: Generic observer pattern implementation

### Protocols

- **PersistenceService**: Protocol for persistence service implementations

### CLI Generation (from model_manager.cli)

- **ModelCLIBuilder**: Auto-generate CLI from Pydantic models
- **TypeMapper**: Maps Pydantic types to Click types
- **ValidatorRegistry**: Registry for custom field validators

## Design Philosophy

- Generic and reusable across any Pydantic model
- Type-safe with full type hinting
- Observable with event notifications
- Thread-safe for concurrent access
- Composable over inheritance

## Example Usage

### Basic Service Usage

```python
from pathlib import Path
from pydantic import BaseModel
from launchsampler.model_manager import ModelManagerService, ModelEvent

# Define your model
class AppConfig(BaseModel):
    debug: bool = False
    port: int = 8000

# Create service
config = AppConfig()
service = ModelManagerService[AppConfig](
    AppConfig,
    config,
    default_path=Path("config.json")
)

# Use the service
service.set("debug", True)
service.save()
```

### CLI Generation

```python
from launchsampler.model_manager.cli import ModelCLIBuilder

builder = ModelCLIBuilder(AppConfig, Path("config.json"))
config_group = builder.build_group()
cli.add_command(config_group)
```
"""

# Core service
from launchsampler.model_manager.service import ModelManagerService

# Persistence
from launchsampler.model_manager.persistence import PydanticPersistence

# Observer pattern
from launchsampler.model_manager.observer import ObserverManager
from launchsampler.model_manager.protocols import (
    ModelEvent,
    ModelObserver,
    PersistenceService,
)

__all__ = [
    # Core service
    "ModelManagerService",
    # Persistence
    "PydanticPersistence",
    # Observer pattern
    "ObserverManager",
    "ModelEvent",
    "ModelObserver",
    "PersistenceService",
]
