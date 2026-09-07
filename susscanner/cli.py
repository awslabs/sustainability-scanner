import os
import subprocess
import shutil
from enum import Enum

import typer
import json
import susscanner as ss

from pathlib import Path
from typing import Optional, List, Annotated, Sequence

app = typer.Typer(add_completion=False)


class TemplateType(str, Enum):
    cloudformation = ("cf",)
    cdk = "cdk"


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


def as_cli_path(path: str) -> str:
    """
    Makes a filesystem path safe to pass as an option *value* to another CLI.

    A path is data, but a path that begins with "-" is indistinguishable from a
    flag to most argument parsers. Prefixing such a path with "./" keeps it
    pointing at the same file while guaranteeing it can never be mistaken for
    an option.

    Args:
        path (str): The path to normalise.

    Returns:
        str: The path, guaranteed not to start with "-".
    """
    if path.startswith("-"):
        return os.path.join(os.curdir, path)
    return path


def run_command(args: Sequence[str]) -> subprocess.CompletedProcess:
    """
    Runs an external command.

    The command MUST be supplied as an already-split argument list, never as a
    single string. Passing a list means the arguments reach the child process
    exactly as given: no quoting is applied and none is required, so a filename
    containing spaces, quotes, or anything that looks like a flag cannot inject
    extra arguments into the child's command line.

    Args:
        args (Sequence[str]): Program name followed by its arguments.

    Raises:
        typer.Exit: (5) the program is not installed / not on PATH.

    Returns:
        subprocess.CompletedProcess: The completed process, with stdout and
        stderr captured as text.
    """
    args = [str(a) for a in args]

    # Resolve the full path of the executable to ensure execution on Windows.
    # shutil.which returns None when the program is missing; previously that
    # None was handed straight to Popen and surfaced as an opaque TypeError.
    executable = shutil.which(args[0])
    if executable is None:
        typer.secho(
            f"Required program '{args[0]}' was not found on PATH. "
            "See the README for installation instructions.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(ss.SCANNER_ERROR)

    return subprocess.run(
        [executable, *args[1:]],
        shell=False,
        universal_newlines=True,
        capture_output=True,
        check=False,
    )


def require_trustworthy_output(
    proc: subprocess.CompletedProcess, program: str
) -> str:
    """
    Returns the command's stdout, but only if we can trust that the command
    actually ran and produced a verdict.

    This exists to make the scanner fail *closed*. cfn-guard exits non-zero
    both when it finds violations (a real result we must parse) and when it
    fails outright, e.g. it could not read the template. Previously any failure
    yielded empty stdout, which the parser happily read as "no failed rules",
    turning a broken scan into a clean report. We therefore treat a non-zero
    exit with no usable output as an error rather than a pass.

    Args:
        proc (subprocess.CompletedProcess): The finished command.
        program (str): Program name, for the error message.

    Raises:
        typer.Exit: (5) the command did not produce a trustworthy verdict.

    Returns:
        str: The command's stdout.
    """
    stdout = proc.stdout or ""

    # Exit 0 means the program ran to completion; empty output is legitimate.
    if proc.returncode == 0:
        return stdout

    # Non-zero with structured output is cfn-guard reporting violations.
    if "{" in stdout:
        return stdout

    typer.secho(
        f"'{program}' failed (exit status {proc.returncode}) and produced no "
        "usable output, so no verdict could be reached. Refusing to report a "
        "result. Details below.",
        fg=typer.colors.RED,
        err=True,
    )
    if proc.stderr:
        typer.secho(proc.stderr.rstrip(), fg=typer.colors.RED, err=True)
    raise typer.Exit(ss.SCANNER_ERROR)


def preprocess_cdk(stack_name: str) -> str:
    """
    Preprocesses CDK file.

    Args:
        stack_name (str): CDK stack name.

    Raises:
        typer.Exit: exit the program
    """

    template_name = "susscanner_template.yaml"
    # stack_name is passed as its own argv element. It is never concatenated
    # into a command string, so whitespace in a stack name cannot inject extra
    # arguments (such as cdk's own --app, which cdk would then execute).
    proc = run_command(["cdk", "synth", stack_name])
    output = require_trustworthy_output(proc, "cdk")
    with open(template_name, "w") as f:
        f.write(output)
    return template_name


def main(
    cfn_template: Annotated[
        List[Path],
        typer.Argument(
            help="List of template names (for CloudFormation format) or stack name (for CDK format)"
        ),
    ],
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
    template_format: Optional[TemplateType] = typer.Option(
        TemplateType.cloudformation.value,
        "--format",
        "-f",
        help="Template format",
        show_default=True,
        is_eager=False,
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
        cfn_template (str, optional): the CloudFormation template or stack name (for CDK format).
        version (Optional[bool], optional): the version of the program.

    Raises:
        typer.Exit: (1) closed because the CloudFormation template was not
            found, or is not a regular file (e.g. a directory was passed)
        typer.Exit: (2) closed because the rules metadata is not valid JSON
        typer.Exit: (5) closed because cfn-guard/cdk is not installed, or ran
            but produced no usable output, so no verdict could be reached

    Returns:
        int: returns the exit status, 0 for successful execution.

    Note:
        A return of 0 means "the scan completed", NOT "the template passed".
        Findings are reported in the JSON on stdout via sustainability_score
        and failed_rules; callers that need a pass/fail gate must inspect
        those fields rather than the process exit status.
    """
    app_init_error = ss.init_app(cfn_template)
    if (
        app_init_error == ss.FILE_NOT_FOUND
        and template_format == TemplateType.cloudformation.value
    ):
        # Report the offending paths. This previously printed the *config file*
        # error string ("config file error") for a missing template, which was
        # misleading, and named no path at all.
        missing = [str(p) for p in cfn_template if not p.is_file()]
        typer.secho(
            "CloudFormation template not found (or is not a regular file): "
            + ", ".join(repr(m) for m in missing),
            fg=typer.colors.RED,
            err=True,
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

    for t in cfn_template:
        if template_format == TemplateType.cdk:
            template = preprocess_cdk(str(t))
        else:
            template = str(t)
        # Build the argument list directly. Do NOT construct a command string
        # and re-split it: quoting a path into a string and then splitting it
        # again lets a filename containing a quote character close the quote and
        # append extra arguments (e.g. a second --rules pointing at an empty
        # directory, which would silently suppress all findings).
        proc = run_command(
            [
                "cfn-guard",
                "validate",
                "-o",
                "json",
                "--rules",
                as_cli_path(rules),
                "--data",
                as_cli_path(template),
            ]
        )
        cfn_guard_output = require_trustworthy_output(proc, "cfn-guard")

        ss.Scan.filter_results(
            cfn_guard_output=cfn_guard_output,
            template_name=str(template),
            rules_metadata=rules_metadata,
        )

    return 0
