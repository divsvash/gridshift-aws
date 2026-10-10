
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from scheduler.schedule_job import schedule_job
from dispatcher.handler import lambda_handler


class TestAWSIntegration(unittest.TestCase):

    @patch("boto3.client")
    def test_scheduler_to_ecs_handoff(self, mock_boto3_client):
        job_id = "gridshift-integration-001"

        # Mock EventBridge Scheduler
        scheduler = MagicMock()
        scheduler.create_schedule.return_value = {
            "ScheduleArn": (
                "arn:aws:scheduler:ap-south-1:"
                "123456789012:schedule/default/"
                "gridshift-gridshift-integration-001"
            )
        }

        # Mock ECS Fargate
        ecs = MagicMock()
        ecs.run_task.return_value = {
            "tasks": [
                {
                    "taskArn": (
                        "arn:aws:ecs:ap-south-1:"
                        "123456789012:task/test-task"
                    )
                }
            ],
            "failures": [],
        }

        # Return the correct mock for each AWS service.
        def select_aws_client(service_name):
            if service_name == "scheduler":
                return scheduler
            if service_name == "ecs":
                return ecs
            raise AssertionError(
                f"Unexpected AWS service: {service_name}"
            )

        mock_boto3_client.side_effect = select_aws_client

        environment = {
            "DISPATCHER_LAMBDA_ARN": (
                "arn:aws:lambda:ap-south-1:"
                "123456789012:function:gridshift-dispatcher"
            ),
            "SCHEDULER_ROLE_ARN": (
                "arn:aws:iam::123456789012:"
                "role/gridshift-scheduler-role"
            ),
            "ECS_CLUSTER_ARN": (
                "arn:aws:ecs:ap-south-1:"
                "123456789012:cluster/gridshift-cluster"
            ),
            "ECS_TASK_DEFINITION_ARN": (
                "arn:aws:ecs:ap-south-1:"
                "123456789012:task-definition/gridshift-worker:1"
            ),
            "ECS_SUBNET_IDS": "subnet-111,subnet-222",
            "ECS_SECURITY_GROUP_ID": "sg-123456",
        }

        with patch.dict(os.environ, environment):
            run_at = (
                datetime.now(timezone.utc)
                + timedelta(hours=2)
            ).isoformat()

            # Step 1: Backend schedules the job.
            scheduled = schedule_job(job_id, run_at)

            scheduler_args = (
                scheduler.create_schedule.call_args.kwargs
            )

            # Step 2: Extract the actual Lambda payload.
            payload = json.loads(
                scheduler_args["Target"]["Input"]
            )

            self.assertEqual(payload, {"job_id": job_id})
            self.assertEqual(scheduled["status"], "scheduled")
            self.assertEqual(
                scheduler_args["FlexibleTimeWindow"],
                {"Mode": "OFF"},
            )
            self.assertEqual(
                scheduler_args["ActionAfterCompletion"],
                "DELETE",
            )

            # Step 3: Simulate Scheduler invoking Lambda.
            dispatched = lambda_handler(payload, None)

            # Step 4: Verify Lambda's ECS RunTask request.
            ecs_args = ecs.run_task.call_args.kwargs

            self.assertEqual(dispatched["status"], "submitted")
            self.assertEqual(dispatched["job_id"], job_id)
            self.assertEqual(ecs_args["launchType"], "FARGATE")
            self.assertEqual(ecs_args["count"], 1)

            self.assertEqual(
                ecs_args["overrides"]["containerOverrides"][0]
                ["environment"][0],
                {"name": "JOB_ID", "value": job_id},
            )

            self.assertEqual(
                ecs_args["networkConfiguration"]
                ["awsvpcConfiguration"]["assignPublicIp"],
                "ENABLED",
            )

            scheduler.create_schedule.assert_called_once()
            ecs.run_task.assert_called_once()


if __name__ == "__main__":
    unittest.main()
