# noqa: D100

import hashlib
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
    from collections.abc import Callable

    from dbrownell_Common.Streams.DoneManager import DoneManager


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class Action(Enum):
    """Action to perform for an entry."""

    Copy = auto()
    """Copy the source to the destination."""

    Link = auto()
    """Symlink the source to the destination."""

    Write = auto()
    """Write the source content to the destination."""


# ----------------------------------------------------------------------
@define(frozen=True)
class Entry:
    """Content to be copied from source to dest."""

    action: Action
    """Action to perform for this entry."""

    source: Path
    """Source path to a file or directory."""

    dest: Path
    """Destination path."""

    rendered_content: str | None = None
    """Rendered template content when the source is a Jinja template."""


# ----------------------------------------------------------------------
def ResolveEntries(env: Environment, config_filenames: list[Path]) -> list[Entry]:
    """Resolve the configuration data into a list of entries that can be processed."""

    results: list[Entry] = []
    all_missing_vars: dict[Path, set[str]] = {}

    # ----------------------------------------------------------------------
    def ProcessMissingVars(config: Configuration, filename: Path, missing_vars: set[str]) -> None:
        for missing_var in missing_vars:
            error_msg = missing_var

            if definition := config.variable_definitions.get(missing_var):
                error_msg += f" : {definition}"

            all_missing_vars.setdefault(filename, set()).add(error_msg)

    # ----------------------------------------------------------------------

    for config_filename in config_filenames:
        config = Configuration.FromFile(config_filename)

        for entry in config.entries:
            has_errors = False

            action: Action | None = None
            dest: Path | None = None
            source: Path = (config_filename.parent / entry.source).expanduser().resolve()
            rendered_content: str | None = None

            # Process the dest
            if this_missing_vars := meta.find_undeclared_variables(env.parse(entry.dest)):
                ProcessMissingVars(config, config_filename, this_missing_vars)
                has_errors = True
            else:
                dest = Path(_Populate(env, entry.dest)).expanduser().resolve()

            # Process the source if it is a template
            if source.suffix in [".jinja", ".jinja2", ".j2"]:
                action = Action.Write

                content = source.read_text(encoding="utf-8")

                if this_missing_vars := meta.find_undeclared_variables(env.parse(content)):
                    ProcessMissingVars(config, source, this_missing_vars)
                    has_errors = True
                else:
                    rendered_content = _Populate(env, content)
            elif dest:
                action = Action.Link if source.drive == dest.drive else Action.Copy

            if not has_errors:
                assert action
                assert dest
                results.append(Entry(action, source, dest, rendered_content))

    if all_missing_vars:
        sections: list[str] = [
            textwrap.dedent(
                """\
                '{}':
                {}
                """,
            ).format(
                filename,
                "\n".join(f"    - {var}" for var in sorted(all_missing_vars[filename])),
            )
            for filename in sorted(all_missing_vars)
        ]

        msg = textwrap.dedent(
            """\
            The following variables are used in the configuration but are not defined:

            {}
            """,
        ).format(TextwrapEx.Indent("\n".join(sections), 4))

        raise ValueError(msg)

    return results


# ----------------------------------------------------------------------
def InstallEntries(
    dm: DoneManager,
    entries: list[Entry],
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

            if entry.action == Action.Copy:
                if entry.source.is_file():
                    action = lambda: shutil.copy2(entry.source, entry.dest)  # noqa: B023, E731
                else:
                    action = lambda: shutil.copytree(entry.source, entry.dest)  # noqa: B023, E731

                action_desc = "Copied"

            elif entry.action == Action.Link:
                action = lambda: entry.dest.symlink_to(  # noqa: B023, E731
                    entry.source,  # noqa: B023
                    target_is_directory=entry.source.is_dir(),  # noqa: B023
                )
                action_desc = "Linked"

            elif entry.action == Action.Write:
                assert entry.rendered_content is not None, entry

                action = lambda: entry.dest.write_text(entry.rendered_content, encoding="utf-8")  # noqa: B023, E731  # ty: ignore[invalid-argument-type]
                action_desc = "Wrote"

            else:
                assert False, entry.action  # noqa: B011, PT015  # pragma: no cover

            if not dry_run:
                entry.dest.parent.mkdir(parents=True, exist_ok=True)
                action()


# ----------------------------------------------------------------------
def ReverseSyncEntries(
    dm: DoneManager,
    entries: list[Entry],
    template_vars: dict[str, object],
    *,
    dry_run: bool = False,
) -> None:
    """Sync changes from the destination back to the source for each entry."""

    untemplater: _Untemplater | None = None

    action_template = "{} (dry_run)" if dry_run else "{}"

    for entry_index, entry in enumerate(entries):
        action_desc: str | None = None

        with dm.Nested(
            "Processing '{}' ({} of {})...".format(entry.dest, entry_index + 1, len(entries)),
            lambda: None if action_desc is None else action_template.format(action_desc),  # noqa: B023
        ) as entry_dm:
            if not entry.dest.exists():
                entry_dm.WriteError("The destination does not exist.")
                continue

            if entry.action == Action.Link:
                action_desc = "Skipped SymLink"
                continue

            action: Callable[[], None] | None = None

            if entry.action == Action.Copy:
                if entry.dest.is_file():
                    if not entry.source.is_file() or _CalcFileHash(entry.dest) != _CalcFileHash(entry.source):
                        action = lambda: shutil.copy2(entry.dest, entry.source)  # noqa: B023, E731
                        action_desc = "Copied file"
                else:  # noqa: PLR5501
                    if not entry.source.is_dir() or not _DirectoriesMatch(entry.dest, entry.source):
                        action = lambda: shutil.copytree(entry.dest, entry.source)  # noqa: B023, E731
                        action_desc = "Copied directory"

            elif entry.action == Action.Write:
                if not entry.dest.is_file():
                    entry_dm.WriteError("Destination is not a file.")
                    continue

                assert entry.rendered_content is not None, entry

                if _CalcFileHash(entry.dest) != _CalcStringHash(entry.rendered_content):
                    if untemplater is None:
                        untemplater = _Untemplater(template_vars)

                    content = untemplater(entry.dest)

                    action = lambda: entry.source.write_text(content, encoding="utf-8")  # noqa: B023, E731  # ty: ignore[invalid-argument-type]
                    action_desc = "Wrote template"

            else:
                assert False, entry.action  # noqa: B011, PT015  # pragma: no cover

            if action is None:
                action_desc = "No changes detected"
            elif not dry_run:
                assert action_desc is not None

                with entry_dm.Nested("Removing source content..."):
                    if entry.source.is_file():
                        entry.source.unlink()
                    else:
                        assert entry.source.is_dir(), entry.source
                        shutil.rmtree(entry.source)

                action()


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _Populate(env: Environment, content: str) -> str:
    content = env.from_string(content).render()
    content = os.path.expandvars(content)

    return content  # noqa: RET504


# ----------------------------------------------------------------------
def _CalcFileHash(path: Path) -> bytes:
    hasher = hashlib.sha256()

    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break

            hasher.update(chunk)

    return hasher.digest()


# ----------------------------------------------------------------------
def _CalcStringHash(content: str) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(content.encode("utf-8"))
    return hasher.digest()


# ----------------------------------------------------------------------
def _DirectoriesMatch(dir1: Path, dir2: Path) -> bool:
    dir1_files = _GetDirectoryFiles(dir1)
    dir2_files = _GetDirectoryFiles(dir2)

    if dir1_files != dir2_files:
        return False

    return all(
        _CalcFileHash(dir1 / file1) == _CalcFileHash(dir2 / file2)
        for file1, file2 in zip(sorted(dir1_files), sorted(dir2_files), strict=True)
    )


# ----------------------------------------------------------------------
def _GetDirectoryFiles(directory: Path) -> set[Path]:
    results: set[Path] = set()

    for root_str, _, files in os.walk(directory):
        root = Path(root_str)

        for file in files:
            results.add((root / file).relative_to(directory))

    return results


# ----------------------------------------------------------------------
class _Untemplater:
    # ----------------------------------------------------------------------
    def __init__(self, original_template_vars: dict[str, object]) -> None:
        min_variable_length = 2

        environment_vars = [
            (key, str(value)) for key, value in os.environ.items() if len(str(value)) >= min_variable_length
        ]
        environment_vars = sorted(environment_vars, key=lambda x: len(x[1]), reverse=True)

        template_vars = [
            (key, str(value))
            for key, value in original_template_vars.items()
            if len(str(value)) >= min_variable_length
        ]
        template_vars = sorted(template_vars, key=lambda x: len(x[1]), reverse=True)

        self.environment_vars = environment_vars
        self.template_vars = template_vars

    # ----------------------------------------------------------------------
    def __call__(self, filename: Path) -> str:
        content = filename.read_text(encoding="utf-8")

        for var, value in self.environment_vars:
            content = content.replace(value, f"${{{var}}}")

        for var, value in self.template_vars:
            content = content.replace(value, f"{{{{ {var} }}}}")

        return content
