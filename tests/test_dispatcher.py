import os
import unittest
from unittest.mock import patch, MagicMock

from dispatcher.handler import lambda_handler


class TestDispatcher(unittest.TestCase):

    @patch("dispatcher.handler.boto3.client")
    @patch.dict(os.environ, {
        "ECS_CLUSTER_ARN": "test-cluster",
        "ECS_TASK_DEFINITION_ARN": "test-task",
        "ECS_SUBNET_IDS": "subnet-a,subnet-b",
        "ECS_SECURITY_GROUP_ID": "sg-test",
    })
    def test_launches_correct_task(self, mock_client):
        fake_ecs = MagicMock()

        fake_ecs.run_task.return_value = {
            "tasks": [{"taskArn": "arn:aws:ecs:fake-task"}],
            "failures": [],
        }

        mock_client.return_value = fake_ecs

        result = lambda_handler(
            {"job_id": "job-001"},
            None,
        )

        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["job_id"], "job-001")

        mock_client.assert_called_once_with("ecs")

        fake_ecs.run_task.assert_called_once()

        request = fake_ecs.run_task.call_args.kwargs

        self.assertEqual(request["cluster"], "test-cluster")
        self.assertEqual(request["taskDefinition"], "test-task")
        self.assertEqual(request["launchType"], "FARGATE")

        overrides = request["overrides"]["containerOverrides"]

        self.assertEqual(
            overrides[0]["environment"][0],
            {"name": "JOB_ID", "value": "job-001"},
        )

    def test_rejects_missing_job_id(self):
        with self.assertRaises(ValueError):
            lambda_handler({}, None)


if __name__ == "__main__":
    unittest.main()
