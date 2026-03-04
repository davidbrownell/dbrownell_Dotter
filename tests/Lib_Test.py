import sys
import textwrap

from pathlib import Path
from typing import cast

import pytest

from dbrownell_Common.Streams.DoneManager import DoneManager
from dbrownell_Common.TestHelpers.StreamTestHelpers import GenerateDoneManagerAndContent
from jinja2 import Environment

from dbrownell_Dotter.Lib import Entry, EntryAction, ProcessEntries, ResolveEntries


# ----------------------------------------------------------------------
class TestResolveEntries:
    # ----------------------------------------------------------------------
    def test_empty_config_list(self) -> None:
        """Test with an empty list of config files."""

        env = Environment()

        entries = ResolveEntries(env, [])

        assert entries == []

    # ----------------------------------------------------------------------
    def test_empty_entries_in_config(self, tmp_path: Path) -> None:
        """Test with a config file that has no entries."""

        env = Environment()

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                variable_definitions: {}
                entries: []
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert entries == []

    # ----------------------------------------------------------------------
    def test_link_action_same_drive(self, tmp_path: Path) -> None:
        """Test that Link action is used when source and dest are on the same drive."""

        env = Environment()

        source_file = tmp_path / "source.txt"
        source_file.write_text("content", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest_path = tmp_path / "dest.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source.txt
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].action == EntryAction.Link
        assert entries[0].source == source_file.resolve()
        assert entries[0].dest == dest_path.resolve()

    # ----------------------------------------------------------------------
    @pytest.mark.skipif(
        sys.platform != "win32", reason="Linux-based operating systems do not have multiple drives."
    )
    def test_copy_action_different_drives(self, tmp_path: Path) -> None:
        """Test that Copy action is used when source and dest are on different drives."""

        env = Environment()

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                """\
                variable_definitions: {}
                entries:
                  - source: C:/source.txt
                    dest: D:/dest.txt
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].action == EntryAction.Copy
        assert entries[0].source == Path("C:/source.txt").resolve()
        assert entries[0].dest == Path("D:/dest.txt").resolve()

    # ----------------------------------------------------------------------
    def test_write_action_jinja_template(self, tmp_path: Path) -> None:
        """Test that Write action is used for .jinja template files."""

        env = Environment()
        env.globals["name"] = "World"

        template_file = tmp_path / "template.txt.jinja"
        template_file.write_text("Hello {{ name }}!", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest_path = tmp_path / "output.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: template.txt.jinja
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].action == EntryAction.Write
        assert entries[0].source == "Hello World!"
        assert entries[0].dest == dest_path.resolve()

    # ----------------------------------------------------------------------
    def test_write_action_jinja2_extension(self, tmp_path: Path) -> None:
        """Test that Write action is used for .jinja2 template files."""

        env = Environment()
        env.globals["value"] = "42"

        template_file = tmp_path / "template.txt.jinja2"
        template_file.write_text("Value: {{ value }}", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest_path = tmp_path / "output.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: template.txt.jinja2
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].action == EntryAction.Write
        assert entries[0].source == "Value: 42"

    # ----------------------------------------------------------------------
    def test_write_action_j2_extension(self, tmp_path: Path) -> None:
        """Test that Write action is used for .j2 template files."""

        env = Environment()
        env.globals["item"] = "test"

        template_file = tmp_path / "template.txt.j2"
        template_file.write_text("Item: {{ item }}", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest_path = tmp_path / "output.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: template.txt.j2
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].action == EntryAction.Write
        assert entries[0].source == "Item: test"

    # ----------------------------------------------------------------------
    def test_jinja_variable_in_dest(self, tmp_path: Path) -> None:
        """Test Jinja variable substitution in destination path."""

        env = Environment()
        env.globals["folder"] = "output_folder"

        source_file = tmp_path / "source.txt"
        source_file.write_text("content", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source.txt
                    dest: {tmp_path.as_posix()}/{{{{ folder }}}}/dest.txt
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].dest == (tmp_path / "output_folder" / "dest.txt").resolve()

    # ----------------------------------------------------------------------
    def test_environment_variable_in_dest(self, tmp_path: Path, monkeypatch) -> None:
        """Test environment variable substitution in destination path."""

        env = Environment()
        monkeypatch.setenv("TEST_DEST_DIR", "env_folder")

        source_file = tmp_path / "source.txt"
        source_file.write_text("content", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source.txt
                    dest: {tmp_path.as_posix()}/${{TEST_DEST_DIR}}/dest.txt
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].dest == (tmp_path / "env_folder" / "dest.txt").resolve()

    # ----------------------------------------------------------------------
    def test_environment_variable_in_template_content(self, tmp_path: Path, monkeypatch) -> None:
        """Test environment variable substitution in Jinja template content."""

        env = Environment()
        monkeypatch.setenv("MY_ENV_VALUE", "environment_value")

        template_file = tmp_path / "template.txt.jinja"
        template_file.write_text("Env: ${MY_ENV_VALUE}", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest_path = tmp_path / "output.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: template.txt.jinja
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].source == "Env: environment_value"

    # ----------------------------------------------------------------------
    def test_missing_variable_in_dest_raises_error(self, tmp_path: Path) -> None:
        """Test that missing Jinja variables in dest path raise ValueError."""

        env = Environment()

        source_file = tmp_path / "source.txt"
        source_file.write_text("content", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source.txt
                    dest: {tmp_path.as_posix()}/{{{{ undefined_var }}}}/dest.txt
                """,
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ResolveEntries(env, [config_file])

        assert str(exc_info.value) == textwrap.dedent(
            f"""\
            The following variables are used in the configuration but are not defined:

                '{config_file}':
                    - undefined_var

            """,
        )

    # ----------------------------------------------------------------------
    def test_missing_variable_in_template_content_raises_error(self, tmp_path: Path) -> None:
        """Test that missing Jinja variables in template content raise ValueError."""

        env = Environment()

        template_file = tmp_path / "template.txt.jinja"
        template_file.write_text("Hello {{ missing_name }}!", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest_path = tmp_path / "output.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: template.txt.jinja
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ResolveEntries(env, [config_file])

        assert str(exc_info.value) == textwrap.dedent(
            f"""\
            The following variables are used in the configuration but are not defined:

                '{template_file}':
                    - missing_name

            """,
        )

    # ----------------------------------------------------------------------
    def test_multiple_missing_variables(self, tmp_path: Path) -> None:
        """Test error message when multiple variables are missing."""

        env = Environment()

        template_file = tmp_path / "template.txt.jinja"
        template_file.write_text("{{ var1 }} and {{ var2 }}", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: template.txt.jinja
                    dest: {tmp_path.as_posix()}/{{{{ var3 }}}}/output.txt
                """,
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ResolveEntries(env, [config_file])

        assert str(exc_info.value) == textwrap.dedent(
            f"""\
            The following variables are used in the configuration but are not defined:

                '{config_file}':
                    - var3

                '{template_file}':
                    - var1
                    - var2

            """,
        )

    # ----------------------------------------------------------------------
    def test_multiple_config_files(self, tmp_path: Path) -> None:
        """Test processing multiple configuration files."""

        env = Environment()

        source1 = tmp_path / "dir1" / "source1.txt"
        source1.parent.mkdir(parents=True, exist_ok=True)
        source1.write_text("content1", encoding="utf-8")

        source2 = tmp_path / "dir2" / "source2.txt"
        source2.parent.mkdir(parents=True, exist_ok=True)
        source2.write_text("content2", encoding="utf-8")

        config1 = tmp_path / "dir1" / "config1.yaml"
        dest1 = tmp_path / "dest1.txt"
        config1.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source1.txt
                    dest: {dest1.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        config2 = tmp_path / "dir2" / "config2.yaml"
        dest2 = tmp_path / "dest2.txt"
        config2.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source2.txt
                    dest: {dest2.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config1, config2])

        assert len(entries) == 2
        assert entries[0].source == source1.resolve()
        assert entries[0].dest == dest1.resolve()
        assert entries[1].source == source2.resolve()
        assert entries[1].dest == dest2.resolve()

    # ----------------------------------------------------------------------
    def test_multiple_entries_in_single_config(self, tmp_path: Path) -> None:
        """Test processing multiple entries from a single config file."""

        env = Environment()

        source1 = tmp_path / "source1.txt"
        source1.write_text("content1", encoding="utf-8")

        source2 = tmp_path / "source2.txt"
        source2.write_text("content2", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest1 = tmp_path / "dest1.txt"
        dest2 = tmp_path / "dest2.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source1.txt
                    dest: {dest1.as_posix()}
                  - source: source2.txt
                    dest: {dest2.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 2
        assert entries[0].action == EntryAction.Link
        assert entries[1].action == EntryAction.Link

    # ----------------------------------------------------------------------
    def test_combined_jinja_and_env_vars(self, tmp_path: Path, monkeypatch) -> None:
        """Test combining Jinja variables and environment variables."""

        env = Environment()
        env.globals["jinja_var"] = "jinja_part"
        monkeypatch.setenv("ENV_PART", "env_part")

        template_file = tmp_path / "template.txt.jinja"
        template_file.write_text(
            "Jinja: {{ jinja_var }}, Env: ${ENV_PART}",
            encoding="utf-8",
        )

        config_file = tmp_path / "config.yaml"
        dest_path = tmp_path / "output.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: template.txt.jinja
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].source == "Jinja: jinja_part, Env: env_part"

    # ----------------------------------------------------------------------
    def test_source_resolved_relative_to_config_parent(self, tmp_path: Path) -> None:
        """Test that source paths are resolved relative to config file's parent directory."""

        env = Environment()

        subdir = tmp_path / "configs" / "subdir"
        subdir.mkdir(parents=True, exist_ok=True)

        source_file = subdir / "source.txt"
        source_file.write_text("content", encoding="utf-8")

        config_file = subdir / "config.yaml"
        dest_path = tmp_path / "dest.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source.txt
                    dest: {dest_path.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        entries = ResolveEntries(env, [config_file])

        assert len(entries) == 1
        assert entries[0].source == source_file.resolve()

    # ----------------------------------------------------------------------
    def test_entry_skipped_when_dest_has_missing_vars(self, tmp_path: Path) -> None:
        """Test that entries with missing dest vars are skipped but other entries process."""

        env = Environment()
        env.globals["defined_var"] = "value"

        source1 = tmp_path / "source1.txt"
        source1.write_text("content1", encoding="utf-8")

        source2 = tmp_path / "source2.txt"
        source2.write_text("content2", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        dest2 = tmp_path / "dest2.txt"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions: {{}}
                entries:
                  - source: source1.txt
                    dest: {tmp_path.as_posix()}/{{{{ undefined_var }}}}/dest1.txt
                  - source: source2.txt
                    dest: {dest2.as_posix()}
                """,
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ResolveEntries(env, [config_file])

        assert str(exc_info.value) == textwrap.dedent(
            f"""\
            The following variables are used in the configuration but are not defined:

                '{config_file}':
                    - undefined_var

            """,
        )

    # ----------------------------------------------------------------------
    def test_missing_variable_with_definition_in_config(self, tmp_path: Path) -> None:
        """Test that variable definitions are shown in error message for missing variables."""

        env = Environment()

        source_file = tmp_path / "source.txt"
        source_file.write_text("content", encoding="utf-8")

        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            textwrap.dedent(
                f"""\
                variable_definitions:
                  my_var: "Description of my_var"
                entries:
                  - source: source.txt
                    dest: {tmp_path.as_posix()}/{{{{ my_var }}}}/dest.txt
                """,
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as exc_info:
            ResolveEntries(env, [config_file])

        assert str(exc_info.value) == textwrap.dedent(
            f"""\
            The following variables are used in the configuration but are not defined:

                '{config_file}':
                    - my_var : Description of my_var

            """,
        )


# ----------------------------------------------------------------------
class TestProcessEntries:
    # ----------------------------------------------------------------------
    def test_write_action(self, tmp_path: Path) -> None:
        """Test that Write action writes string content to dest file."""

        dest_path = tmp_path / "output.txt"
        entries = [Entry(EntryAction.Write, "Hello, World!", dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert dest_path.exists()
        assert dest_path.read_text(encoding="utf-8") == "Hello, World!"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Wrote)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_copy_action_file(self, tmp_path: Path) -> None:
        """Test that Copy action copies a file to dest."""

        source_file = tmp_path / "source.txt"
        source_file.write_text("source content", encoding="utf-8")

        dest_path = tmp_path / "dest.txt"
        entries = [Entry(EntryAction.Copy, source_file, dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert dest_path.exists()
        assert dest_path.read_text(encoding="utf-8") == "source content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Copied)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_copy_action_directory(self, tmp_path: Path) -> None:
        """Test that Copy action copies a directory tree to dest."""

        source_dir = tmp_path / "source_dir"
        source_dir.mkdir()
        (source_dir / "file1.txt").write_text("file1 content", encoding="utf-8")
        (source_dir / "subdir").mkdir()
        (source_dir / "subdir" / "file2.txt").write_text("file2 content", encoding="utf-8")

        dest_path = tmp_path / "dest_dir"
        entries = [Entry(EntryAction.Copy, source_dir, dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert dest_path.exists()
        assert dest_path.is_dir()
        assert (dest_path / "file1.txt").read_text(encoding="utf-8") == "file1 content"
        assert (dest_path / "subdir" / "file2.txt").read_text(encoding="utf-8") == "file2 content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Copied)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_link_action(self, tmp_path: Path) -> None:
        """Test that Link action creates a symlink to source."""

        source_file = tmp_path / "source.txt"
        source_file.write_text("source content", encoding="utf-8")

        dest_path = tmp_path / "link.txt"
        entries = [Entry(EntryAction.Link, source_file, dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert dest_path.exists()
        assert dest_path.is_symlink()
        assert dest_path.read_text(encoding="utf-8") == "source content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Linked)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_dest_already_exists_no_force(self, tmp_path: Path) -> None:
        """Test that existing dest is skipped when force=False."""

        dest_path = tmp_path / "output.txt"
        dest_path.write_text("existing content", encoding="utf-8")

        entries = [Entry(EntryAction.Write, "new content", dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries, force=False)

        content = cast(str, next(dm_and_content))

        assert dest_path.read_text(encoding="utf-8") == "existing content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Already exists)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_dest_already_exists_with_force_file(self, tmp_path: Path) -> None:
        """Test that existing dest file is removed and recreated when force=True."""

        dest_path = tmp_path / "output.txt"
        dest_path.write_text("existing content", encoding="utf-8")

        entries = [Entry(EntryAction.Write, "new content", dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries, force=True)

        content = cast(str, next(dm_and_content))

        assert dest_path.read_text(encoding="utf-8") == "new content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...
                Removing...DONE! (0, <scrubbed duration>)
              DONE! (0, <scrubbed duration>, Wrote)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_dest_already_exists_with_force_directory(self, tmp_path: Path) -> None:
        """Test that existing dest directory is removed and recreated when force=True."""

        source_file = tmp_path / "source.txt"
        source_file.write_text("source content", encoding="utf-8")

        dest_path = tmp_path / "dest_dir"
        dest_path.mkdir()
        (dest_path / "old_file.txt").write_text("old content", encoding="utf-8")

        entries = [Entry(EntryAction.Copy, source_file, dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries, force=True)

        content = cast(str, next(dm_and_content))

        assert dest_path.exists()
        assert dest_path.is_file()
        assert dest_path.read_text(encoding="utf-8") == "source content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...
                Removing...DONE! (0, <scrubbed duration>)
              DONE! (0, <scrubbed duration>, Copied)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_dry_run(self, tmp_path: Path) -> None:
        """Test that dry_run=True does not perform actual file operations."""

        dest_path = tmp_path / "output.txt"
        entries = [Entry(EntryAction.Write, "Hello, World!", dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries, dry_run=True)

        content = cast(str, next(dm_and_content))

        assert not dest_path.exists()
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Wrote (dry_run))
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_dry_run_with_force_existing_file(self, tmp_path: Path) -> None:
        """Test that dry_run=True with force=True does not remove existing file."""

        dest_path = tmp_path / "output.txt"
        dest_path.write_text("existing content", encoding="utf-8")

        entries = [Entry(EntryAction.Write, "new content", dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries, force=True, dry_run=True)

        content = cast(str, next(dm_and_content))

        assert dest_path.read_text(encoding="utf-8") == "existing content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...
                Removing (dry_run)...DONE! (0, <scrubbed duration>)
              DONE! (0, <scrubbed duration>, Wrote (dry_run))
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_multiple_entries(self, tmp_path: Path) -> None:
        """Test processing multiple entries."""

        source_file = tmp_path / "source.txt"
        source_file.write_text("source content", encoding="utf-8")

        dest1 = tmp_path / "dest1.txt"
        dest2 = tmp_path / "dest2.txt"

        entries = [
            Entry(EntryAction.Write, "written content", dest1),
            Entry(EntryAction.Copy, source_file, dest2),
        ]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert dest1.read_text(encoding="utf-8") == "written content"
        assert dest2.read_text(encoding="utf-8") == "source content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest1}' (1 of 2)...DONE! (0, <scrubbed duration>, Wrote)
              Processing '{dest2}' (2 of 2)...DONE! (0, <scrubbed duration>, Copied)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created if they don't exist."""

        dest_path = tmp_path / "nested" / "path" / "output.txt"
        entries = [Entry(EntryAction.Write, "nested content", dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert dest_path.exists()
        assert dest_path.read_text(encoding="utf-8") == "nested content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Wrote)
            DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_empty_entries_list(self) -> None:
        """Test processing an empty entries list."""

        entries: list[Entry] = []

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert content == textwrap.dedent(
            """\
            Heading...DONE! (0, <scrubbed duration>)
            """,
        )

    # ----------------------------------------------------------------------
    def test_link_action_directory(self, tmp_path: Path) -> None:
        """Test that Link action creates a symlink to a directory."""

        source_dir = tmp_path / "source_dir"
        source_dir.mkdir()
        (source_dir / "file.txt").write_text("file content", encoding="utf-8")

        dest_path = tmp_path / "link_dir"
        entries = [Entry(EntryAction.Link, source_dir, dest_path)]

        dm_and_content = iter(GenerateDoneManagerAndContent())
        dm = cast(DoneManager, next(dm_and_content))

        ProcessEntries(dm, entries)

        content = cast(str, next(dm_and_content))

        assert dest_path.exists()
        assert dest_path.is_symlink()
        assert (dest_path / "file.txt").read_text(encoding="utf-8") == "file content"
        assert content == textwrap.dedent(
            f"""\
            Heading...
              Processing '{dest_path}' (1 of 1)...DONE! (0, <scrubbed duration>, Linked)
            DONE! (0, <scrubbed duration>)
            """,
        )
