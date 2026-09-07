import os

from pathlib import Path
from susscanner.scan import Scan
from susscanner.config import init_app
from susscanner.cli import main


__app_name__ = "susscanner"
__version__ = "1.3.0"

(
    SUCCESS,
    FILE_NOT_FOUND,
    JSON_ERROR,
    TEMPLATE_ERROR,
    ID_ERROR,
) = range(5)

# Exit code used when the underlying scanner (cfn-guard / cdk) could not be
# executed or failed in a way that means "we did not get a trustworthy result".
# Deliberately a distinct code so callers can tell "scan clean" (0) apart from
# "scan did not run" -- previously both produced 0.
SCANNER_ERROR = 5

# cfn-guard signals "ran fine but found violations" with a NON-ZERO status
# (0 on success, 5 when rules fail; other codes vary by version), so a non-zero
# exit is not by itself an execution failure. We therefore do not enumerate
# "good" exit codes -- see cli._require_trustworthy_output, which decides based
# on whether usable output was actually produced.

(
    _,
    SCORE_LOW,
    SCORE_MEDIUM,
    SCORE_HIGH,
) = range(4)

ERRORS = {
    FILE_NOT_FOUND: "config file error",
    JSON_ERROR: "json error",
    TEMPLATE_ERROR: "CloudFormation Template error",
    ID_ERROR: "id error",
}

DIR_PATH = os.path.dirname(__file__)
CONFIG_FILE_NAME = "rules_metadata.json"
CONFIG_FILE_PATH = Path(os.path.join(DIR_PATH, CONFIG_FILE_NAME))
