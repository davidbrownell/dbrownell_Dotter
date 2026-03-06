# noqa: D100

import hashlib
import os
import re
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

    Substitute = auto()
    """Apply regex substitutions to an existing file."""


# ----------------------------------------------------------------------
@define(frozen=True)
class Entry:
    """Content to be copied from source to dest."""

    action: Action
    """Action to perform for this entry."""

    source: Path | None
    """Source path to a file or directory. None for Substitute actions."""

    dest: Path
    """Destination path."""

    rendered_content: str | None = None
    """Rendered template content when the source is a Jinja template."""

    substitutions: list[tuple[re.Pattern[str], str]] | None = None
    """List of (pattern, rendered_replacement) tuples for Substitute actions."""


# ----------------------------------------------------------------------
def ResolveEntries(env: Environment, config_filenames: list[Path]) -> list[Entry]:  # noqa: PLR0915
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
        env.globals["configuration_file_dir"] = config_filename.parent

        config = Configuration.FromFile(config_filename)

        for entry in config.entries:
            has_errors = False

            action: Action | None = None
            source: Path | None = None
            dest: Path | None = None
            rendered_content: str | None = None
            substitutions: list[tuple[re.Pattern[str], str]] | None = None

            # Process the dest
            if this_missing_vars := meta.find_undeclared_variables(env.parse(entry.dest)):
                ProcessMissingVars(config, config_filename, this_missing_vars)
                has_errors = True
            else:
                dest = Path(_Populate(env, entry.dest)).expanduser().absolute()

            if entry.source is not None:
                # We are looking at a Write, Link, or Copy

                source = (config_filename.parent / entry.source).expanduser().absolute()

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
            else:
                # We are looking at a Substitute
                assert entry.substitutions, entry

                action = Action.Substitute
                resolved_substitutions: list[tuple[re.Pattern[str], str]] = []

                for sub in entry.substitutions:
                    # Process the replacement string for Jinja/env vars
                    if this_missing_vars := meta.find_undeclared_variables(env.parse(sub.replacement)):
                        ProcessMissingVars(config, config_filename, this_missing_vars)
                        has_errors = True
                    else:
                        resolved_substitutions.append(
                            (
                                re.compile(sub.pattern, re.MULTILINE),
                                _Populate(env, sub.replacement),
                            ),
                        )

                substitutions = resolved_substitutions

            if not has_errors:
                assert action
                assert dest
                results.append(Entry(action, source, dest, rendered_content, substitutions))

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
def InstallEntries(  # noqa: C901, PLR0915
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
            "'{}' ({} of {})...".format(entry.dest, entry_index + 1, len(entries)),
            lambda: (
                None if action_desc is None else action_template.format(action_desc)  # noqa: B023
            ),
        ) as entry_dm:
            # Substitute action requires the dest to exist (we're modifying an existing file)
            if entry.action == Action.Substitute:
                if not entry.dest.exists():
                    entry_dm.WriteError("Destination does not exist.")
                    continue
            elif entry.dest.exists() or entry.dest.is_symlink():
                if force:
                    with entry_dm.Nested("Removing{}...".format(" (dry_run)" if dry_run else "")):
                        if not dry_run:
                            if entry.dest.is_file() or entry.dest.is_symlink():
                                entry.dest.unlink()
                            elif entry.dest.is_dir():
                                shutil.rmtree(entry.dest)
                            else:
                                assert False, entry.dest  # noqa: B011, PT015  # pragma: no cover
                else:
                    action_desc = "Already exists"
                    continue

            if entry.action == Action.Copy:
                assert entry.source is not None, entry

                if entry.source.is_file():
                    action = lambda: shutil.copy2(entry.source, entry.dest)  # noqa: B023, E731  # ty: ignore[no-matching-overload]
                else:
                    action = lambda: shutil.copytree(entry.source, entry.dest)  # noqa: B023, E731  # ty: ignore[invalid-argument-type]

                action_desc = "Copied"

            elif entry.action == Action.Link:
                assert entry.source is not None, entry

                action = lambda: entry.dest.symlink_to(  # noqa: B023, E731
                    entry.source,  # noqa: B023  # ty: ignore[invalid-argument-type]
                    target_is_directory=entry.source.is_dir(),  # noqa: B023  # ty: ignore[unresolved-attribute]
                )
                action_desc = "Linked"

            elif entry.action == Action.Write:
                assert entry.rendered_content is not None, entry

                action = lambda: entry.dest.write_text(entry.rendered_content, encoding="utf-8")  # noqa: B023, E731  # ty: ignore[invalid-argument-type]
                action_desc = "Wrote"

            elif entry.action == Action.Substitute:
                assert entry.substitutions is not None, entry

                if not entry.dest.is_file():
                    entry_dm.WriteError("Destination is not a file.")
                    continue

                # ----------------------------------------------------------------------
                def ApplySubstitutions(entry: Entry) -> None:
                    assert entry.substitutions is not None

                    content = entry.dest.read_text(encoding="utf-8")

                    for pattern, replacement in entry.substitutions:
                        content = pattern.sub(replacement, content)

                    entry.dest.write_text(content, encoding="utf-8")

                # ----------------------------------------------------------------------

                action = lambda entry=entry: ApplySubstitutions(entry)  # noqa: E731
                action_desc = "Substituted"

            else:
                assert False, entry.action  # noqa: B011, PT015  # pragma: no cover

            if not dry_run:
                entry.dest.parent.mkdir(parents=True, exist_ok=True)
                action()


# ----------------------------------------------------------------------
def ReverseSyncEntries(  # noqa: C901, PLR0915
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
            "'{}' ({} of {})...".format(entry.dest, entry_index + 1, len(entries)),
            lambda: None if action_desc is None else action_template.format(action_desc),  # noqa: B023
        ) as entry_dm:
            if not entry.dest.exists():
                entry_dm.WriteError("The destination does not exist.")
                continue

            if entry.action == Action.Link:
                action_desc = "Skipped Symlink"
                continue

            if entry.action == Action.Substitute:
                action_desc = "Skipped Substitution"
                continue

            action: Callable[[], None] | None = None

            if entry.action == Action.Copy:
                assert entry.source is not None, entry

                if entry.dest.is_file():
                    if not entry.source.is_file() or _CalcFileHash(entry.dest) != _CalcFileHash(entry.source):
                        action = lambda: shutil.copy2(entry.dest, entry.source)  # noqa: B023, E731  # ty: ignore[no-matching-overload]
                        action_desc = "Copied file"
                else:  # noqa: PLR5501
                    if not entry.source.is_dir() or not _DirectoriesMatch(entry.dest, entry.source):
                        action = lambda: shutil.copytree(entry.dest, entry.source)  # noqa: B023, E731  # ty: ignore[invalid-argument-type]
                        action_desc = "Copied directory"

            elif entry.action == Action.Write:
                assert entry.source is not None, entry

                if not entry.dest.is_file():
                    entry_dm.WriteError("Destination is not a file.")
                    continue

                assert entry.rendered_content is not None, entry

                if _CalcFileHash(entry.dest) != _CalcStringHash(entry.rendered_content):
                    if untemplater is None:
                        untemplater = _Untemplater(template_vars)

                    content = untemplater(entry.dest)

                    action = lambda: entry.source.write_text(content, encoding="utf-8")  # noqa: B023, E731  # ty: ignore[unresolved-attribute]
                    action_desc = "Wrote template"

            else:
                assert False, entry.action  # noqa: B011, PT015  # pragma: no cover

            if action is None:
                action_desc = "No changes detected"
            elif not dry_run:
                assert action_desc is not None
                assert entry.source is not None, entry

                with entry_dm.Nested("Removing source content..."):
                    if entry.source.is_file():
                        entry.source.unlink()
                    elif entry.source.is_dir():
                        assert entry.source.is_dir(), entry.source
                        shutil.rmtree(entry.source)
                    else:
                        assert False, entry.source  # noqa: B011, PT015  # pragma: no cover

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
