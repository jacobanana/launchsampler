"""Set model for saving/loading pad configurations."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_serializer

from .launchpad import Launchpad


class Set(BaseModel):
    """A saved configuration of pad assignments."""

    name: str = Field(description="Set name")
    launchpad: Launchpad = Field(description="Launchpad configuration")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    modified_at: datetime = Field(default_factory=datetime.now, description="Last modified timestamp")

    @field_serializer("created_at", "modified_at")
    def serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime to ISO format."""
        return dt.isoformat()

    def save_to_file(self, path: Path) -> None:
        """Save set to JSON file."""
        path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load_from_file(cls, path: Path) -> "Set":
        """Load set from JSON file."""
        return cls.model_validate_json(path.read_text())

    @classmethod
    def create_empty(cls, name: str) -> "Set":
        """Create a new empty set."""
        return cls(
            name=name,
            launchpad=Launchpad.create_empty()
        )
