import shlex
import subprocess
import typer
import json
import susscanner as ss

from pathlib import Path
from typing import Optional, List


app = typer.Typer(add_completion=False)


def _version_callback(value: bool) -> None:
    """
    Returns SusScanner version.

    Args:
        value (bool): Display the version Y/N.

    Raises:
        typer.Exit: exit the program
    """
    if value:
        typer.echo(f"{ss.__app_name__} v{ss.__version__}")
        raise typer.Exit()


def _rules_metadata_callback(rules_metadata: Path) -> Path:
    """
    Checks if the provided rules metadata is valid

    Args:
        rules_metadata (Path): The path of the config file

    Raises:
        typer.Exit: exit the program
    """
    if rules_metadata is None:
        return rules_metadata

    # check if the rules metadata exists
    if not rules_metadata.is_file():
        raise typer.BadParameter(
            f"Specified rules metadata file '{rules_metadata}' is not a file"
        )

    # check if the json inside the rules metadata is valid
    try:
        json.loads(rules_metadata.read_text())
    except ValueError:
        raise typer.BadParameter(
            f"Specified rules metadata file '{rules_metadata}' is not valid json"
        )
    return rules_metadata


def main(
    cfn_template: List[Path],
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
    rules_metadata: Path = typer.Option(
        None,
        "--rules",
        "-r",
        help="Location for a custom rules metadata file.",
        callback=_rules_metadata_callback,
        show_default=False,
    ),
) -> int:
    """ """  # additional docstring to surpress the comments in the cli output
    """
    This function constitutes the main flow of the program. First, it checks if
    a valid config file exists. It then checks whether the specified Cloudformation
    template can be found. Given the input checks passed, "cfn-guard validate" is run
    to execute our rules on the provided template. The output of Cloudformation Guard
    is structured and enriched to result in the Sustainability Scanner report.

    Args:
        cfn_template (str, optional): the CloudFormation template.
        version (Optional[bool], optional): the version of the program.

    Raises:
        typer.Exit: (1) closed because the configuration file was not found
        typer.Exit: (2) closed because the configuration is not valid JSON
        typer.Exit: (3) closed because the CloudFormation file was not found

    Returns:
        int: returns the exit status, 0 for successful execution
    """
    app_init_error = ss.init_app(cfn_template)
    if app_init_error == ss.FILE_ERROR:
        typer.secho(
            f'Config file not found "{ss.ERRORS[app_init_error]}"',
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    if app_init_error == ss.JSON_ERROR:
        typer.secho(
            f'Config file not valid "{ss.ERRORS[app_init_error]}"',
            fg=typer.colors.RED,
        )
        raise typer.Exit(2)
    if app_init_error == ss.TEMPLATE_ERROR:
        typer.secho(
            f'CloudFormation template not found "{ss.ERRORS[app_init_error]}"',
            fg=typer.colors.RED,
        )
        raise typer.Exit(3)

    rules = Path(ss.DIR_PATH).joinpath(Path("rules")).__str__()

    for template in cfn_template:
        command = rf"cfn-guard validate -o json --rules '{rules}' --data '{template}'"
        args = shlex.split(command)

        cfn_guard_output = subprocess.Popen(
            args,
            shell=False,
            universal_newlines=True,
            stdout=subprocess.PIPE,
        ).stdout.read()

        ss.Scan.filter_results(
            cfn_guard_output=cfn_guard_output,
            template_name=str(template),
            rules_metadata=rules_metadata,
        )

    return 0
