# noqa: D100

from pathlib import Path  # noqa: TC003
from typing import Self

import json5
import yaml

from attrs import define
from cattrs import structure


# ----------------------------------------------------------------------
@define(frozen=True)
class ConfigurationEntry:
    """Represents a single entry in the configuration file."""

    source: Path
    """Relative path to the source file/directory"""

    dest: str
    """Value may include environment variables or jinja2 template variables"""


# ----------------------------------------------------------------------
@define(frozen=True)
class Configuration:
    """Represents the entire configuration file."""

    variable_definitions: dict[str, str]
    """Dictionary of variable definitions that can be used in source content and dest paths"""

    entries: list[ConfigurationEntry]
    """List of configuration entries"""

    # ----------------------------------------------------------------------
    @classmethod
    def FromFile(cls, filename: Path) -> Self:
        """Load the configuration from a file."""

        if not filename.is_file():
            msg = f"'{filename}' does not exist."
            raise ValueError(msg)

        if filename.suffix in [".yaml", ".yml"]:
            with filename.open(encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
        elif filename.suffix in [".json", ".json5"]:
            with filename.open(encoding="utf-8") as f:
                content = json5.load(f)
        else:
            msg = f"'{filename}' is not a supported file type."
            raise ValueError(msg)

        return structure(content, cls)
