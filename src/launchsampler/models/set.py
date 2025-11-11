"""Set model for saving/loading pad configurations."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .launchpad import Launchpad


class Set(BaseModel):
    """A saved configuration of pad assignments."""

    name: str = Field(description="Set name")
    launchpad: Launchpad = Field(description="Launchpad configuration")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    modified_at: datetime = Field(default_factory=datetime.now, description="Last modified timestamp")
    description: Optional[str] = Field(default=None, description="Optional description")

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

    def update_timestamp(self) -> None:
        """Update the modified_at timestamp."""
        self.modified_at = datetime.now()

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
