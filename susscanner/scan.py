import json
import re

import susscanner as ss

from pathlib import Path


class Scan:
    """The class takes output of CFN Guard in JSON format, parses it and
    re-formats it with additional metadata.

    Even though, CFN Guard runs with JSON output option, the output it
    provides is not valid JSON, it includes some additional lines which are
    not JSON. If you run validation with multiple rule files, then for each
    failed rule file output will look like this:

    <template_file.yaml> = FAIL
    FAILED rules
    <list of rule names, one per line>
    ---
    {
       here comes JSON output with details of failed rules
    }{
       JSON output of the next rule file(s) with compliant rules
    }<template_file.yaml> = FAIL
    FAILED rules
    .....

    So this class finds blocks with failed rules in the output and parses
    them. Each JSON block has the following structure (only relevant elements
    are shown below):

    {
    "not_compliant": [
        {
        "Rule": {
            "name": "<rule_name>",
            "checks": [
            {
                "Clause": {
                "Unary/Binary": {
                    "messages": {
                    "error_message": "<message with resource path and line number>"
                    },
                    "check": {
                    "Unresolved": {
                        "value": {
                        "traversed_to": {
                            "path": "<resource path in template>"
                        }
                        }
                    },
                    "Resolved": {
                        "from": {
                        "path": "<resource path in template>"
                        }
                    }
                    }
                }
                }
            }
            ]
        }
        }
    ]
    }

    Blocks Unresolved and Resolved are mutually exclusive, so for the same
    failed check only one can be present. Insid checks array there can be
    element Disjunctions if rule contained disjunction and inside it there
    will be one more checks block.
    """

    def load_metadata(self, rules_metadata: Path):
        """Loads rules metadata from metadata file. Only enabled rules are loaded.

        Args:
            rules_metadata (Path): location of the rule metadata.
            Will be a Path value if specefied, otherwise None.

        Returns:
            [dictionary] - keys are rule names and values are metadata object
            as defined in the file.
        """
        result = {}
        # check if a rules metadata location is specified with -r or --rules
        if rules_metadata:  # rules metadata is specified
            data = json.loads(rules_metadata.resolve().read_text())
        else:  # not specified, using the defaults
            data = json.loads(ss.CONFIG_FILE_PATH.read_text())

        for group in data["all_rules"].items():
            if group[1]["enabled"]:
                for rule in group[1]["rules"]:
                    if rule["enabled"]:
                        result[rule["rule_name"]] = rule
        return result

    @staticmethod
    def get_path(obj: dict):
        """This method finds path key in a dictionary, even if path is located in nested dictionaries.

        Args:
            obj: dictionary to search in

        Returns:
            value of the path key or None
        """
        for key in obj:
            value = obj[key]
            if key == "path":
                return value
            elif type(value) is dict:
                return Scan.get_path(value)

    def parse_checks(self, checks: list):
        """This method parses failed checks output and returned resources part of it. Each resource contains
        resource name and line number in CF template.

        Args:
            checks(list): list of failed checks

        Returns:
            generator object, which returns resources which has failed the check. Resources are dictionaries containing
            2 keys: line and name.
        """
        for check in checks:
            # If this is disjunction rule, then recursively parse checks inside it.
            if "Disjunctions" in check:
                for sub_parse in self.parse_checks(check["Disjunctions"]["checks"]):
                    yield sub_parse
            else:
                if "Clause" in check:
                    clause = check["Clause"]
                    resource = {}
                    rule_type = ""
                    if "Unary" in clause:
                        rule_type = "Unary"
                    elif "Binary" in clause:
                        rule_type = "Binary"
                    error_msg = clause[rule_type]["messages"]["error_message"]
                    typed_check = clause[rule_type]["check"]
                    resource["name"] = Scan.get_path(typed_check)

                    # error message contains line number in the format like this:
                    # "Value traversed to [Path=/Resources/API-GW-1/Properties[L:12,C:3]"
                    # so the regex below just finds it.
                    line = re.findall(r"\[L\:([0-9]*),C\:[0-9]*\]", error_msg)
                    resource["line"] = line[0]
                    yield resource

    @staticmethod
    def get_object_to_parse(jsons):
        """Returns dictionary object which should be parsed for the results. Only the first one of the inout list
        will be returned because remaining ones are rules which passed.

        Args:
            jsons (list): List of strings, where each element represents result of a rule file evaluation.

        Returns:
            A dict which represents output of failed rule file.
        """
        # Take only first json as others are not applicable
        if len(jsons) > 1:
            obj = json.loads(jsons[0] + "}")
        else:
            obj = json.loads(jsons[0])
        return obj

    def parse_failed_rules(self, rules_obj, md, failed_rules):
        """
        This method parses output of CFN Guard for 1 rule file and add dictionary with additional metadata for each
        rule to failed_rules list.
        Args:
            rules_obj (dict): output of CF guard for one rule file
            md (dict): rules metadata dictionary
            failed_rules (list): list to which this method adds a dictionary for each failed rule, containing:
            * rule_name - rule name
            * severity - rule severity
            * message - message explaining the rule
            * links - links to additional material
            * resources - list of resources, which point to all resources in a CF template which had failed this rule
        Returns:
        """
        for not_comp_rule in rules_obj["not_compliant"]:
            rule_name = not_comp_rule["Rule"]["name"]
            if rule_name in md:
                meta = md[rule_name]
                failed_rule = {
                    "rule_name": not_comp_rule["Rule"]["name"],
                    "severity": meta["severity"],
                    "message": meta["message"],
                    "links": meta["links"],
                    "resources": list(
                        self.parse_checks(not_comp_rule["Rule"]["checks"])
                    ),
                }
                failed_rules.append(failed_rule)

    def calculate_sustainability_score(self, failed_rules: list) -> int:
        """Calculate the sustainability score by providing a penalty for each
        rule failed based on the severity of that rule.

        Args:
            failed_rules (list): a list of all failed rules

        Returns:
            sustainability_score (int): the sustainability score, lower is better.
        """
        sustainability_score = 0

        for failed_rule in failed_rules:
            rule_severity = failed_rule["severity"]

            if rule_severity == "LOW":
                sustainability_score += ss.SCORE_LOW
            elif rule_severity == "MEDIUM":
                sustainability_score += ss.SCORE_MEDIUM
            elif rule_severity == "HIGH":
                sustainability_score += ss.SCORE_HIGH
            else:
                raise ValueError(
                    f"The severity level of rule {failed_rule['rule_name']} was set "
                    + f"to {rule_severity} this type is not supported. "
                    + "Supported types are LOW, MEDIUM, HIGH"
                )

        return sustainability_score

    def parse_cfn_guard_output(
        self,
        cfn_guard_output: str,
        template_name: str,
        rules_metadata: Path,
    ) -> dict:
        """This function parses JSON output of the cfn guard.

        Args:
            cfn_guard_output (str): output produced by CFN guard in JSON format.

        Returns:
            summary dictionary object which contains failed_rules array containing
            objects with following structure:
            {
               "rule_name": "",
               "severity": "",
               "message": "",
               "links": [],
               "resources": [{"name": "", "line": 123}]
            }
        """
        md = self.load_metadata(rules_metadata)
        failed_rules = []
        matcher = re.match(
            r".*(}|^)([\d\S]+) Status = FAIL", cfn_guard_output, re.DOTALL
        )
        if matcher:
            file_name = matcher.group(2)
            failed_pieces = cfn_guard_output.split(file_name + " ")
            for p in failed_pieces:
                delim = p.find("---")
                if delim >= 0:
                    json_text = p[delim + 3 :]
                    jsons = json_text.split("}{")
                    if len(jsons) > 0:
                        obj = Scan.get_object_to_parse(jsons)
                        self.parse_failed_rules(obj, md, failed_rules)

        sustainability_score = self.calculate_sustainability_score(failed_rules)

        return {
            "title": "Sustainability Scanner Report",
            "file": template_name,
            "version": ss.__version__,
            "sustainability_score": sustainability_score,
            "failed_rules": failed_rules,
        }

    @classmethod
    def filter_results(cls, cfn_guard_output, template_name, rules_metadata):
        parsed = cls().parse_cfn_guard_output(
            cfn_guard_output, template_name, rules_metadata
        )
        print(json.dumps(parsed, indent=4))
