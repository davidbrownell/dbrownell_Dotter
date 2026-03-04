# noqa: D100

import os
import shutil
import textwrap

from enum import auto, Enum
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import define
from dbrownell_Common import TextwrapEx
from jinja2 import Environment, meta

from dbrownell_Dotter.Configuration import Configuration

if TYPE_CHECKING:
    from dbrownell_Common.Streams.DoneManager import DoneManager


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class InstallAction(Enum):
    """Action to perform for an entry."""

    Copy = auto()
    """Copy the source to the destination."""

    Link = auto()
    """Symlink the source to the destination."""

    Write = auto()
    """Write the source content to the destination."""


# ----------------------------------------------------------------------
@define(frozen=True)
class InstallEntry:
    """Content to be copied from source to dest."""

    action: InstallAction
    """Action to perform for this entry."""

    source: Path
    """Source path to a file or directory."""

    dest: Path
    """Destination path."""

    rendered_content: str | None = None
    """Rendered template content when the source is a Jinja template."""


# ----------------------------------------------------------------------
def ResolveInstallEntries(env: Environment, config_filenames: list[Path]) -> list[InstallEntry]:
    """Resolve the configuration data into a list of entries that can be processed."""

    results: list[InstallEntry] = []
    missing_vars: dict[Path, set[str]] = {}

    for config_filename in config_filenames:
        config = Configuration.FromFile(config_filename)

        for entry in config.entries:
            has_errors = False

            action: InstallAction | None = None
            dest: Path | None = None
            source: Path = (config_filename.parent / entry.source).expanduser().resolve()
            rendered_content: str | None = None

            # Process the dest
            if this_missing_vars := meta.find_undeclared_variables(env.parse(entry.dest)):
                missing_vars.setdefault(config_filename, set()).update(this_missing_vars)
                has_errors = True
            else:
                dest = Path(_Populate(env, entry.dest)).expanduser().resolve()

            # Process the source if it is a template
            if source.suffix in [".jinja", ".jinja2", ".j2"]:
                action = InstallAction.Write

                content = source.read_text(encoding="utf-8")

                if this_missing_vars := meta.find_undeclared_variables(env.parse(content)):
                    missing_vars.setdefault(source, set()).update(this_missing_vars)
                    has_errors = True
                else:
                    rendered_content = _Populate(env, content)
            elif dest:
                action = InstallAction.Link if source.drive == dest.drive else InstallAction.Copy

            if not has_errors:
                assert action
                assert dest
                results.append(InstallEntry(action, source, dest, rendered_content))

    if missing_vars:
        sections: list[str] = []

        for filename in sorted(missing_vars):
            variable_definitions: list[str] = []

            for var in sorted(missing_vars[filename]):
                description = f"    - {var}"

                if (definition := config.variable_definitions.get(var)) is not None:
                    description += f" : {definition}"

                variable_definitions.append(description)

            sections.append(
                textwrap.dedent(
                    """\
                    '{}':
                    {}
                    """,
                ).format(filename, "\n".join(variable_definitions)),
            )

        msg = textwrap.dedent(
            """\
            The following variables are used in the configuration but are not defined:

            {}
            """,
        ).format(TextwrapEx.Indent("\n".join(sections), 4))

        raise ValueError(msg)

    return results


# ----------------------------------------------------------------------
def ProcessInstallEntries(
    dm: DoneManager,
    entries: list[InstallEntry],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Process the action associated with each entry."""

    action_template = "{} (dry_run)" if dry_run else "{}"

    for entry_index, entry in enumerate(entries):
        action_desc: str | None = None

        with dm.Nested(
            "Processing '{}' ({} of {})...".format(entry.dest, entry_index + 1, len(entries)),
            lambda: (
                None if action_desc is None else action_template.format(action_desc)  # noqa: B023
            ),
        ) as entry_dm:
            if entry.dest.exists():
                if force:
                    with entry_dm.Nested("Removing{}...".format(" (dry_run)" if dry_run else "")):
                        if not dry_run:
                            if entry.dest.is_file():
                                entry.dest.unlink()
                            else:
                                shutil.rmtree(entry.dest)
                else:
                    action_desc = "Already exists"
                    continue

            if entry.action == InstallAction.Copy:
                if entry.source.is_file():
                    action = lambda: shutil.copy2(entry.source, entry.dest)  # noqa: B023, E731
                else:
                    action = lambda: shutil.copytree(entry.source, entry.dest)  # noqa: B023, E731

                action_desc = "Copied"

            elif entry.action == InstallAction.Link:
                action = lambda: entry.dest.symlink_to(  # noqa: B023, E731
                    entry.source,  # noqa: B023
                    target_is_directory=entry.source.is_dir(),  # noqa: B023
                )
                action_desc = "Linked"

            elif entry.action == InstallAction.Write:
                assert entry.rendered_content is not None, entry

                action = lambda: entry.dest.write_text(entry.rendered_content, encoding="utf-8")  # noqa: B023, E731  # ty: ignore[invalid-argument-type]
                action_desc = "Wrote"

            else:
                assert False, entry.action  # noqa: B011, PT015  # pragma: no cover

            if not dry_run:
                entry.dest.parent.mkdir(parents=True, exist_ok=True)
                action()


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _Populate(env: Environment, content: str) -> str:
    content = env.from_string(content).render()
    content = os.path.expandvars(content)

    return content  # noqa: RET504
