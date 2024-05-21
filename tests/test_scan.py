import unittest
from pathlib import Path

from susscanner import Scan

TEST_DATA_DIR = Path(__file__).parent.joinpath("test-data")
RULES_METADATA_DIR = (
    Path(__file__).parent.parent.joinpath("susscanner").joinpath("rules_metadata.json")
)


class TestScan(unittest.TestCase):
    def test_empty_input(self):
        result = Scan.parse_cfn_guard_output(
            Scan(),
            "",
            "empty.yaml",
            RULES_METADATA_DIR,
        )
        self.assertEqual(len(result["failed_rules"]), 0)

    def test_input_with_1_violation(self):
        # Template source for this output is VPC_EC2_Instance_With_ENI from
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/quickref-ec2.html
        # with one modification - To-From ports changed from 22-22, to 20-23
        with open(TEST_DATA_DIR / "test-output-1.txt") as f:
            data = f.read()
        result = Scan.parse_cfn_guard_output(
            Scan(),
            data,
            "quickref-ec2.yaml",
            RULES_METADATA_DIR,
        )
        fr = result["failed_rules"]
        self.assertEqual(1, len(fr))
        self.assertEqual(fr[0]["rule_name"], "port_range_includes_ssh")

    def test_wordpress_output(self):
        # Template source for this output is
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/sample-templates-applications-eu-west-2.html
        with open(TEST_DATA_DIR / "wordpress-output.txt") as f:
            data = f.read()
        result = Scan.parse_cfn_guard_output(
            Scan(),
            data,
            "sample.yaml",
            RULES_METADATA_DIR,
        )
        fr = result["failed_rules"]
        self.assertEqual(0, len(fr))

    def test_ecs_cluster_output(self):
        # Template source for this output is
        # https://github.com/aws-samples/ecs-refarch-cloudformation/blob/master/infrastructure/ecs-cluster.yaml
        with open(TEST_DATA_DIR / "ecs-cluster-output.txt") as f:
            data = f.read()
        result = Scan.parse_cfn_guard_output(
            Scan(),
            data,
            "ecs-cluster.yaml",
            RULES_METADATA_DIR,
        )
        fr = result["failed_rules"]
        self.assertEqual(0, len(fr))

    def test_lamp_output(self):
        # Template source for this output is
        # https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/sample-templates-appframeworks-eu-west-1.html
        with open(TEST_DATA_DIR / "lamp-output.txt") as f:
            data = f.read()
        result = Scan.parse_cfn_guard_output(
            Scan(),
            data,
            "appframeworks.yaml",
            RULES_METADATA_DIR,
        )
        fr = result["failed_rules"]
        self.assertEqual(2, len(fr))
        self.assertEqual(fr[0]["rule_name"], "check_graviton_instance_usage_in_rds")
        self.assertEqual(fr[1]["rule_name"], "check_rds_performanceinsights_enabled")

    def test_rds_output(self):
        # Template source for this output is
        # https://github.com/awslabs/aws-cloudformation-templates/blob/master/aws/services/RDS/RDS_with_DBParameterGroup.yaml
        # with one modification - Added `EnablePerformanceInsights: 'true'`
        with open(TEST_DATA_DIR / "rds-output.txt") as f:
            data = f.read()
        result = Scan.parse_cfn_guard_output(
            Scan(),
            data,
            "rds.yaml",
            RULES_METADATA_DIR,
        )
        fr = result["failed_rules"]
        self.assertEqual(1, len(fr))
        self.assertEqual(fr[0]["rule_name"], "check_graviton_instance_usage_in_rds")


if __name__ == "__main__":
    unittest.main()
