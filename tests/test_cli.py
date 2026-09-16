"""CLI-layer tests, with a focus on how filenames reach the cfn-guard process.

Regression coverage for a crafted-filename scan bypass.

Two independent defects allowed a violating template to be reported as clean by
naming the committed file a particular way:

  1. The cfn-guard command was assembled as a single string with hand-written
     single quotes and then re-split with shlex.split. A filename containing a
     quote character closed the quote early and appended extra arguments to
     cfn-guard's command line -- for example a second --rules pointing at an
     empty directory, which suppresses every finding.

  2. The result parser matched the file name in cfn-guard's output with
     [\\d\\S]+, which cannot match whitespace. A template whose name contained a
     space skipped the entire "failed rules" block and scored 0.

Neither requires a shell: susscanner runs cfn-guard with shell=False and an argv
list, so shell metacharacters were never the issue. The tests below therefore
assert on the exact argv handed to the child process, which is where the
vulnerability actually lived.

cfn-guard is not installed in most environments, so subprocess.run is mocked and
the assertions are made against the recorded argv.
"""

import contextlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import typer
from typer.testing import CliRunner

import susscanner as ss
from susscanner import cli

RULES_METADATA = (
    Path(__file__).parent.parent.joinpath("susscanner").joinpath("rules_metadata.json")
)

VIOLATING_TEMPLATE = """AWSTemplateFormatVersion: '2010-09-09'
Resources:
  MyLogGroup:
    Type: AWS::Logs::LogGroup
"""

# A real rule name from rules_metadata.json, severity HIGH (score 3).
RULE = "ensure_all_loggroups_have_retention"


def cfn_guard_fail_output(file_name: str) -> str:
    """Builds a cfn-guard --output json FAIL payload for the given file name.

    Mirrors the real format, confirmed against the captured fixtures in
    tests/test-data/: a "}<file name> Status = FAIL" line, a FAILED rules list,
    a "---" delimiter, then the JSON body.
    """
    body = {
        "name": "cloudwatch.guard",
        "not_compliant": [
            {
                "Rule": {
                    "name": RULE,
                    "checks": [
                        {
                            "Clause": {
                                "Unary": {
                                    "messages": {
                                        "error_message": (
                                            "Value traversed to "
                                            "[Path=/Resources/MyLogGroup/Properties[L:4,C:5]"
                                        )
                                    },
                                    "check": {
                                        "Unresolved": {
                                            "value": {
                                                "traversed_to": {
                                                    "path": "/Resources/MyLogGroup"
                                                }
                                            }
                                        }
                                    },
                                }
                            }
                        }
                    ],
                }
            }
        ],
    }
    return (
        "{}"
        + file_name
        + " Status = FAIL\nFAILED rules\ncloudwatch.guard/"
        + RULE
        + "\n---\n"
        + json.dumps(body)
    ).replace("{}", "}", 1)


def build_app() -> typer.Typer:
    """Wraps cli.main the same way __main__.main does via typer.run."""
    app = typer.Typer()
    app.command()(cli.main)
    return app


@contextlib.contextmanager
def workspace():
    """A temp cwd containing an empty 'emptyrules' directory an attacker could
    commit as part of the payload."""
    prev = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        Path("emptyrules").mkdir()
        Path("clean.yaml").write_text("Resources: {}\n")
        try:
            yield Path(tmp)
        finally:
            os.chdir(prev)


class RecordingGuard:
    """Stands in for subprocess.run, recording argv and returning a FAIL report
    for whatever --data it was actually given."""

    def __init__(self):
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append(list(args))
        data = None
        for i, a in enumerate(args):
            if a == "--data" and i + 1 < len(args):
                data = args[i + 1]
        # Report against the file cfn-guard was really pointed at. If that file
        # does not exist, behave like cfn-guard does: error, no usable output.
        if data is None or not os.path.isfile(data):
            return subprocess.CompletedProcess(
                args, returncode=2, stdout="", stderr=f"cannot read data: {data!r}"
            )
        return subprocess.CompletedProcess(
            args,
            returncode=5,  # cfn-guard uses a non-zero status for "rules failed"
            stdout=cfn_guard_fail_output(os.path.basename(data)),
            stderr="",
        )

    @property
    def last_argv(self):
        return self.calls[-1]


class CliTestBase(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.app = build_app()
        self.guard = RecordingGuard()
        patch_run = mock.patch.object(cli.subprocess, "run", self.guard)
        patch_which = mock.patch.object(
            cli.shutil, "which", side_effect=lambda p: f"/usr/local/bin/{p}"
        )

        # Guard against reintroducing the vulnerable pattern. The original code
        # built a command *string* and ran it through shlex.split + Popen. These
        # tests observe argv via subprocess.run, so a reversion to Popen would
        # silently escape observation; make it an explicit, legible failure.
        def _no_popen(*args, **kwargs):
            raise AssertionError(
                "subprocess.Popen was called. Commands must be run through "
                "run_command() with an argv list -- never by building a command "
                "string and re-splitting it, which is what allowed a filename "
                "to inject extra cfn-guard arguments."
            )

        patch_popen = mock.patch.object(cli.subprocess, "Popen", _no_popen)

        for patcher in (patch_run, patch_which, patch_popen):
            patcher.start()
            self.addCleanup(patcher.stop)

    def scan(self, *args):
        return self.runner.invoke(self.app, list(args))

    def report(self, result):
        return json.loads(result.stdout)


class TestArgvIsNotInjectable(CliTestBase):
    """The crafted filename must arrive as exactly ONE argv element."""

    def assert_single_pair(self, argv, expected_data):
        self.assertEqual(
            1, argv.count("--rules"), f"extra --rules injected: {argv!r}"
        )
        self.assertEqual(1, argv.count("--data"), f"extra --data injected: {argv!r}")
        self.assertEqual(expected_data, argv[argv.index("--data") + 1])

    def test_quote_injecting_extra_rules_flag(self):
        # The original payload: closes the quote, then adds --rules <empty dir>.
        name = "x.yaml' --rules 'emptyrules"
        with workspace():
            Path(name).write_text(VIOLATING_TEMPLATE)
            result = self.scan(name)
        self.assertEqual(0, result.exit_code, result.output)
        self.assert_single_pair(self.guard.last_argv, name)
        # And the violation is still reported.
        self.assertEqual(3, self.report(result)["sustainability_score"])

    def test_quote_injecting_data_redirect(self):
        name = "x.yaml' --data 'clean.yaml"
        with workspace():
            Path(name).write_text(VIOLATING_TEMPLATE)
            result = self.scan(name)
        self.assertEqual(0, result.exit_code, result.output)
        self.assert_single_pair(self.guard.last_argv, name)
        self.assertEqual(3, self.report(result)["sustainability_score"])

    def test_unbalanced_quote_does_not_crash(self):
        # Previously raised ValueError("No closing quotation") from shlex.split.
        name = "x'.yaml"
        with workspace():
            Path(name).write_text(VIOLATING_TEMPLATE)
            result = self.scan(name)
        self.assertIsNone(result.exception, repr(result.exception))
        self.assertEqual(0, result.exit_code, result.output)
        self.assert_single_pair(self.guard.last_argv, name)

    def test_double_quote_and_backslash(self):
        name = 'weird"name\\.yaml'
        with workspace():
            Path(name).write_text(VIOLATING_TEMPLATE)
            result = self.scan(name)
        self.assertEqual(0, result.exit_code, result.output)
        self.assert_single_pair(self.guard.last_argv, name)

    def test_shell_metacharacters_are_inert(self):
        # No shell is involved; these must be passed through as literal bytes.
        name = "a;b&&c|d`e$(f).yaml"
        with workspace():
            Path(name).write_text(VIOLATING_TEMPLATE)
            result = self.scan(name)
        self.assertEqual(0, result.exit_code, result.output)
        self.assert_single_pair(self.guard.last_argv, name)

    def test_glob_metacharacters_are_not_expanded(self):
        name = "*.yaml"
        with workspace():
            Path(name).write_text(VIOLATING_TEMPLATE)
            result = self.scan(name)
        self.assertEqual(0, result.exit_code, result.output)
        self.assert_single_pair(self.guard.last_argv, name)

    def test_leading_dash_is_neutralised(self):
        # A path starting with "-" would be read as a flag by the child parser,
        # so it is rewritten to "./-o" -- same file, unambiguously a path.
        with workspace():
            Path("-o").write_text(VIOLATING_TEMPLATE)
            result = self.scan("--", "-o")
        self.assertEqual(0, result.exit_code, result.output)
        argv = self.guard.last_argv
        self.assertEqual(os.path.join(os.curdir, "-o"), argv[argv.index("--data") + 1])

    def test_spaces_and_unicode(self):
        for name in ["my template.yaml", "тест-模板.yaml", "a b c.yaml"]:
            with self.subTest(name=name), workspace():
                Path(name).write_text(VIOLATING_TEMPLATE)
                result = self.scan(name)
                self.assertEqual(0, result.exit_code, result.output)
                self.assert_single_pair(self.guard.last_argv, name)


class TestFindingsSurviveCraftedNames(CliTestBase):
    """The end-to-end property that actually matters: a violating template must
    never report as clean because of how it is named."""

    NAMES = [
        "ordinary.yaml",
        "my template.yaml",  # defeated the old result-parsing regex
        "two  spaces.yaml",
        "тест 模板.yaml",
        "x.yaml' --rules 'emptyrules",  # defeated the old quoting
        "x'.yaml",
        "trailing space .yaml",
    ]

    def test_violation_is_always_reported(self):
        for name in self.NAMES:
            with self.subTest(name=name), workspace():
                Path(name).write_text(VIOLATING_TEMPLATE)
                result = self.scan(name)
                self.assertEqual(0, result.exit_code, result.output)
                report = self.report(result)
                self.assertEqual(
                    3,
                    report["sustainability_score"],
                    f"{name!r} reported clean -- scan bypass",
                )
                self.assertEqual(1, len(report["failed_rules"]))
                self.assertEqual(RULE, report["failed_rules"][0]["rule_name"])
                self.assertEqual(name, report["file"])


class TestFailsClosed(CliTestBase):
    """A scan that did not produce a verdict must not look like a clean scan."""

    def test_scanner_error_is_not_a_pass(self):
        def broken(args, **kwargs):
            return subprocess.CompletedProcess(
                args, returncode=2, stdout="", stderr="boom: could not read rules"
            )

        with mock.patch.object(cli.subprocess, "run", broken), workspace():
            Path("t.yaml").write_text(VIOLATING_TEMPLATE)
            result = self.scan("t.yaml")
        self.assertEqual(ss.SCANNER_ERROR, result.exit_code)
        self.assertNotIn("sustainability_score", result.stdout)

    def test_missing_binary_reports_clearly(self):
        with mock.patch.object(cli.shutil, "which", return_value=None), workspace():
            Path("t.yaml").write_text(VIOLATING_TEMPLATE)
            result = self.scan("t.yaml")
        self.assertEqual(ss.SCANNER_ERROR, result.exit_code)
        self.assertNotIsInstance(result.exception, TypeError)
        self.assertIn("not found on PATH", result.output)

    def test_zero_exit_with_empty_output_is_allowed(self):
        # A compliant template legitimately produces no FAIL block.
        def compliant(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

        with mock.patch.object(cli.subprocess, "run", compliant), workspace():
            Path("t.yaml").write_text(VIOLATING_TEMPLATE)
            result = self.scan("t.yaml")
        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(0, self.report(result)["sustainability_score"])


class TestInputValidation(CliTestBase):
    def test_directory_argument_is_rejected(self):
        with workspace():
            result = self.scan("emptyrules")
        self.assertEqual(1, result.exit_code)
        self.assertEqual([], self.guard.calls, "cfn-guard should not have run")

    def test_missing_file_is_rejected_and_named(self):
        with workspace():
            result = self.scan("nope.yaml")
        self.assertEqual(1, result.exit_code)
        self.assertIn("nope.yaml", result.output)
        self.assertNotIn("config file error", result.output)

    def test_multiple_templates_each_scanned_once(self):
        with workspace():
            for n in ["a.yaml", "b b.yaml"]:
                Path(n).write_text(VIOLATING_TEMPLATE)
            result = self.scan("a.yaml", "b b.yaml")
        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(2, len(self.guard.calls))


class TestAsCliPath(unittest.TestCase):
    def test_leading_dash_prefixed(self):
        self.assertEqual(os.path.join(os.curdir, "-o"), cli.as_cli_path("-o"))
        self.assertEqual(
            os.path.join(os.curdir, "--rules"), cli.as_cli_path("--rules")
        )

    def test_ordinary_paths_untouched(self):
        for p in ["t.yaml", "./t.yaml", "/abs/t.yaml", "a b.yaml", "x'y.yaml"]:
            self.assertEqual(p, cli.as_cli_path(p))


class TestResultParsingAcceptsAnyFileName(unittest.TestCase):
    """Direct regression test for the [\\d\\S]+ result-parsing defect, using the
    real captured cfn-guard fixture rather than a synthetic payload."""

    FIXTURE = Path(__file__).parent.joinpath("test-data", "test-output-1.txt")

    def parse(self, data, name):
        return ss.Scan.parse_cfn_guard_output(
            ss.Scan(), data, name, RULES_METADATA
        )

    def test_findings_detected_regardless_of_file_name(self):
        raw = self.FIXTURE.read_text()
        baseline = self.parse(raw, "test.yaml")
        self.assertEqual(1, len(baseline["failed_rules"]))
        expected_score = baseline["sustainability_score"]

        for name in [
            "my test.yaml",
            "a b.yaml",
            "two  spaces.yaml",
            "тест 模板.yaml",
            "quote'name.yaml",
            "sub dir/test.yaml",
        ]:
            with self.subTest(name=name):
                result = self.parse(raw.replace("test.yaml", name), name)
                self.assertEqual(
                    expected_score,
                    result["sustainability_score"],
                    f"{name!r} lost its findings -- scan bypass",
                )
                self.assertEqual(1, len(result["failed_rules"]))


if __name__ == "__main__":
    unittest.main()
