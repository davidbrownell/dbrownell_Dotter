import textwrap

from pathlib import Path

import pytest

from cattrs.errors import ClassValidationError

from dbrownell_Dotter.Configuration import (
    Configuration,
    ConfigurationEntryTypes,
    PostInstallConfigurationEntry,
    SourceConfigurationEntry,
    SubstituteConfigurationEntry,
    Substitution,
)


# ----------------------------------------------------------------------
class TestSourceConfigurationEntry:
    # ----------------------------------------------------------------------
    def test_Construct(self) -> None:
        entry = SourceConfigurationEntry(source=Path("foo/bar.txt"), dest="/dest.txt")

        assert entry.source == Path("foo/bar.txt")
        assert entry.dest == "/dest.txt"
        assert entry.condition is None

    # ----------------------------------------------------------------------
    def test_ConstructWithCondition(self) -> None:
        entry = SourceConfigurationEntry(
            source=Path("foo/bar.txt"),
            dest="/dest.txt",
            condition="{{ os_name == 'Windows' }}",
        )

        assert entry.source == Path("foo/bar.txt")
        assert entry.dest == "/dest.txt"
        assert entry.condition == "{{ os_name == 'Windows' }}"

    # ----------------------------------------------------------------------
    def test_ConstructWithMakeExecutable(self) -> None:
        assert SourceConfigurationEntry(source=Path("foo/bar.txt"), dest="/dest.txt").make_executable is False

        entry = SourceConfigurationEntry(
            source=Path("foo/bar.txt"),
            dest="/dest.txt",
            make_executable=True,
        )

        assert entry.make_executable is True


# ----------------------------------------------------------------------
class TestSubstituteConfigurationEntry:
    # ----------------------------------------------------------------------
    def test_Construct(self) -> None:
        substitutions = [Substitution("old_value", "new_value")]

        entry = SubstituteConfigurationEntry(dest="/dest.txt", substitutions=substitutions)

        assert entry.dest == "/dest.txt"
        assert entry.substitutions == substitutions
        assert entry.condition is None

    # ----------------------------------------------------------------------
    def test_ConstructWithCondition(self) -> None:
        substitutions = [Substitution("old_value", "new_value")]

        entry = SubstituteConfigurationEntry(
            dest="/dest.txt",
            substitutions=substitutions,
            condition="{{ os_name == 'Windows' }}",
        )

        assert entry.dest == "/dest.txt"
        assert entry.substitutions == substitutions
        assert entry.condition == "{{ os_name == 'Windows' }}"

    # ----------------------------------------------------------------------
    def test_ConstructWithMakeExecutable(self) -> None:
        substitutions = [Substitution("old_value", "new_value")]

        assert (
            SubstituteConfigurationEntry(dest="/dest.txt", substitutions=substitutions).make_executable
            is False
        )

        entry = SubstituteConfigurationEntry(
            dest="/dest.txt",
            substitutions=substitutions,
            make_executable=True,
        )

        assert entry.make_executable is True

    # ----------------------------------------------------------------------
    def test_ConstructWithoutSubstitutions(self) -> None:
        with pytest.raises(ValueError, match="'substitutions' must contain at least one item."):
            SubstituteConfigurationEntry(dest="/dest.txt", substitutions=[])


# ----------------------------------------------------------------------
class TestPostInstallConfigurationEntry:
    # ----------------------------------------------------------------------
    def test_Construct(self) -> None:
        entry = PostInstallConfigurationEntry(post_install_instructions="Do this thing.")

        assert entry.post_install_instructions == "Do this thing."
        assert entry.condition is None

    # ----------------------------------------------------------------------
    def test_ConstructWithCondition(self) -> None:
        entry = PostInstallConfigurationEntry(
            post_install_instructions="Do this thing.",
            condition="{{ os_name == 'Windows' }}",
        )

        assert entry.post_install_instructions == "Do this thing."
        assert entry.condition == "{{ os_name == 'Windows' }}"

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("instructions", ["", "   \n  "])
    def test_ConstructWithoutInstructions(self, instructions) -> None:
        with pytest.raises(ValueError, match="'post_install_instructions' must not be empty."):
            PostInstallConfigurationEntry(post_install_instructions=instructions)


# ----------------------------------------------------------------------
class TestConfiguration:
    # ----------------------------------------------------------------------
    def test_Construct(self) -> None:
        variable_definitions = {"FOO_VARIABLE": "foo_value", "BAR_VARIABLE": "bar_value"}
        entries: list[ConfigurationEntryTypes] = [
            SourceConfigurationEntry(source=Path("one.txt"), dest="/one.txt"),
            SourceConfigurationEntry(source=Path("two.txt"), dest="/two.txt"),
        ]

        config = Configuration(variable_definitions, entries)

        assert config.variable_definitions == variable_definitions
        assert config.entries == entries

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("ext", [".json", ".json5"])
    def test_FromFileJson(self, ext, fs) -> None:
        fs.create_file(
            f"config.{ext}",
            contents=textwrap.dedent(
                """\
                {
                  // This works because we are using json5
                  "variable_definitions": {
                    "FOO_VARIABLE": "foo_value",
                    "BAR_VARIABLE": "bar_value"
                  },
                  "entries": [
                    {
                      "source": "one.txt",
                      "dest": "/one.txt",
                    },
                    {
                      "source": "two.txt",
                      "dest": "/two.txt",
                    }
                  ]
                }
                """,
            ),
        )

        config = Configuration.FromFile(Path(f"config.{ext}"))

        assert config.variable_definitions == {"FOO_VARIABLE": "foo_value", "BAR_VARIABLE": "bar_value"}

        # We can't compare the entries directly, because the use of fs monkeypatches the Path class. Compare by string instead.
        source_entries = [e for e in config.entries if isinstance(e, SourceConfigurationEntry)]

        assert len(source_entries) == len(config.entries)
        assert [(str(e.source), e.dest) for e in source_entries] == [
            (
                "one.txt",
                "/one.txt",
            ),
            (
                "two.txt",
                "/two.txt",
            ),
        ]

    # ----------------------------------------------------------------------
    @pytest.mark.parametrize("ext", [".yaml", ".yml"])
    def test_FromFileYaml(self, ext, fs) -> None:
        fs.create_file(
            f"config.{ext}",
            contents=textwrap.dedent(
                """\
                # This works because we are using json5
                variable_definitions:
                  FOO_VARIABLE: "foo_value"
                  BAR_VARIABLE: "bar_value"
                entries:
                  - source: "one.txt"
                    dest: "/one.txt"
                  - source: "two.txt"
                    dest: "/two.txt"
                """,
            ),
        )

        config = Configuration.FromFile(Path(f"config.{ext}"))

        assert config.variable_definitions == {"FOO_VARIABLE": "foo_value", "BAR_VARIABLE": "bar_value"}

        # We can't compare the entries directly, because the use of fs monkeypatches the Path class. Compare by string instead.
        source_entries = [e for e in config.entries if isinstance(e, SourceConfigurationEntry)]

        assert len(source_entries) == len(config.entries)
        assert [(str(e.source), e.dest) for e in source_entries] == [
            (
                "one.txt",
                "/one.txt",
            ),
            (
                "two.txt",
                "/two.txt",
            ),
        ]

    # ----------------------------------------------------------------------
    def test_FromFileWithCondition(self, fs) -> None:
        fs.create_file(
            "config.yaml",
            contents=textwrap.dedent(
                """\
                variable_definitions: {}
                entries:
                  - source: "windows.txt"
                    dest: "/dest.txt"
                    condition: "{{ os_name == 'Windows' }}"
                  - source: "linux.txt"
                    dest: "/dest.txt"
                    condition: "{{ os_name == 'Linux' }}"
                  - source: "always.txt"
                    dest: "/always.txt"
                """,
            ),
        )

        config = Configuration.FromFile(Path("config.yaml"))

        assert len(config.entries) == 3
        assert config.entries[0].condition == "{{ os_name == 'Windows' }}"
        assert config.entries[1].condition == "{{ os_name == 'Linux' }}"
        assert config.entries[2].condition is None

    # ----------------------------------------------------------------------
    def test_FromFileEntryTypes(self, fs) -> None:
        fs.create_file(
            "config.yaml",
            contents=textwrap.dedent(
                """\
                variable_definitions: {}
                entries:
                  - source: "one.txt"
                    dest: "/one.txt"
                  - dest: "/two.txt"
                    substitutions:
                      - pattern: "old_value"
                        replacement: "new_value"
                  - post_install_instructions: "Do this thing."
                """,
            ),
        )

        config = Configuration.FromFile(Path("config.yaml"))

        assert len(config.entries) == 3

        source_entry = config.entries[0]
        assert isinstance(source_entry, SourceConfigurationEntry)
        assert str(source_entry.source) == "one.txt"
        assert source_entry.dest == "/one.txt"

        substitute_entry = config.entries[1]
        assert isinstance(substitute_entry, SubstituteConfigurationEntry)
        assert substitute_entry.dest == "/two.txt"
        assert substitute_entry.substitutions == [Substitution("old_value", "new_value")]

        post_install_entry = config.entries[2]
        assert isinstance(post_install_entry, PostInstallConfigurationEntry)
        assert post_install_entry.post_install_instructions == "Do this thing."

    # ----------------------------------------------------------------------
    def test_FromFileWithMakeExecutable(self, fs) -> None:
        fs.create_file(
            "config.yaml",
            contents=textwrap.dedent(
                """\
                variable_definitions: {}
                entries:
                  - source: "one.sh"
                    dest: "/one.sh"
                    make_executable: true
                  - dest: "/two.sh"
                    make_executable: true
                    substitutions:
                      - pattern: "old_value"
                        replacement: "new_value"
                  - source: "three.txt"
                    dest: "/three.txt"
                """,
            ),
        )

        config = Configuration.FromFile(Path("config.yaml"))

        assert [e.make_executable for e in config.entries] == [  # ty: ignore[unresolved-attribute]
            True,
            True,
            False,
        ]

    # ----------------------------------------------------------------------
    def test_FromFileInvalidEntry(self, fs) -> None:
        fs.create_file(
            "config.yaml",
            contents=textwrap.dedent(
                """\
                variable_definitions: {}
                entries:
                  - dest: "/one.txt"
                """,
            ),
        )

        with pytest.raises(ClassValidationError):
            Configuration.FromFile(Path("config.yaml"))

    # ----------------------------------------------------------------------
    def test_FromFileWithoutSubstitutions(self, fs) -> None:
        fs.create_file(
            "config.yaml",
            contents=textwrap.dedent(
                """\
                variable_definitions: {}
                entries:
                  - dest: "/one.txt"
                    substitutions: []
                """,
            ),
        )

        with pytest.raises(ClassValidationError):
            Configuration.FromFile(Path("config.yaml"))

    # ----------------------------------------------------------------------
    def test_FromFileDoesNotExist(self) -> None:
        filename = Path("foo.txt")

        with pytest.raises(ValueError, match=f"'{filename}' does not exist."):
            Configuration.FromFile(filename)

    # ----------------------------------------------------------------------
    def test_FromFileUnsupportedExtension(self, fs) -> None:
        filename = Path("foo.txt")

        fs.create_file(filename)

        with pytest.raises(ValueError, match=f"'{filename}' is not a supported file type."):
            Configuration.FromFile(filename)
