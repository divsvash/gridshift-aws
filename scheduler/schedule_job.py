
import json
import os
import re
from datetime import datetime, timezone

import boto3


def schedule_job(job_id: str, run_at: str) -> dict:
    """
    Schedule a GridShift job using AWS EventBridge Scheduler.

    Args:
        job_id: Unique identifier for the workload.
        run_at: ISO 8601 timestamp with timezone.
                Example: 2026-10-11T04:30:00Z
    """

    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("job_id must be a non-empty string")

    # Parse and validate the execution timestamp.
    try:
        execution_time = datetime.fromisoformat(
            run_at.replace("Z", "+00:00")
        )
    except (ValueError, AttributeError) as exc:
        raise ValueError("Invalid run_at timestamp") from exc

    if execution_time.tzinfo is None:
        raise ValueError("run_at must include a timezone")

    execution_time = execution_time.astimezone(timezone.utc)

    if execution_time <= datetime.now(timezone.utc):
        raise ValueError("run_at must be in the future")

    # Read deployment-specific values from the environment.
    dispatcher_arn = os.environ["DISPATCHER_LAMBDA_ARN"]
    scheduler_role_arn = os.environ["SCHEDULER_ROLE_ARN"]

    # Keep the schedule name within AWS naming limits.
    safe_job_id = re.sub(
        r"[^a-zA-Z0-9_-]",
        "-",
        job_id,
    )

    schedule_name = f"gridshift-{safe_job_id}"

    if len(schedule_name) > 64:
        raise ValueError("job_id is too long for a schedule name")

    # EventBridge Scheduler uses a timezone-free
    # timestamp inside the at() expression.
    schedule_time = execution_time.strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    scheduler = boto3.client("scheduler")

    response = scheduler.create_schedule(
        Name=schedule_name,
        ScheduleExpression=f"at({schedule_time})",
        ScheduleExpressionTimezone="UTC",
        FlexibleTimeWindow={
            "Mode": "OFF",
        },
        Target={
            "Arn": dispatcher_arn,
            "RoleArn": scheduler_role_arn,
            "Input": json.dumps({
                "job_id": job_id,
            }),
        },
        ActionAfterCompletion="DELETE",
        State="ENABLED",
    )

    return {
        "job_id": job_id,
        "schedule_name": schedule_name,
        "scheduled_for": execution_time.isoformat(),
        "schedule_arn": response["ScheduleArn"],
        "status": "scheduled",
    }
