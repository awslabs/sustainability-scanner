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
        # check the CloudFormation template exists and is a regular file.
        # is_file() is False both for a missing path and for a directory (so a
        # directory argument is rejected here), and it already implies exists(),
        # which is why there is no separate existence check. The return code
        # stays FILE_NOT_FOUND rather than TEMPLATE_ERROR to keep the process
        # exit status for a missing template at 1, as it has always been.
        if not path.is_file():
            return ss.FILE_NOT_FOUND

        # check if the json inside the rules metadata config file is valid
        if not json.loads(ss.CONFIG_FILE_PATH.read_text()):
            return ss.JSON_ERROR

    return ss.SUCCESS
