# noqa: D100
import textwrap

from pathlib import Path  # noqa: TC003
from typing import Annotated

import typer

from dbrownell_Common.InflectEx import inflect
from dbrownell_Common.Streams.DoneManager import DoneManager, Flags as DoneManagerFlags
from jinja2 import Environment
from typer.core import TyperGroup

from dbrownell_Dotter import Lib


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):  # noqa: D101
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs) -> list[str]:  # noqa: ARG002, D102
        return list(self.commands.keys())  # pragma: no cover


# ----------------------------------------------------------------------
app = typer.Typer(
    cls=NaturalOrderGrouper,
    help=__doc__,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
def _InstallHelp() -> str:
    variables: list[str] = [
        "- {}: {}{}".format(
            var.name,
            var.description,
            r" \[value: {}]".format(var.value) if not callable(var.value) else "",
        )
        for var in Lib.DEFAULT_DYNAMIC_VARIABLES
    ]

    return textwrap.dedent(
        """\
        Installs dotfiles on the current machine.

        Configuration Files
        ===================
          Configuration files are YAML (.yaml, .yml) or JSON5 (.json5, .json) files that specify how
          dotfiles should be installed.

          Example.yaml
          ------------
          variable_definitions:
            my_variable: "This must be provided on the command line via `--var my_variable=value`."

          entries:
            # Copy a file from the source to the destination.
            - source: "relative/path/to/source/file1.txt"
              dest: "~/destination/file1.txt"

            # Populate a template and write it to the destination.
            - source: "relative/path/to/source/file2.txt.jinja"
              dest: "~/destination/file2.txt"

            # Update content in an existing file by applying regex substitutions.
            - dest: "{{{{ tools_dir }}}}/somefile.txt"
              substitutions:
                - pattern: "pattern to match"
                  replacement: "replacement string that may include {{{{ my_variable }}}}"

            # Apply the Entry only if a certain condition is met at runtime.
            - source: "relative/path/to/source/file3.txt"
              dest: "~/destination/file3.txt"
              condition: "my_variable == 'some value'"  # This is a python expression

            # Use environment variables
            - source: "relative/path/to/source/file4.txt"
              dest: "~/destination/file4.txt"
              condition: "${{HOME}} == '/home/myuser'"

            # Set the execute flag on the destination (only valid when the destination is a file).
            - source: "relative/path/to/source/script.sh"
              dest: "~/destination/script.sh"
              make_executable: true

        Variables
        =========
          Variables are provided via the command line using `--var key=value`. They can then be used
          in source paths, destination paths, and substitution replacements.

          Additionally, the following dynamic variables are always available:

            {variables}
        """,
    ).format(
        variables="\n    ".join(variables),
    )


# ----------------------------------------------------------------------
@app.command(
    "Install",
    help=_InstallHelp(),
    no_args_is_help=True,
)
def Install(
    config_filenames: Annotated[
        list[Path],
        typer.Argument(
            dir_okay=False, exists=True, resolve_path=True, help="Configuration files to process."
        ),
    ],
    variables: Annotated[
        list[str] | None,
        typer.Option(
            "--var",
            help="Jinja template variables in the form key=value. Can be specified multiple times.",
        ),
    ] = None,
    force: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--force", help="Overwrite existing files."),
    ] = False,
    force_symbolic_links: Annotated[  # noqa: FBT002
        bool,
        typer.Option(
            "--force-symbolic-links",
            help="Force symbolic links even when source and destination are on different drives.",
        ),
    ] = False,
    dry_run: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--dry-run", help="Show what would be done without making changes."),
    ] = False,
    verbose: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--verbose", help="Write verbose information to the terminal."),
    ] = False,
    debug: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--debug", help="Write debug information to the terminal."),
    ] = False,
) -> None:
    """Installs dotfiles on the current machine."""

    with DoneManager.CreateCommandLine(
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        # Parse variables into a dictionary
        var_dict: dict = {}
        for var in variables or []:
            if "=" not in var:
                msg = f"Variable '{var}' must be in the form key=value."
                raise typer.BadParameter(msg)
            key, value = var.split("=", 1)
            var_dict[key] = value

        # Create the Jinja environment
        env = Environment(autoescape=False)  # noqa: S701 (we want to preserve the original content, regardless of what it is)
        env.globals.update(var_dict)

        entries: list[Lib.Entry] = []

        with dm.Nested(
            "Resolving entries...",
            lambda: "{} found".format(inflect.no("entry", len(entries))),
            suffix="\n",
        ):
            entries = Lib.ResolveEntries(
                env,
                config_filenames,
                force_symbolic_links=force_symbolic_links,
            )

        with dm.Nested("Processing {}...".format(inflect.no("entry", len(entries)))) as processing_dm:
            Lib.InstallEntries(processing_dm, entries, force=force, dry_run=dry_run)


# ----------------------------------------------------------------------
@app.command("ReverseSync", no_args_is_help=True)
def ReverseSync(
    config_filenames: Annotated[
        list[Path],
        typer.Argument(
            dir_okay=False, exists=True, resolve_path=True, help="Configuration files to process."
        ),
    ],
    variables: Annotated[
        list[str] | None,
        typer.Option(
            "--var",
            help="Jinja template variables in the form key=value. Can be specified multiple times.",
        ),
    ] = None,
    force_symbolic_links: Annotated[  # noqa: FBT002
        bool,
        typer.Option(
            "--force-symbolic-links",
            help="Force symbolic links even when source and destination are on different drives.",
        ),
    ] = False,
    dry_run: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--dry-run", help="Show what would be done without making changes."),
    ] = False,
    verbose: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--verbose", help="Write verbose information to the terminal."),
    ] = False,
    debug: Annotated[  # noqa: FBT002
        bool,
        typer.Option("--debug", help="Write debug information to the terminal."),
    ] = False,
) -> None:
    """Sync changes from installed destinations back to source files."""

    with DoneManager.CreateCommandLine(
        flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        # Parse variables into a dictionary
        var_dict: dict = {}

        for var in variables or []:
            if "=" not in var:
                msg = f"Variable '{var}' must be in the form key=value."
                raise typer.BadParameter(msg)
            key, value = var.split("=", 1)
            var_dict[key] = value

        # Create the Jinja environment
        env = Environment(autoescape=False)  # noqa: S701 (we want to preserve the original content, regardless of what it is)
        env.globals.update(var_dict)

        entries: list[Lib.Entry] = []

        with dm.Nested(
            "Resolving entries...",
            lambda: "{} found".format(inflect.no("entry", len(entries))),
            suffix="\n",
        ):
            entries = Lib.ResolveEntries(
                env,
                config_filenames,
                force_symbolic_links=force_symbolic_links,
            )

        with dm.Nested("Processing {}...".format(inflect.no("entry", len(entries)))) as reverse_sync_dm:
            Lib.ReverseSyncEntries(reverse_sync_dm, entries, var_dict, dry_run=dry_run)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()  # pragma: no cover
