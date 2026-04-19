import textwrap

from pathlib import Path

import pytest

from dbrownell_Dotter.Configuration import Configuration, ConfigurationEntry


# ----------------------------------------------------------------------
class TestConfigurationEntry:
    # ----------------------------------------------------------------------
    def test_Construct(self) -> None:
        entry = ConfigurationEntry(Path("foo/bar.txt"), "/dest.txt")

        assert entry.source == Path("foo/bar.txt")
        assert entry.dest == "/dest.txt"
        assert entry.condition is None

    # ----------------------------------------------------------------------
    def test_ConstructWithCondition(self) -> None:
        entry = ConfigurationEntry(
            Path("foo/bar.txt"),
            "/dest.txt",
            condition="{{ os_name == 'Windows' }}",
        )

        assert entry.source == Path("foo/bar.txt")
        assert entry.dest == "/dest.txt"
        assert entry.condition == "{{ os_name == 'Windows' }}"


# ----------------------------------------------------------------------
class TestConfiguration:
    # ----------------------------------------------------------------------
    def test_Construct(self) -> None:
        variable_definitions = {"FOO_VARIABLE": "foo_value", "BAR_VARIABLE": "bar_value"}
        entries = [
            ConfigurationEntry(Path("one.txt"), "/one.txt"),
            ConfigurationEntry(Path("two.txt"), "/two.txt"),
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
        assert [(str(e.source), e.dest) for e in config.entries] == [
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
        assert [(str(e.source), e.dest) for e in config.entries] == [
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
