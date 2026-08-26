# noqa: D100

import hashlib
import os
import re
import shutil
import stat
import sys
import tempfile
import textwrap

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import ClassVar, TYPE_CHECKING

from attrs import define
from dbrownell_Common.ContextlibEx import ExitStack
from dbrownell_Common import SubprocessEx, TextwrapEx
from jinja2 import Environment, meta

from dbrownell_Dotter.Configuration import (
    CommandConfigurationEntry,
    Configuration,
    PostInstallConfigurationEntry,
    SourceConfigurationEntry,
    SubstituteConfigurationEntry,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from dbrownell_Common.Streams.DoneManager import DoneManager


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class Entry(ABC):
    """Content to be installed on the local machine."""

    dynamic_variables: dict[str, object] | None = None
    """Dynamic variables used when rendering this entry's content. These variables will be added to the jinja environment's global variables."""

    # ----------------------------------------------------------------------
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Value that identifies this entry on the terminal."""

    # ----------------------------------------------------------------------
    @abstractmethod
    def Install(self, dm: DoneManager, *, force: bool, dry_run: bool) -> str | None:
        """Install the entry and return a description of what was done (or None when nothing was)."""

    # ----------------------------------------------------------------------
    @abstractmethod
    def ReverseSync(self, dm: DoneManager, untemplater: _Untemplater, *, dry_run: bool) -> str | None:
        """Sync changes from the destination back to the source and return a description of what was done (or None when nothing was)."""


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class CommandEntry(Entry):
    """Commands run via a temporary script."""

    name: str
    """Rendered display name."""

    commands: list[str]
    """Rendered commands to run."""

    # ----------------------------------------------------------------------
    @property
    def display_name(self) -> str:  # noqa: D102
        return self.name

    # ----------------------------------------------------------------------
    def Install(self, dm: DoneManager, *, force: bool, dry_run: bool) -> str | None:  # noqa: ARG002, D102
        dm.WriteVerbose("\n{}\n\n".format("\n".join(self.commands)))

        if not dry_run:
            with _TemporaryScript(self.commands) as script_filename:
                result = SubprocessEx.Run(f'"{script_filename}"')

                if result.returncode == 0:
                    dm.WriteVerbose(result.output)
                else:
                    dm.WriteError(result.output)

        return "Executed"

    # ----------------------------------------------------------------------
    def ReverseSync(  # noqa: D102
        self,
        dm: DoneManager,  # noqa: ARG002
        untemplater: _Untemplater,  # noqa: ARG002
        *,
        dry_run: bool,  # noqa: ARG002
    ) -> str | None:
        return "Skipped Commands"


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class DestinationEntry(Entry):
    """Content associated with a destination on the local filesystem."""

    dest: Path
    """Destination path."""

    make_executable: bool = False
    """Set the execute flag on the destination; only valid when the destination is a file."""

    _action_desc: ClassVar[str]
    """Description displayed once the content has been applied to the destination."""

    # ----------------------------------------------------------------------
    @property
    def display_name(self) -> str:  # noqa: D102
        return str(self.dest)

    # ----------------------------------------------------------------------
    def Install(self, dm: DoneManager, *, force: bool, dry_run: bool) -> str | None:  # noqa: D102
        should_apply, skip_desc = self._PrepareDestination(dm, force=force, dry_run=dry_run)

        if not should_apply:
            return skip_desc

        if not dry_run:
            self.dest.parent.mkdir(parents=True, exist_ok=True)
            self._Apply()

            if self.make_executable:
                if self.dest.is_file():
                    self.dest.chmod(
                        self.dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
                    )
                else:
                    dm.WriteError("'make_executable' is only valid when the destination is a file.")

        return self._action_desc

    # ----------------------------------------------------------------------
    def ReverseSync(self, dm: DoneManager, untemplater: _Untemplater, *, dry_run: bool) -> str | None:  # noqa: D102
        if not self.dest.exists():
            dm.WriteError("The destination does not exist.")
            return None

        return self._ReverseSyncDestination(dm, untemplater, dry_run=dry_run)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _PrepareDestination(
        self,
        dm: DoneManager,
        *,
        force: bool,
        dry_run: bool,
    ) -> tuple[bool, str | None]:
        """Return (apply the content, description to display when the content is not applied)."""

        if self.dest.exists() or self.dest.is_symlink():
            if not force:
                return False, "Already exists"

            with dm.Nested("Removing{}...".format(" (dry_run)" if dry_run else "")):
                if not dry_run:
                    if self.dest.is_file() or self.dest.is_symlink():
                        self.dest.unlink()
                    elif self.dest.is_dir():
                        shutil.rmtree(self.dest)
                    else:
                        assert False, self.dest  # noqa: B011, PT015  # pragma: no cover

        return True, None

    # ----------------------------------------------------------------------
    @abstractmethod
    def _Apply(self) -> None:
        """Apply the content to the destination."""

    # ----------------------------------------------------------------------
    @abstractmethod
    def _ReverseSyncDestination(
        self,
        dm: DoneManager,
        untemplater: _Untemplater,
        *,
        dry_run: bool,
    ) -> str | None:
        """Sync changes from the existing destination back to the source."""


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class SubstituteEntry(DestinationEntry):
    """Regex substitutions applied to an existing destination file."""

    substitutions: list[tuple[re.Pattern[str], str]]
    """List of (pattern, rendered_replacement) tuples."""

    _action_desc: ClassVar[str] = "Substituted"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _PrepareDestination(
        self,
        dm: DoneManager,
        *,
        force: bool,  # noqa: ARG002
        dry_run: bool,  # noqa: ARG002
    ) -> tuple[bool, str | None]:
        # Unlike other entries, an existing destination is modified rather than replaced.
        if not self.dest.exists():
            dm.WriteError("Destination does not exist.")
            return False, None

        if not self.dest.is_file():
            dm.WriteError("Destination is not a file.")
            return False, None

        return True, None

    # ----------------------------------------------------------------------
    def _Apply(self) -> None:
        content = self.dest.read_text(encoding="utf-8")

        for pattern, replacement in self.substitutions:
            content = pattern.sub(replacement, content)

        self.dest.write_text(content, encoding="utf-8")

    # ----------------------------------------------------------------------
    def _ReverseSyncDestination(
        self,
        dm: DoneManager,  # noqa: ARG002
        untemplater: _Untemplater,  # noqa: ARG002
        *,
        dry_run: bool,  # noqa: ARG002
    ) -> str | None:
        return "Skipped Substitution"


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class SourceEntry(DestinationEntry):
    """Content produced from a source on the local filesystem."""

    source: Path
    """Source path to a file or directory."""

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _ReverseSyncDestination(
        self,
        dm: DoneManager,
        untemplater: _Untemplater,
        *,
        dry_run: bool,
    ) -> str | None:
        action_info = self._CreateReverseSyncAction(untemplater)

        if action_info is None:
            return "No changes detected"

        action, action_desc = action_info

        if action is not None and not dry_run:
            with dm.Nested("Removing source content..."):
                if self.source.is_file():
                    self.source.unlink()
                elif self.source.is_dir():
                    shutil.rmtree(self.source)
                else:
                    assert False, self.source  # noqa: B011, PT015  # pragma: no cover

            action()

        return action_desc

    # ----------------------------------------------------------------------
    @abstractmethod
    def _CreateReverseSyncAction(
        self,
        untemplater: _Untemplater,
    ) -> tuple[Callable[[], object] | None, str | None] | None:
        """Return (action that updates the source, description) or None when the source is already up to date."""


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class CopyEntry(SourceEntry):
    """Source copied to the destination."""

    _action_desc: ClassVar[str] = "Copied"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _Apply(self) -> None:
        if self.source.is_file():
            shutil.copy2(self.source, self.dest)
        else:
            shutil.copytree(self.source, self.dest)

    # ----------------------------------------------------------------------
    def _CreateReverseSyncAction(
        self,
        untemplater: _Untemplater,  # noqa: ARG002
    ) -> tuple[Callable[[], object] | None, str | None] | None:
        if self.dest.is_file():
            if not self.source.is_file() or _CalcFileHash(self.dest) != _CalcFileHash(self.source):
                return lambda: shutil.copy2(self.dest, self.source), "Copied file"
        elif not self.source.is_dir() or not _DirectoriesMatch(self.dest, self.source):
            return lambda: shutil.copytree(self.dest, self.source), "Copied directory"

        return None


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class LinkEntry(SourceEntry):
    """Symlink at the destination that points to the source."""

    _action_desc: ClassVar[str] = "Linked"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _Apply(self) -> None:
        self.dest.symlink_to(self.source, target_is_directory=self.source.is_dir())

    # ----------------------------------------------------------------------
    def _CreateReverseSyncAction(
        self,
        untemplater: _Untemplater,  # noqa: ARG002
    ) -> tuple[Callable[[], object] | None, str | None] | None:
        # The destination is the source, so there is nothing to sync.
        return None, "Skipped Symlink"


# ----------------------------------------------------------------------
@define(frozen=True, kw_only=True)
class WriteEntry(SourceEntry):
    """Rendered template content written to the destination."""

    rendered_content: str
    """Rendered template content."""

    _action_desc: ClassVar[str] = "Wrote"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _Apply(self) -> None:
        self.dest.write_text(self.rendered_content, encoding="utf-8")

    # ----------------------------------------------------------------------
    def _ReverseSyncDestination(
        self,
        dm: DoneManager,
        untemplater: _Untemplater,
        *,
        dry_run: bool,
    ) -> str | None:
        if not self.dest.is_file():
            dm.WriteError("Destination is not a file.")
            return None

        return super()._ReverseSyncDestination(dm, untemplater, dry_run=dry_run)

    # ----------------------------------------------------------------------
    def _CreateReverseSyncAction(
        self,
        untemplater: _Untemplater,
    ) -> tuple[Callable[[], object] | None, str | None] | None:
        if _CalcFileHash(self.dest) == _CalcStringHash(self.rendered_content):
            return None

        content = untemplater(self.dynamic_variables or {}, self.dest)

        return lambda: self.source.write_text(content, encoding="utf-8"), "Wrote template"


# ----------------------------------------------------------------------
@define(frozen=True)
class ResolvedContent:
    """Content resolved from configuration files."""

    entries: list[Entry]
    """Entries to be processed."""

    post_install_instructions: list[str]
    """Rendered instructions to display once the install process completes without errors."""


# ----------------------------------------------------------------------
@define(frozen=True)
class DefaultDynamicVariable:
    """Default dynamic variables that are always available for use in the configuration."""

    name: str
    """Name of the variable."""

    description: str
    """Description of the variable."""

    value: object | Callable[[Path], object]
    """Value of the variable, or a callable that generates the value given the configuration file path."""


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
DEFAULT_DYNAMIC_VARIABLES: list[DefaultDynamicVariable] = [
    DefaultDynamicVariable(
        "configuration_file_dir",
        "The directory containing the configuration file. Can be used for resolving relative paths in the configuration.",
        lambda config_path: str(config_path.parent),
    ),
    DefaultDynamicVariable(
        "configuration_file_name",
        "The name of the configuration file. Can be used for resolving relative paths in the configuration.",
        lambda config_path: config_path.name,
    ),
    DefaultDynamicVariable(
        "home_dir",
        "The current user's home directory. Can be used for resolving paths in the configuration.",
        str(Path.home()),
    ),
    DefaultDynamicVariable(
        "is_linux",
        "True if the current platform is Linux. Can be used for platform-specific conditions in the configuration.",
        sys.platform.startswith("linux"),
    ),
    DefaultDynamicVariable(
        "is_macos",
        "True if the current platform is macOS. Can be used for platform-specific conditions in the configuration.",
        sys.platform == "darwin",
    ),
    DefaultDynamicVariable(
        "is_windows",
        "True if the current platform is Windows. Can be used for platform-specific conditions in the configuration.",
        sys.platform.startswith("win"),
    ),
]


# ----------------------------------------------------------------------
def ResolveEntries(  # noqa: C901, PLR0912, PLR0915
    env: Environment,
    config_filenames: list[Path],
    *,
    force_symbolic_links: bool = False,
) -> ResolvedContent:
    """Resolve the configuration data into content that can be processed."""

    results: list[Entry] = []
    post_install_instructions: list[str] = []
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
        # Create the dynamic variables
        dynamic_variables: dict[str, object] = {
            var.name: var.value(config_filename) if callable(var.value) else var.value  # ty: ignore[call-top-callable]
            for var in DEFAULT_DYNAMIC_VARIABLES
        }

        # Apply the dynamic variables to the Jinja environment
        for key, value in dynamic_variables.items():
            assert key not in env.globals, key
            env.globals[key] = value  # ty: ignore[invalid-assignment]

        # ----------------------------------------------------------------------
        def RemoveDynamicVariables() -> None:
            for key in dynamic_variables:  # noqa: B023
                del env.globals[key]

        # ----------------------------------------------------------------------

        with ExitStack(RemoveDynamicVariables):
            config = Configuration.FromFile(config_filename)

            for entry in config.entries:
                # Evaluate the condition if present
                if entry.condition is not None:
                    condition_expression = entry.condition.strip()

                    # Support the documented expression syntax while remaining
                    # compatible with existing template-style conditions.
                    if condition_expression.startswith("{{") and condition_expression.endswith("}}"):
                        condition_expression = condition_expression[2:-2].strip()

                    if this_missing_vars := meta.find_undeclared_variables(
                        env.parse("{{ " + condition_expression + " }}")
                    ):
                        ProcessMissingVars(config, config_filename, this_missing_vars)
                        continue

                    condition_result = env.compile_expression(
                        condition_expression,
                        undefined_to_none=False,
                    )()

                    if not bool(condition_result):
                        continue

                if isinstance(entry, CommandConfigurationEntry):
                    values_to_render = [entry.name, *entry.commands]
                    rendered_values: list[str] = []

                    for value in values_to_render:
                        if this_missing_vars := meta.find_undeclared_variables(env.parse(value)):
                            ProcessMissingVars(config, config_filename, this_missing_vars)
                        else:
                            rendered_values.append(_Populate(env, value))

                    if len(rendered_values) == len(values_to_render):
                        results.append(
                            CommandEntry(
                                name=rendered_values[0],
                                commands=rendered_values[1:],
                                dynamic_variables=dynamic_variables,
                            ),
                        )

                    continue

                if isinstance(entry, PostInstallConfigurationEntry):
                    if this_missing_vars := meta.find_undeclared_variables(
                        env.parse(entry.post_install_instructions)
                    ):
                        ProcessMissingVars(config, config_filename, this_missing_vars)
                    else:
                        post_install_instructions.append(
                            _Populate(env, entry.post_install_instructions),
                        )

                    continue

                has_errors = False

                dest: Path | None = None
                new_entry: DestinationEntry | None = None

                # Process the dest
                if this_missing_vars := meta.find_undeclared_variables(env.parse(entry.dest)):
                    ProcessMissingVars(config, config_filename, this_missing_vars)
                    has_errors = True
                else:
                    dest = Path(_Populate(env, entry.dest)).expanduser().absolute()

                if isinstance(entry, SourceConfigurationEntry):
                    source = (config_filename.parent / entry.source).expanduser().absolute()

                    # Process the source if it is a template
                    if source.suffix in [".jinja", ".jinja2", ".j2"]:
                        content = source.read_text(encoding="utf-8")

                        if this_missing_vars := meta.find_undeclared_variables(env.parse(content)):
                            ProcessMissingVars(config, source, this_missing_vars)
                            has_errors = True
                        elif dest is not None:
                            new_entry = WriteEntry(
                                source=source,
                                dest=dest,
                                rendered_content=_Populate(env, content),
                                dynamic_variables=dynamic_variables,
                                make_executable=entry.make_executable,
                            )
                    elif dest is not None:
                        entry_type = (
                            LinkEntry if (force_symbolic_links or source.drive == dest.drive) else CopyEntry
                        )

                        new_entry = entry_type(
                            source=source,
                            dest=dest,
                            dynamic_variables=dynamic_variables,
                            make_executable=entry.make_executable,
                        )
                elif isinstance(entry, SubstituteConfigurationEntry):
                    substitutions: list[tuple[re.Pattern[str], str]] = []

                    for sub in entry.substitutions:
                        # Process the replacement string for Jinja/env vars
                        if this_missing_vars := meta.find_undeclared_variables(env.parse(sub.replacement)):
                            ProcessMissingVars(config, config_filename, this_missing_vars)
                            has_errors = True
                        else:
                            substitutions.append(
                                (
                                    re.compile(sub.pattern, re.MULTILINE),
                                    _Populate(env, sub.replacement),
                                ),
                            )

                    if not has_errors and dest is not None:
                        new_entry = SubstituteEntry(
                            dest=dest,
                            substitutions=substitutions,
                            dynamic_variables=dynamic_variables,
                            make_executable=entry.make_executable,
                        )
                else:
                    assert False, entry  # noqa: B011, PT015  # pragma: no cover

                if not has_errors:
                    assert new_entry is not None
                    results.append(new_entry)

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

    return ResolvedContent(results, post_install_instructions)


# ----------------------------------------------------------------------
def DisplayPostInstallInstructions(dm: DoneManager, post_install_instructions: list[str]) -> None:
    """Display the instructions produced by the configuration files."""

    header = textwrap.dedent(
        """\
        Post-Install Instructions
        -------------------------""",
    )

    if dm.capabilities.supports_colors:
        header = f"{TextwrapEx.BRIGHT_GREEN_COLOR_ON}{header}{TextwrapEx.COLOR_OFF}"

    items: list[str] = []

    for index, instructions in enumerate(post_install_instructions):
        prefix = "{}) ".format(index + 1)

        items.append(prefix + TextwrapEx.Indent(instructions.strip(), len(prefix), skip_first_line=True))

    dm.WriteLine("\n{}\n{}\n\n".format(header, "\n\n".join(items)))


# ----------------------------------------------------------------------
def InstallEntries(
    dm: DoneManager,
    entries: list[Entry],
    *,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Process the action associated with each entry."""

    _ProcessEntries(
        dm,
        entries,
        lambda entry_dm, entry: entry.Install(entry_dm, force=force, dry_run=dry_run),
        dry_run=dry_run,
    )


# ----------------------------------------------------------------------
def ReverseSyncEntries(
    dm: DoneManager,
    entries: list[Entry],
    template_vars: dict[str, object],
    *,
    dry_run: bool = False,
) -> None:
    """Sync changes from the destination back to the source for each entry."""

    untemplater = _Untemplater(template_vars)

    _ProcessEntries(
        dm,
        entries,
        lambda entry_dm, entry: entry.ReverseSync(entry_dm, untemplater, dry_run=dry_run),
        dry_run=dry_run,
    )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _ProcessEntries(
    dm: DoneManager,
    entries: list[Entry],
    process_func: Callable[[DoneManager, Entry], str | None],
    *,
    dry_run: bool,
) -> None:
    action_template = "{} (dry_run)" if dry_run else "{}"

    for entry_index, entry in enumerate(entries):
        _ProcessEntry(
            dm,
            entry,
            "'{}' ({} of {})...".format(entry.display_name, entry_index + 1, len(entries)),
            action_template,
            process_func,
        )


# ----------------------------------------------------------------------
def _ProcessEntry(
    dm: DoneManager,
    entry: Entry,
    heading: str,
    action_template: str,
    process_func: Callable[[DoneManager, Entry], str | None],
) -> None:
    # Invoked outside of the enclosing loop so that the closure below does not capture a loop variable.
    action_desc: str | None = None

    with dm.Nested(
        heading,
        lambda: None if action_desc is None else action_template.format(action_desc),
    ) as entry_dm:
        action_desc = process_func(entry_dm, entry)


# ----------------------------------------------------------------------
@contextmanager
def _TemporaryScript(commands: list[str]) -> Iterator[Path]:
    # Commands are written to a script (rather than invoked individually) so that state established
    # by one command is visible to those that follow it.
    if os.name == "nt":
        extension = ".cmd"
        prefix = "@echo off\n"

        # cmd transfers control permanently when one script invokes another without 'call', which
        # would silently abandon the commands that follow. 'call' is a no-op for everything else.
        command_prefix = "call "

        # Terminate the script as soon as a command fails.
        command_suffix = "\nif %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%"
    else:
        extension = ".sh"

        # Terminate the script as soon as a command fails.
        prefix = "#!/usr/bin/env sh\nset -e\n"

        command_prefix = ""
        command_suffix = ""

    temp_directory = Path(tempfile.mkdtemp())

    with ExitStack(lambda: shutil.rmtree(temp_directory, ignore_errors=True)):
        filename = temp_directory / f"commands{extension}"

        filename.write_text(
            prefix + "".join(f"{command_prefix}{command}{command_suffix}\n" for command in commands),
            encoding="utf-8",
        )
        filename.chmod(filename.stat().st_mode | stat.S_IXUSR)

        yield filename


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
            (key, str(value))
            for key, value in os.environ.items()
            if len(str(value)) >= min_variable_length and not str(value).isdigit()
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
    def __call__(self, dynamic_variables: dict[str, object], filename: Path) -> str:
        content = filename.read_text(encoding="utf-8")

        for var, value in self.environment_vars:
            content = content.replace(value, f"${{{var}}}")

        for var, value in self.template_vars:
            content = content.replace(value, f"{{{{ {var} }}}}")

        for var, value in sorted(dynamic_variables.items(), key=lambda x: len(str(x[1])), reverse=True):
            content = content.replace(str(value), f"{{{{ {var} }}}}")

        return content
