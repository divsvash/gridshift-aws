import json
import os

import boto3


def lambda_handler(event, context):
    job_id = event.get("job_id")

    if not isinstance(job_id, str) or not job_id.strip():
        raise ValueError("A non-empty job_id is required")

    cluster_arn = os.environ["ECS_CLUSTER_ARN"]
    task_definition_arn = os.environ["ECS_TASK_DEFINITION_ARN"]
    subnet_ids = os.environ["ECS_SUBNET_IDS"].split(",")
    security_group_id = os.environ["ECS_SECURITY_GROUP_ID"]

    ecs = boto3.client("ecs")

    response = ecs.run_task(
        cluster=cluster_arn,
        taskDefinition=task_definition_arn,
        launchType="FARGATE",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": subnet_ids,
                "securityGroups": [security_group_id],
                "assignPublicIp": "ENABLED",
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "gridshift-worker",
                    "environment": [
                        {"name": "JOB_ID", "value": job_id}
                    ],
                }
            ]
        },
    )

    failures = response.get("failures", [])

    if failures:
        raise RuntimeError(
            f"ECS failed to launch task: {json.dumps(failures)}"
        )

    tasks = response.get("tasks", [])

    if not tasks:
        raise RuntimeError("ECS returned no launched tasks")

    task_arn = tasks[0]["taskArn"]

    return {
        "status": "submitted",
        "job_id": job_id,
        "task_arn": task_arn,
    }
