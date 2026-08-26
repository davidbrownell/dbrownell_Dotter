# noqa: D100

from pathlib import Path  # noqa: TC003
from typing import Self

import json5
import yaml

from attrs import define
from cattrs import structure


# ----------------------------------------------------------------------
@define(frozen=True)
class Substitution:
    """Represents a single regex substitution to apply."""

    pattern: str
    """Regex pattern to match."""

    replacement: str
    """Replacement string. May include environment variables or jinja2 template variables."""


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class ConfigurationEntry:
    """Attributes common to all entries in the configuration file."""

    condition: str | None = None
    """Optional jinja2 expression that must evaluate to true for this entry to be applied at runtime."""


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class SourceConfigurationEntry(ConfigurationEntry):
    """An entry that copies, links, or renders a source file/directory to a destination."""

    source: Path
    """Relative path to the source file/directory."""

    dest: str
    """Value may include environment variables or jinja2 template variables."""

    make_executable: bool = False
    """Set the execute flag on the destination; only valid when the destination is a file."""


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class SubstituteConfigurationEntry(ConfigurationEntry):
    """An entry that applies regex substitutions to an existing destination file."""

    dest: str
    """Value may include environment variables or jinja2 template variables."""

    substitutions: list[Substitution]
    """List of regex substitutions to apply to an existing file."""

    make_executable: bool = False
    """Set the execute flag on the destination; only valid when the destination is a file."""

    # ----------------------------------------------------------------------
    def __attrs_post_init__(self) -> None:
        if not self.substitutions:
            msg = "'substitutions' must contain at least one item."
            raise ValueError(msg)


# ----------------------------------------------------------------------
ConfigurationEntryTypes = SourceConfigurationEntry | SubstituteConfigurationEntry
"""All concrete configuration entry types; cattrs uses this union to determine the type of each entry."""


# ----------------------------------------------------------------------
@define(frozen=True)
class Configuration:
    """Represents the entire configuration file."""

    variable_definitions: dict[str, str]
    """Dictionary of variable definitions that can be used in source content and dest paths"""

    entries: list[ConfigurationEntryTypes]
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
