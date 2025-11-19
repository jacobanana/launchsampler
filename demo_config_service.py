"""
Standalone demonstration of ConfigService functionality.

This script demonstrates the ConfigService without requiring the full test environment.
Run with: python3 demo_config_service.py (requires only pydantic)
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from pydantic import BaseModel, Field
    print("✓ Pydantic is available")
except ImportError:
    print("✗ This demo requires pydantic. Install with: pip install pydantic")
    sys.exit(1)

# Define a simple test config model
class DemoConfig(BaseModel):
    """Simple configuration for demonstration."""
    app_name: str = "LaunchSampler"
    version: str = "1.0.0"
    debug_mode: bool = False
    max_connections: int = 10
    data_dir: Path = Field(default_factory=lambda: Path("/tmp/demo"))


print("\n" + "=" * 60)
print("ConfigService Demonstration")
print("=" * 60)

# Import our modules directly to avoid package init
try:
    import importlib.util

    # Load protocols module directly
    spec = importlib.util.spec_from_file_location(
        "protocols",
        Path(__file__).parent / "src/launchsampler/protocols.py"
    )
    protocols = importlib.util.module_from_spec(spec)
    sys.modules['launchsampler.protocols'] = protocols
    spec.loader.exec_module(protocols)
    ConfigEvent = protocols.ConfigEvent
    ConfigObserver = protocols.ConfigObserver

    # Load observer_manager module directly
    spec = importlib.util.spec_from_file_location(
        "observer_manager",
        Path(__file__).parent / "src/launchsampler/utils/observer_manager.py"
    )
    observer_manager = importlib.util.module_from_spec(spec)
    sys.modules['launchsampler.utils.observer_manager'] = observer_manager
    spec.loader.exec_module(observer_manager)
    ObserverManager = observer_manager.ObserverManager

    # Load persistence module directly
    spec = importlib.util.spec_from_file_location(
        "persistence",
        Path(__file__).parent / "src/launchsampler/utils/persistence.py"
    )
    persistence_module = importlib.util.module_from_spec(spec)
    sys.modules['launchsampler.utils.persistence'] = persistence_module
    spec.loader.exec_module(persistence_module)
    PydanticPersistence = persistence_module.PydanticPersistence

    # Create utils module and expose both ObserverManager and PydanticPersistence
    import types
    utils_module = types.ModuleType('launchsampler.utils')
    utils_module.ObserverManager = ObserverManager
    utils_module.PydanticPersistence = PydanticPersistence
    sys.modules['launchsampler.utils'] = utils_module

    # Load config_service module directly
    spec = importlib.util.spec_from_file_location(
        "config_service",
        Path(__file__).parent / "src/launchsampler/services/config_service.py"
    )
    config_service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_service)
    ConfigService = config_service.ConfigService

    print("✓ All modules imported successfully\n")
except Exception as e:
    print(f"✗ Failed to import modules: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


# Create a simple observer to demonstrate events
class DemoObserver:
    """Simple observer that prints events."""

    def __init__(self):
        self.events_received = []

    def on_config_event(self, event: ConfigEvent, **kwargs):
        """Handle config events."""
        self.events_received.append((event, kwargs))
        print(f"  📢 Observer received: {event.value}")
        if "keys" in kwargs:
            print(f"     Changed keys: {kwargs['keys']}")
        if "values" in kwargs:
            print(f"     New values: {kwargs['values']}")


print("1. Creating ConfigService with DemoConfig")
print("-" * 60)
config = DemoConfig()
service = ConfigService[DemoConfig](DemoConfig, config)
print(f"✓ Service created")
print(f"  Config type: {service._config_type.__name__}")
print()

print("2. Registering Observer")
print("-" * 60)
observer = DemoObserver()
service.register_observer(observer)
print("✓ Observer registered\n")

print("3. Getting Configuration Values")
print("-" * 60)
print(f"  app_name: {service.get('app_name')}")
print(f"  version: {service.get('version')}")
print(f"  debug_mode: {service.get('debug_mode')}")
print(f"  max_connections: {service.get('max_connections')}")
print()

print("4. Setting Single Value")
print("-" * 60)
print("  Calling: service.set('debug_mode', True)")
service.set('debug_mode', True)
print(f"  New value: {service.get('debug_mode')}")
print()

print("5. Batch Update Multiple Values")
print("-" * 60)
print("  Calling: service.update({'app_name': 'MyApp', 'max_connections': 50})")
service.update({
    'app_name': 'MyApp',
    'max_connections': 50
})
print(f"  app_name: {service.get('app_name')}")
print(f"  max_connections: {service.get('max_connections')}")
print()

print("6. Get All Configuration")
print("-" * 60)
all_config = service.get_all()
for key, value in all_config.items():
    print(f"  {key}: {value}")
print()

print("7. Reset to Defaults")
print("-" * 60)
print("  Calling: service.reset()")
service.reset()
print(f"  app_name: {service.get('app_name')}")
print(f"  debug_mode: {service.get('debug_mode')}")
print(f"  max_connections: {service.get('max_connections')}")
print()

print("8. Save and Load Configuration")
print("-" * 60)
temp_config_path = Path("/tmp/demo_config.json")
service = ConfigService[DemoConfig](DemoConfig, config, temp_config_path)
service.set('app_name', 'SavedApp')
service.set('max_connections', 100)
print(f"  Saving to: {temp_config_path}")
service.save()
print(f"  ✓ Saved")

# Load in new service
new_config = DemoConfig()
new_service = ConfigService[DemoConfig](DemoConfig, new_config, temp_config_path)
print(f"  Loading from: {temp_config_path}")
new_service.load()
print(f"  ✓ Loaded")
print(f"  app_name: {new_service.get('app_name')}")
print(f"  max_connections: {new_service.get('max_connections')}")
print()

print("9. Observer Events Summary")
print("-" * 60)
print(f"  Total events received: {len(observer.events_received)}")
for event, kwargs in observer.events_received:
    print(f"  - {event.value}")
print()

print("10. Error Handling - Invalid Field")
print("-" * 60)
try:
    service.set('nonexistent_field', 'value')
    print("  ✗ Should have raised AttributeError")
except AttributeError as e:
    print(f"  ✓ Correctly raised AttributeError: {e}")
print()

print("11. Error Handling - Type Validation")
print("-" * 60)
try:
    service.set('max_connections', 'not_an_integer')
    print("  ✗ Should have raised ValidationError")
except Exception as e:
    print(f"  ✓ Correctly raised ValidationError: {type(e).__name__}")
print()

print("=" * 60)
print("✓ All demonstrations completed successfully!")
print("=" * 60)
print()

# Clean up
if temp_config_path.exists():
    temp_config_path.unlink()
    print(f"Cleaned up: {temp_config_path}")
