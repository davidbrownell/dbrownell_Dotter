# noqa: D100
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jinja2 import Environment
from typer.testing import CliRunner

from dbrownell_Dotter.__main__ import app
from dbrownell_Dotter.Lib import Entry, EntryAction


# ----------------------------------------------------------------------
runner = CliRunner()


# ----------------------------------------------------------------------
class TestInstall:
    # ----------------------------------------------------------------------
    def test_no_args_shows_help(self) -> None:
        """Test that running Install with no args shows help/usage."""

        result = runner.invoke(app, [])

        # Exit code 2 is expected for missing required arguments
        assert result.exit_code == 2
        assert "Usage:" in result.output

    # ----------------------------------------------------------------------
    def test_basic_invocation(self, tmp_path: Path) -> None:
        """Test basic invocation with a config file."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        mock_entries: list[Entry] = []

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries") as mock_process,
        ):
            mock_resolve.return_value = mock_entries

            result = runner.invoke(app, [str(config_file)])

            assert result.exit_code == 0
            mock_resolve.assert_called_once()
            mock_process.assert_called_once()

            # Verify ResolveEntries was called with an Environment and the config files
            resolve_args = mock_resolve.call_args
            assert isinstance(resolve_args[0][0], Environment)
            assert resolve_args[0][1] == [config_file]

            # Verify ProcessEntries was called with correct kwargs
            process_kwargs = mock_process.call_args[1]
            assert process_kwargs["force"] is False
            assert process_kwargs["dry_run"] is False

    # ----------------------------------------------------------------------
    def test_multiple_config_files(self, tmp_path: Path) -> None:
        """Test invocation with multiple config files."""

        config1 = tmp_path / "config1.yaml"
        config1.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        config2 = tmp_path / "config2.yaml"
        config2.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries") as mock_process,
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config1), str(config2)])

            assert result.exit_code == 0

            # Verify both config files were passed
            resolve_args = mock_resolve.call_args
            assert resolve_args[0][1] == [config1, config2]

    # ----------------------------------------------------------------------
    def test_force_option(self, tmp_path: Path) -> None:
        """Test that --force option is passed to ProcessEntries."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries") as mock_process,
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config_file), "--force"])

            assert result.exit_code == 0

            process_kwargs = mock_process.call_args[1]
            assert process_kwargs["force"] is True

    # ----------------------------------------------------------------------
    def test_dry_run_option(self, tmp_path: Path) -> None:
        """Test that --dry-run option is passed to ProcessEntries."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries") as mock_process,
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config_file), "--dry-run"])

            assert result.exit_code == 0

            process_kwargs = mock_process.call_args[1]
            assert process_kwargs["dry_run"] is True

    # ----------------------------------------------------------------------
    def test_force_and_dry_run_together(self, tmp_path: Path) -> None:
        """Test that --force and --dry-run can be used together."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries") as mock_process,
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config_file), "--force", "--dry-run"])

            assert result.exit_code == 0

            process_kwargs = mock_process.call_args[1]
            assert process_kwargs["force"] is True
            assert process_kwargs["dry_run"] is True

    # ----------------------------------------------------------------------
    def test_var_option_single(self, tmp_path: Path) -> None:
        """Test that --var option sets Jinja variables."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries"),
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config_file), "--var", "name=value"])

            assert result.exit_code == 0

            # Verify the Environment has the variable set
            resolve_args = mock_resolve.call_args
            env = resolve_args[0][0]
            assert env.globals["name"] == "value"

    # ----------------------------------------------------------------------
    def test_var_option_multiple(self, tmp_path: Path) -> None:
        """Test that multiple --var options set multiple Jinja variables."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries"),
        ):
            mock_resolve.return_value = []

            result = runner.invoke(
                app,
                [str(config_file), "--var", "key1=value1", "--var", "key2=value2"],
            )

            assert result.exit_code == 0

            resolve_args = mock_resolve.call_args
            env = resolve_args[0][0]
            assert env.globals["key1"] == "value1"
            assert env.globals["key2"] == "value2"

    # ----------------------------------------------------------------------
    def test_var_option_with_equals_in_value(self, tmp_path: Path) -> None:
        """Test that --var handles values containing equals signs."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries"),
        ):
            mock_resolve.return_value = []

            result = runner.invoke(
                app,
                [str(config_file), "--var", "equation=a=b+c"],
            )

            assert result.exit_code == 0

            resolve_args = mock_resolve.call_args
            env = resolve_args[0][0]
            assert env.globals["equation"] == "a=b+c"

    # ----------------------------------------------------------------------
    def test_var_option_invalid_format(self, tmp_path: Path) -> None:
        """Test that --var without equals sign raises an error."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries"),
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries"),
        ):
            result = runner.invoke(app, [str(config_file), "--var", "invalid"])

            assert result.exit_code != 0
            assert "must be in the form key=value" in result.output

    # ----------------------------------------------------------------------
    def test_entries_passed_to_process(self, tmp_path: Path) -> None:
        """Test that entries from ResolveEntries are passed to ProcessEntries."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        mock_entries = [
            Entry(EntryAction.Write, "content", tmp_path / "dest.txt"),
        ]

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries") as mock_process,
        ):
            mock_resolve.return_value = mock_entries

            result = runner.invoke(app, [str(config_file)])

            assert result.exit_code == 0

            # Verify the entries were passed to ProcessEntries
            process_args = mock_process.call_args[0]
            assert process_args[1] == mock_entries

    # ----------------------------------------------------------------------
    def test_nonexistent_config_file(self, tmp_path: Path) -> None:
        """Test that nonexistent config file causes an error."""

        nonexistent = tmp_path / "nonexistent.yaml"

        result = runner.invoke(app, [str(nonexistent)])

        assert result.exit_code != 0

    # ----------------------------------------------------------------------
    def test_verbose_option(self, tmp_path: Path) -> None:
        """Test that --verbose option is accepted."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries"),
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config_file), "--verbose"])

            assert result.exit_code == 0

    # ----------------------------------------------------------------------
    def test_debug_option(self, tmp_path: Path) -> None:
        """Test that --debug option is accepted."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries"),
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config_file), "--debug"])

            assert result.exit_code == 0

    # ----------------------------------------------------------------------
    def test_var_option_empty_value(self, tmp_path: Path) -> None:
        """Test that --var with empty value is accepted."""

        config_file = tmp_path / "config.yaml"
        config_file.write_text("variable_definitions: {}\nentries: []", encoding="utf-8")

        with (
            patch("dbrownell_Dotter.__main__.Lib.ResolveEntries") as mock_resolve,
            patch("dbrownell_Dotter.__main__.Lib.ProcessEntries"),
        ):
            mock_resolve.return_value = []

            result = runner.invoke(app, [str(config_file), "--var", "empty="])

            assert result.exit_code == 0

            resolve_args = mock_resolve.call_args
            env = resolve_args[0][0]
            assert env.globals["empty"] == ""
