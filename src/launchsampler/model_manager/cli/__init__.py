"""CLI generation framework for Pydantic models.

This package provides tools for auto-generating Click CLI commands from
Pydantic models, with type mapping, validation, and customization support.

Public API:
    - ModelCLIBuilder: Main builder for generating CLI commands
    - TypeMapper: Maps Pydantic field types to Click parameter types
    - ValidatorRegistry: Registry for custom field validators

Example:
    ```python
    from launchsampler.model_manager.cli import ModelCLIBuilder
    from myapp.models import AppConfig

    builder = ModelCLIBuilder(
        AppConfig,
        config_path=Path("~/.myapp/config.json"),
        field_overrides={
            "port": {"short": "p", "help": "Server port"}
        }
    )

    # Generate complete command group
    config = builder.build_group()
    cli.add_command(config)

    # Usage:
    # myapp config              -> show all fields
    # myapp config set -p 8080  -> set port
    # myapp config validate     -> validate config
    # myapp config reset        -> reset to defaults
    ```
"""

from launchsampler.model_manager.cli.builder import (
    ModelCLIBuilder,
    TypeMapper,
    ValidatorRegistry,
)

__all__ = [
    "ModelCLIBuilder",
    "TypeMapper",
    "ValidatorRegistry",
]
