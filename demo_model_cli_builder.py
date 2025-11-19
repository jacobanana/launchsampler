"""
Demonstration of ModelCLIBuilder with different Pydantic models.

This script shows how ModelCLIBuilder can work with any Pydantic model
to auto-generate CLI commands.

Run with:
    python3 demo_model_cli_builder.py --help
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pydantic import BaseModel, Field

# Import the builder (will fail gracefully if dependencies missing)
try:
    from launchsampler.cli.model_cli_builder import ModelCLIBuilder, ValidatorRegistry
    import click
except ImportError as e:
    print(f"✗ Missing dependencies: {e}")
    print("Install with: pip install click pydantic")
    sys.exit(1)


# ===================================================================
# Example 1: Simple Server Configuration
# ===================================================================

class ServerConfig(BaseModel):
    """Configuration for a web server."""

    host: str = "localhost"
    port: int = Field(default=8000, description="Server port number")
    debug: bool = Field(default=False, description="Enable debug mode")
    workers: int = Field(default=4, description="Number of worker processes")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")


# Register custom validator for port
@ValidatorRegistry.register("port")
def validate_port(port: int) -> tuple[bool, Optional[str]]:
    """Validate port is in valid range."""
    if port < 1 or port > 65535:
        return False, "Port must be between 1 and 65535"
    if port < 1024:
        return True, f"Warning: Port {port} requires root/admin privileges"
    return True, None


# ===================================================================
# Example 2: Database Configuration
# ===================================================================

class DatabaseConfig(BaseModel):
    """Configuration for database connection."""

    host: str = "localhost"
    port: int = 5432
    database: str = "myapp"
    username: str = Field(default="postgres", description="Database username")
    password: Optional[str] = Field(default=None, description="Database password")
    pool_size: int = Field(default=10, description="Connection pool size")
    ssl: bool = Field(default=True, description="Use SSL connection")


# ===================================================================
# Example 3: Application Configuration (Like AppConfig)
# ===================================================================

class AppSettings(BaseModel):
    """General application settings."""

    app_name: str = "MyApp"
    version: str = "1.0.0"
    log_level: str = Field(default="INFO", description="Logging level (DEBUG/INFO/WARNING/ERROR)")
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".myapp")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    auto_update: bool = Field(default=True, description="Automatically check for updates")


# ===================================================================
# Build CLI
# ===================================================================

@click.group()
def cli():
    """Demo of ModelCLIBuilder with multiple models."""
    pass


# Server config command
server_builder = ModelCLIBuilder(
    ServerConfig,
    config_path=Path("/tmp/server_config.json"),
    field_overrides={
        "port": {"short": "p"},
        "host": {"short": "h"},
        "workers": {"short": "w"}
    }
)
cli.add_command(server_builder.build_group(name="server", help="Configure server settings"))


# Database config command
db_builder = ModelCLIBuilder(
    DatabaseConfig,
    config_path=Path("/tmp/database_config.json"),
    field_overrides={
        "password": {"expose": False},  # Don't expose password in CLI
        "port": {"short": "p"},
        "host": {"short": "h"}
    }
)
cli.add_command(db_builder.build_group(name="database", help="Configure database settings"))


# App settings command
app_builder = ModelCLIBuilder(
    AppSettings,
    config_path=Path("/tmp/app_settings.json")
)
cli.add_command(app_builder.build_group(name="app", help="Configure application settings"))


# ===================================================================
# Demonstration
# ===================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ModelCLIBuilder Demonstration")
    print("=" * 60)
    print()
    print("This demo shows how ModelCLIBuilder works with ANY Pydantic model.")
    print()
    print("Try these commands:")
    print()
    print("  # Server configuration")
    print("  python3 demo_model_cli_builder.py server show")
    print("  python3 demo_model_cli_builder.py server set --port 8080 --workers 8")
    print("  python3 demo_model_cli_builder.py server reset --field port")
    print()
    print("  # Database configuration")
    print("  python3 demo_model_cli_builder.py database show")
    print("  python3 demo_model_cli_builder.py database set --host db.example.com")
    print("  python3 demo_model_cli_builder.py database validate")
    print()
    print("  # App settings")
    print("  python3 demo_model_cli_builder.py app show")
    print("  python3 demo_model_cli_builder.py app set --log-level DEBUG")
    print()
    print("=" * 60)
    print()

    # Run CLI
    cli()
