import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from scheduler.schedule_job import schedule_job


class TestScheduler(unittest.TestCase):

    @patch("scheduler.schedule_job.boto3.client")
    @patch.dict(os.environ, {
        "DISPATCHER_LAMBDA_ARN": "arn:aws:lambda:ap-south-1:123456789012:function:gridshift-dispatcher",
        "SCHEDULER_ROLE_ARN": "arn:aws:iam::123456789012:role/gridshift-scheduler-role",
    })
    def test_creates_one_time_schedule(self, mock_client):
        fake_scheduler = MagicMock()
        fake_scheduler.create_schedule.return_value = {
            "ScheduleArn": "arn:aws:scheduler:ap-south-1:123456789012:schedule/default/gridshift-job-001"
        }
        mock_client.return_value = fake_scheduler

        # Use a future time so this test keeps working tomorrow.
        run_at = (
            datetime.now(timezone.utc) + timedelta(hours=2)
        ).replace(microsecond=0).isoformat()

        result = schedule_job("job-001", run_at)

        self.assertEqual(result["status"], "scheduled")
        self.assertEqual(result["job_id"], "job-001")
        self.assertEqual(result["schedule_name"], "gridshift-job-001")

        mock_client.assert_called_once_with("scheduler")
        fake_scheduler.create_schedule.assert_called_once()

        request = fake_scheduler.create_schedule.call_args.kwargs

        self.assertEqual(request["Name"], "gridshift-job-001")
        self.assertEqual(request["ScheduleExpressionTimezone"], "UTC")
        self.assertEqual(request["FlexibleTimeWindow"], {"Mode": "OFF"})
        self.assertEqual(request["ActionAfterCompletion"], "DELETE")

        expected_time = datetime.fromisoformat(run_at).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        self.assertEqual(
            request["ScheduleExpression"],
            f"at({expected_time})",
        )

        self.assertEqual(
            request["Target"]["Arn"],
            os.environ["DISPATCHER_LAMBDA_ARN"],
        )
        self.assertEqual(
            request["Target"]["RoleArn"],
            os.environ["SCHEDULER_ROLE_ARN"],
        )
        self.assertEqual(
            json.loads(request["Target"]["Input"]),
            {"job_id": "job-001"},
        )

    def test_rejects_empty_job_id(self):
        with self.assertRaises(ValueError):
            schedule_job("", "2027-01-01T00:00:00Z")

    def test_rejects_invalid_timestamp(self):
        with self.assertRaises(ValueError):
            schedule_job("job-001", "not-a-date")

    def test_rejects_missing_timezone(self):
        with self.assertRaises(ValueError):
            schedule_job("job-001", "2027-01-01T00:00:00")

    def test_rejects_past_timestamp(self):
        with self.assertRaises(ValueError):
            schedule_job("job-001", "2020-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
