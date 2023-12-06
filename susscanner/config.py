import json
import susscanner as ss


def init_app(cfn_template: list) -> int:
    """
    check if the configuration file and CloudFormation template exists and if
    the configuration is valid json.

    Args:
        cfn_template (str): the CloudFormation template.

    Returns:
        int: the success code if the configuration file exists and is valid.
        and the CloudFormation template exists
    """
    for path in cfn_template:
        # check if the config file exists
        if not path.is_file():
            return ss.FILE_ERROR

        # check if the json inside the config file is valid
        if not json.loads(ss.CONFIG_FILE_PATH.read_text()):
            return ss.JSON_ERROR

        # check if the CloudFormation Template exists
        if not path.exists():
            return ss.TEMPLATE_ERROR

    return ss.SUCCESS
