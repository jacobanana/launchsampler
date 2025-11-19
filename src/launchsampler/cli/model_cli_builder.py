"""Generic CLI builder for Pydantic models with ModelManagerService.

This module provides a reusable framework for auto-generating CLI commands
from any Pydantic model. It maps Pydantic field types to Click types,
generates help text from field descriptions, and integrates with
ModelManagerService for type-safe configuration management.

Design Philosophy:
    - Model as source of truth: Types, defaults, descriptions from Pydantic
    - Generic and reusable: Works with any Pydantic BaseModel
    - Customizable: Field-level overrides and validation hooks
    - Auto-updating: Add field to model → CLI updates automatically

Example Usage:
    ```python
    from launchsampler.models import AppConfig
    from launchsampler.cli.model_cli_builder import ModelCLIBuilder

    # Create builder for AppConfig
    builder = ModelCLIBuilder(
        AppConfig,
        config_path=Path.home() / ".launchsampler" / "config.json",
        field_overrides={
            "default_audio_device": {
                "short": "a",
                "help": "Audio device ID (use 'launchsampler audio list')"
            }
        }
    )

    # Build commands
    config = click.Group(name='config')
    config.add_command(builder.build_show_command())
    config.add_command(builder.build_set_command())
    ```
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar, get_origin, get_args, Union

import click
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from launchsampler.services import ModelManagerService
from launchsampler.exceptions import ConfigurationError

logger = logging.getLogger(__name__)

# Type variable for any Pydantic model
ModelType = TypeVar('ModelType', bound=BaseModel)


class TypeMapper:
    """Maps Pydantic field types to Click parameter types."""

    # Basic type mappings
    MAPPINGS: Dict[Type, click.ParamType] = {
        int: click.INT,
        str: click.STRING,
        float: click.FLOAT,
        bool: click.BOOL,
        Path: click.Path(path_type=Path),
    }

    @classmethod
    def to_click_type(cls, python_type: Type) -> click.ParamType:
        """
        Convert a Python type annotation to a Click parameter type.

        Handles Optional[T], Union types, and basic Python types.

        Args:
            python_type: Python type annotation from Pydantic field

        Returns:
            Corresponding Click parameter type

        Example:
            ```python
            # Optional[int] → click.INT
            # str → click.STRING
            # Path → click.Path(path_type=Path)
            ```
        """
        # Handle Optional[T] (which is Union[T, None])
        origin = get_origin(python_type)
        if origin is Union:
            args = get_args(python_type)
            # Filter out NoneType to get the actual type
            non_none_types = [t for t in args if t is not type(None)]
            if non_none_types:
                python_type = non_none_types[0]

        # Look up in mappings
        click_type = cls.MAPPINGS.get(python_type)
        if click_type:
            return click_type

        # Default to STRING for unknown types
        logger.warning(f"Unknown type {python_type}, defaulting to click.STRING")
        return click.STRING


class ValidatorRegistry:
    """
    Registry for custom field validators.

    Validators can provide custom validation logic beyond Pydantic's
    built-in validation. They return (is_valid, message) tuples where
    the message is shown to the user.

    Example:
        ```python
        @ValidatorRegistry.register("default_audio_device")
        def validate_audio_device(value: int) -> tuple[bool, Optional[str]]:
            try:
                device = AudioDevice.get(value)
                return True, f"Using device: {device.name}"
            except ValueError:
                return False, "Device not found. Run 'launchsampler audio list'"
        ```
    """

    _validators: Dict[str, Callable[[Any], tuple[bool, Optional[str]]]] = {}

    @classmethod
    def register(cls, field_name: str):
        """
        Decorator to register a validator for a field.

        Args:
            field_name: Name of the model field to validate

        Returns:
            Decorator function
        """
        def decorator(func: Callable[[Any], tuple[bool, Optional[str]]]):
            cls._validators[field_name] = func
            return func
        return decorator

    @classmethod
    def validate(cls, field_name: str, value: Any) -> tuple[bool, Optional[str]]:
        """
        Run validation for a field if a validator is registered.

        Args:
            field_name: Name of the field
            value: Value to validate

        Returns:
            Tuple of (is_valid, message)
            - is_valid: True if validation passed
            - message: User-friendly message (error if invalid, info if valid)
        """
        validator = cls._validators.get(field_name)
        if validator:
            return validator(value)
        # No validator registered, accept value
        return True, None


class ModelCLIBuilder(Generic[ModelType]):
    """
    Generic CLI builder for Pydantic models.

    This class auto-generates Click commands from a Pydantic model,
    integrating with ModelManagerService for persistence and validation.

    Features:
        - Auto-generated options from model fields
        - Type mapping: Pydantic types → Click types
        - Help text from field descriptions
        - Custom validators via ValidatorRegistry
        - Field-level overrides for customization

    Type Parameters:
        ModelType: The Pydantic BaseModel subclass

    Example:
        ```python
        builder = ModelCLIBuilder(
            AppConfig,
            config_path=Path.home() / ".launchsampler" / "config.json",
            field_overrides={
                "buffer_size": {"short": "b"}
            }
        )

        # Generate commands
        show_cmd = builder.build_show_command()
        set_cmd = builder.build_set_command()
        ```
    """

    def __init__(
        self,
        model_type: Type[ModelType],
        config_path: Path,
        field_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
        expose_all: bool = True
    ):
        """
        Initialize the CLI builder.

        Args:
            model_type: Pydantic model class to build CLI for
            config_path: Default path for model persistence
            field_overrides: Per-field customization options
                - short: Short flag (e.g., "a" for -a)
                - help: Custom help text
                - expose: Whether to expose field in CLI (default: True)
                - type: Custom Click type override
            expose_all: Expose all fields by default (default: True)
        """
        self.model_type = model_type
        self.config_path = config_path
        self.field_overrides = field_overrides or {}
        self.expose_all = expose_all

    def _should_expose(self, field_name: str) -> bool:
        """
        Determine if a field should be exposed in the CLI.

        Args:
            field_name: Name of the field

        Returns:
            True if field should be exposed
        """
        overrides = self.field_overrides.get(field_name, {})
        return overrides.get("expose", self.expose_all)

    def _get_field_help(self, field_name: str, field_info: FieldInfo) -> str:
        """
        Generate help text for a field.

        Args:
            field_name: Name of the field
            field_info: Pydantic FieldInfo

        Returns:
            Help text string
        """
        overrides = self.field_overrides.get(field_name, {})

        # Use override help if provided
        if "help" in overrides:
            return overrides["help"]

        # Use field description from Pydantic
        if field_info.description:
            return field_info.description

        # Generate basic help
        return f"Set {field_name.replace('_', ' ')}"

    def _field_to_option(self, field_name: str, field_info: FieldInfo) -> click.Option:
        """
        Convert a Pydantic field to a Click option.

        Args:
            field_name: Name of the field
            field_info: Pydantic FieldInfo

        Returns:
            Click Option object
        """
        overrides = self.field_overrides.get(field_name, {})

        # Build option name
        option_name = f'--{field_name.replace("_", "-")}'
        flags = [option_name]

        # Add short flag if specified
        if "short" in overrides:
            flags.append(f'-{overrides["short"]}')

        # Get Click type
        if "type" in overrides:
            click_type = overrides["type"]
        else:
            click_type = TypeMapper.to_click_type(field_info.annotation)

        # Get help text
        help_text = self._get_field_help(field_name, field_info)

        # Add default value to help if present
        if field_info.default is not None and field_info.default != ...:
            help_text += f" (default: {field_info.default})"

        return click.Option(
            flags,
            type=click_type,
            default=None,  # None means "not provided by user"
            help=help_text
        )

    def build_show_command(self) -> click.Command:
        """
        Build a 'show' command that displays current configuration.

        Returns:
            Click Command for showing configuration

        Command:
            ```
            config show              # Show all fields
            config show --field name # Show specific field
            ```
        """
        @click.command(name='show')
        @click.option(
            '--field',
            '-f',
            type=str,
            default=None,
            help='Show specific field instead of all fields'
        )
        def show(field: Optional[str]):
            """Display current model configuration."""
            try:
                # Load model
                model = self.model_type.load_or_default(self.config_path)

                if field:
                    # Show specific field
                    if hasattr(model, field):
                        value = getattr(model, field)
                        click.echo(f"{field}: {value}")
                    else:
                        click.echo(f"Error: Field '{field}' does not exist", err=True)
                        return
                else:
                    # Show all fields
                    model_dict = model.model_dump()
                    click.echo(f"\n{self.model_type.__name__} Configuration:")
                    click.echo("=" * 60)
                    for key, value in model_dict.items():
                        if self._should_expose(key):
                            click.echo(f"  {key}: {value}")
                    click.echo("")

            except ConfigurationError as e:
                click.echo(f"Error: {e.user_message}", err=True)
                if e.recovery_hint:
                    click.echo(f"Hint: {e.recovery_hint}", err=True)

        return show

    def build_set_command(self) -> click.Command:
        """
        Build a 'set' command that updates field values.

        Returns:
            Click Command for setting fields

        Command:
            ```
            config set --field-name value [--other-field value ...]
            ```
        """
        # Dynamically create options from model fields
        def make_set_command():
            @click.command(name='set')
            def set_cmd(**kwargs):
                """Set one or more model field values."""
                # Filter out None values (fields not provided)
                updates = {k: v for k, v in kwargs.items() if v is not None}

                if not updates:
                    click.echo("Error: No fields specified. Use --help to see available options.", err=True)
                    return

                try:
                    # Load current model
                    model = self.model_type.load_or_default(self.config_path)

                    # Create service
                    service = ModelManagerService[self.model_type](
                        self.model_type,
                        model,
                        default_path=self.config_path
                    )

                    # Apply updates with validation
                    for field_name, value in updates.items():
                        # Run custom validator if registered
                        is_valid, message = ValidatorRegistry.validate(field_name, value)

                        if not is_valid:
                            click.echo(f"Error validating {field_name}: {message}", err=True)
                            return

                        # Set value
                        service.set(field_name, value)

                        # Show validation message if provided
                        if message:
                            click.echo(f"✓ {field_name}: {message}")
                        else:
                            click.echo(f"✓ {field_name} = {value}")

                    # Save
                    service.save()
                    click.echo(f"\nConfiguration saved to {self.config_path}")

                except ConfigurationError as e:
                    click.echo(f"Error: {e.user_message}", err=True)
                    if e.recovery_hint:
                        click.echo(f"Hint: {e.recovery_hint}", err=True)
                except Exception as e:
                    click.echo(f"Error: {e}", err=True)

            # Add options dynamically
            for field_name, field_info in self.model_type.model_fields.items():
                if self._should_expose(field_name):
                    option = self._field_to_option(field_name, field_info)
                    set_cmd = option(set_cmd)

            return set_cmd

        return make_set_command()

    def build_validate_command(self) -> click.Command:
        """
        Build a 'validate' command that checks configuration validity.

        Returns:
            Click Command for validating configuration

        Command:
            ```
            config validate  # Validate configuration file
            ```
        """
        @click.command(name='validate')
        def validate():
            """Validate the model configuration file."""
            try:
                # Try to load - this will validate
                model = self.model_type.load_or_default(self.config_path)
                click.echo(f"✓ {self.config_path} is valid")
                click.echo(f"  Model: {self.model_type.__name__}")
                click.echo(f"  Fields: {len(model.model_fields)}")

            except ConfigurationError as e:
                click.echo(f"✗ Validation failed: {e.user_message}", err=True)
                if e.recovery_hint:
                    click.echo(f"  Hint: {e.recovery_hint}", err=True)
                return 1

        return validate

    def build_reset_command(self) -> click.Command:
        """
        Build a 'reset' command that resets configuration to defaults.

        Returns:
            Click Command for resetting configuration

        Command:
            ```
            config reset              # Reset all fields
            config reset --field name # Reset specific field
            ```
        """
        @click.command(name='reset')
        @click.option(
            '--field',
            '-f',
            type=str,
            default=None,
            help='Reset specific field instead of all fields'
        )
        @click.confirmation_option(
            prompt='Are you sure you want to reset configuration?'
        )
        def reset(field: Optional[str]):
            """Reset configuration to defaults."""
            try:
                if field:
                    # Reset specific field
                    model = self.model_type.load_or_default(self.config_path)
                    service = ModelManagerService[self.model_type](
                        self.model_type,
                        model,
                        default_path=self.config_path
                    )

                    # Get default value
                    default_model = self.model_type()
                    default_value = getattr(default_model, field)

                    # Set to default
                    service.set(field, default_value)
                    service.save()

                    click.echo(f"✓ Reset {field} to default: {default_value}")
                else:
                    # Reset all fields
                    default_model = self.model_type()
                    service = ModelManagerService[self.model_type](
                        self.model_type,
                        default_model,
                        default_path=self.config_path
                    )
                    service.save()

                    click.echo(f"✓ Reset all fields to defaults")

                click.echo(f"  Configuration saved to {self.config_path}")

            except ConfigurationError as e:
                click.echo(f"Error: {e.user_message}", err=True)
                if e.recovery_hint:
                    click.echo(f"Hint: {e.recovery_hint}", err=True)

        return reset

    def build_group(self, name: str = "config", help: Optional[str] = None) -> click.Group:
        """
        Build a complete Click group with all commands.

        Args:
            name: Name of the command group
            help: Help text for the group

        Returns:
            Click Group with show/set/validate/reset commands

        Example:
            ```python
            builder = ModelCLIBuilder(AppConfig, ...)
            config = builder.build_group()
            cli.add_command(config)
            ```
        """
        if help is None:
            help = f"Manage {self.model_type.__name__} configuration"

        group = click.Group(name=name, help=help)
        group.add_command(self.build_show_command())
        group.add_command(self.build_set_command())
        group.add_command(self.build_validate_command())
        group.add_command(self.build_reset_command())

        return group
