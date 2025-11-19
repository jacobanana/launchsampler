# ModelCLIBuilder: Auto-Generate CLI from Pydantic Models

`ModelCLIBuilder` is a generic framework for auto-generating CLI commands from any Pydantic model. It integrates with `ModelManagerService` for type-safe configuration management.

## Quick Start

```python
from pathlib import Path
from launchsampler.cli.model_cli_builder import ModelCLIBuilder
from launchsampler.models import AppConfig

# Create builder
builder = ModelCLIBuilder(
    AppConfig,
    config_path=Path.home() / ".launchsampler" / "config.json"
)

# Build CLI group with all commands
config = builder.build_group()
```

This auto-generates:
- `config show` - Display configuration
- `config set --field value` - Update fields
- `config validate` - Validate configuration file
- `config reset` - Reset to defaults

## Features

### 1. Auto-Generated Options

CLI options are automatically generated from Pydantic model fields:

```python
class AppConfig(BaseModel):
    buffer_size: int = Field(default=512, description="Audio buffer size")
    auto_save: bool = Field(default=True, description="Auto-save changes")
```

Generates CLI options:
```bash
config set --buffer-size 1024
config set --auto-save false
```

### 2. Type Mapping

Pydantic types are automatically mapped to Click types:

| Pydantic Type | Click Type |
|---------------|------------|
| `int` | `click.INT` |
| `str` | `click.STRING` |
| `float` | `click.FLOAT` |
| `bool` | `click.BOOL` |
| `Path` | `click.Path(path_type=Path)` |
| `Optional[T]` | Same as `T` |

### 3. Help Text

Help text is automatically generated from field descriptions:

```python
class Config(BaseModel):
    port: int = Field(
        default=8000,
        description="Server port number"  # ← Used in CLI help
    )
```

```bash
$ myapp config set --help
Options:
  --port INTEGER  Server port number (default: 8000)
```

### 4. Custom Validators

Add custom validation logic with the `ValidatorRegistry`:

```python
from launchsampler.cli.model_cli_builder import ValidatorRegistry

@ValidatorRegistry.register("port")
def validate_port(port: int) -> tuple[bool, str | None]:
    if port < 1 or port > 65535:
        return False, "Port must be between 1 and 65535"
    if port < 1024:
        return True, "Warning: Port requires root privileges"
    return True, None
```

The validator returns:
- `(True, message)` - Valid, show info message to user
- `(False, error)` - Invalid, show error and abort

### 5. Field-Level Overrides

Customize individual fields:

```python
builder = ModelCLIBuilder(
    AppConfig,
    config_path=Path("config.json"),
    field_overrides={
        "buffer_size": {
            "short": "b",  # Add short flag: -b
            "help": "Audio buffer size in frames"  # Override help text
        },
        "internal_field": {
            "expose": False  # Hide from CLI
        },
        "custom_field": {
            "type": click.Choice(['a', 'b', 'c'])  # Custom Click type
        }
    }
)
```

## Usage Examples

### Example 1: Basic Usage

```python
from pydantic import BaseModel, Field
from pathlib import Path

class ServerConfig(BaseModel):
    host: str = "localhost"
    port: int = Field(default=8000, description="Server port")
    workers: int = 4

# Build CLI
builder = ModelCLIBuilder(
    ServerConfig,
    config_path=Path("server.json")
)
config_cli = builder.build_group()
```

Generated CLI:
```bash
# Show all settings
$ myapp config show
ServerConfig Configuration:
  host: localhost
  port: 8000
  workers: 4

# Update settings
$ myapp config set --port 8080 --workers 16
✓ port = 8080
✓ workers = 16
Configuration saved to server.json

# Show specific field
$ myapp config show --field port
port: 8080

# Validate config file
$ myapp config validate
✓ server.json is valid

# Reset to defaults
$ myapp config reset --field port
✓ Reset port to default: 8000
```

### Example 2: With Custom Validators

```python
from launchsampler.cli.model_cli_builder import ValidatorRegistry

@ValidatorRegistry.register("buffer_size")
def validate_buffer_size(size: int) -> tuple[bool, str | None]:
    """Validate buffer size is power of 2."""
    if size & (size - 1) != 0:
        return False, "Buffer size must be a power of 2 (512, 1024, 2048, ...)"
    return True, f"Using buffer size: {size} frames"

builder = ModelCLIBuilder(AppConfig, Path("config.json"))
```

```bash
$ myapp config set --buffer-size 1000
Error validating buffer_size: Buffer size must be a power of 2 (512, 1024, 2048, ...)

$ myapp config set --buffer-size 1024
✓ buffer_size: Using buffer size: 1024 frames
Configuration saved to config.json
```

### Example 3: Field Overrides

```python
builder = ModelCLIBuilder(
    AppConfig,
    config_path=Path("config.json"),
    field_overrides={
        "default_audio_device": {
            "short": "a",
            "help": "Audio device ID (use 'myapp audio list' to see devices)"
        },
        "internal_debug_flag": {
            "expose": False  # Don't expose in CLI
        }
    }
)
```

### Example 4: Complete Example

```python
# models/config.py
from pydantic import BaseModel, Field
from pathlib import Path

class DatabaseConfig(BaseModel):
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="myapp", description="Database name")
    pool_size: int = Field(default=10, description="Connection pool size")

# cli/commands/database.py
from launchsampler.cli.model_cli_builder import ModelCLIBuilder, ValidatorRegistry

@ValidatorRegistry.register("pool_size")
def validate_pool_size(size: int) -> tuple[bool, str | None]:
    if size < 1:
        return False, "Pool size must be at least 1"
    if size > 100:
        return True, "Warning: Large pool sizes may consume excessive resources"
    return True, None

builder = ModelCLIBuilder(
    DatabaseConfig,
    config_path=Path.home() / ".myapp" / "database.json",
    field_overrides={
        "host": {"short": "h"},
        "port": {"short": "p"}
    }
)

database = builder.build_group(name="database")

# cli/main.py
import click
from .commands.database import database

@click.group()
def cli():
    """MyApp CLI"""
    pass

cli.add_command(database)
```

## Individual Command Builders

Instead of building a complete group, you can build individual commands:

```python
builder = ModelCLIBuilder(AppConfig, Path("config.json"))

# Build individual commands
show_cmd = builder.build_show_command()
set_cmd = builder.build_set_command()
validate_cmd = builder.build_validate_command()
reset_cmd = builder.build_reset_command()

# Add to custom group
@click.group()
def config():
    """Custom config group"""
    pass

config.add_command(show_cmd)
config.add_command(set_cmd)
# ... add more commands
```

## Best Practices

### 1. Model as Source of Truth

Define descriptions, types, and defaults in your Pydantic model:

```python
class Config(BaseModel):
    # Good: Description in model
    port: int = Field(
        default=8000,
        description="Server port number"
    )

    # Avoid: Description in field_overrides
    # (keeps CLI separate from model)
```

### 2. Use Field Descriptions

Always add descriptions to Pydantic fields - they become CLI help text:

```python
# Good
buffer_size: int = Field(
    default=512,
    description="Audio buffer size in frames"
)

# Bad - no help text generated
buffer_size: int = 512
```

### 3. Register Validators for Domain Logic

Use validators for domain-specific checks:

```python
@ValidatorRegistry.register("audio_device")
def validate_audio_device(device_id: int):
    # Check if device exists in system
    # Provide helpful error messages
    # Return warnings for non-ideal configurations
    ...
```

### 4. Hide Internal Fields

Don't expose internal fields in the CLI:

```python
builder = ModelCLIBuilder(
    Config,
    field_overrides={
        "_internal_state": {"expose": False},
        "debug_flag": {"expose": False}
    }
)
```

### 5. Provide Short Flags for Common Options

```python
field_overrides={
    "audio_device": {"short": "a"},
    "buffer_size": {"short": "b"},
    "config_file": {"short": "c"}
}
```

## Architecture

```
┌──────────────────────────┐
│ Pydantic Model           │
│ - Field definitions      │
│ - Type annotations       │
│ - Descriptions           │
│ - Defaults               │
└────────┬─────────────────┘
         │
         ↓
┌──────────────────────────┐
│ ModelCLIBuilder          │
│ - Type mapping           │
│ - Help generation        │
│ - Option creation        │
│ - Validator integration  │
└────────┬─────────────────┘
         │
         ↓
┌──────────────────────────┐
│ Click Commands           │
│ - show                   │
│ - set                    │
│ - validate               │
│ - reset                  │
└──────────────────────────┘
```

## Comparison with Manual CLI

### Manual Approach

```python
@click.command()
@click.option('--buffer-size', type=int, help='Audio buffer size')
@click.option('--auto-save', type=bool, help='Auto-save changes')
@click.option('--port', type=int, help='Server port')
# ... 20 more options ...
def config(buffer_size, auto_save, port, ...):
    # Manual validation
    # Manual loading
    # Manual saving
    # Manual error handling
    pass
```

### ModelCLIBuilder Approach

```python
builder = ModelCLIBuilder(AppConfig, Path("config.json"))
config = builder.build_group()
```

**Benefits:**
- ✅ Auto-updates when model changes
- ✅ Type-safe (Pydantic → Click)
- ✅ Consistent error handling
- ✅ Built-in validate/reset commands
- ✅ Less code (DRY principle)
- ✅ Model is single source of truth

## See Also

- `demo_model_cli_builder.py` - Complete working example
- `src/launchsampler/cli/commands/config_auto.py` - AppConfig example
- `ModelManagerService` - Backend service for model management
