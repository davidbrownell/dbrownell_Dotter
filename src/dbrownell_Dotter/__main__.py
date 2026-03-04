# noqa: D100
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
@app.command("Install", no_args_is_help=True)
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
        var_dict: dict[str, str] = {}
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
        ):
            entries = Lib.ResolveEntries(env, config_filenames)

        with dm.Nested("Processing entries..."):
            Lib.InstallEntries(dm, entries, force=force, dry_run=dry_run)


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
        var_dict: dict[str, object] = {}
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
        ):
            entries = Lib.ResolveEntries(env, config_filenames)

        with dm.Nested("Processing entries..."):
            Lib.ReverseSyncEntries(dm, entries, var_dict, dry_run=dry_run)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()  # pragma: no cover
