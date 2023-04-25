import json
import susscanner as ss

from pathlib import Path


def init_app(cfn_template: str) -> int:
    """
    check if the configuration file and CloudFormation template exists and if
    the configuration is valid json.

    Args:
        cfn_template (str): the CloudFormation template.

    Returns:
        int: the success code if the configuration file exists and is valid.
        and the CloudFormation template exists
    """
    # check if the config file exists
    if not Path.exists(ss.CONFIG_FILE_PATH):
        return ss.FILE_ERROR

    # check if the json inside the config file is valid
    if not json.loads(ss.CONFIG_FILE_PATH.read_text()):
        return ss.JSON_ERROR

    # check if the CloudFormation Template exists
    if not Path(cfn_template).exists():
        return ss.TEMPLATE_ERROR

    return ss.SUCCESS
