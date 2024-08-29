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
