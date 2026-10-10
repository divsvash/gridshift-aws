
from pathlib import Path

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_ecs as ecs,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as lambda_,
)
from aws_cdk import (
    aws_logs as logs,
)
from constructs import Construct


class GridShiftStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --------------------------------------------------
        # 1. NETWORKING
        # --------------------------------------------------

        # Temporary VPC configuration for offline synthesis.
        # Replace these IDs with real AWS resource IDs
        # before deployment.
        vpc = ec2.Vpc.from_vpc_attributes(
            self,
            "GridShiftVpc",
            vpc_id="vpc-PLACEHOLDER",
            availability_zones=[
                "ap-south-1a",
                "ap-south-1b",
            ],
            public_subnet_ids=[
                "subnet-PLACEHOLDER-A",
                "subnet-PLACEHOLDER-B",
            ],
        )

        self.worker_security_group = ec2.SecurityGroup(
            self,
            "GridShiftWorkerSecurityGroup",
            vpc=vpc,
            description="Security group for GridShift Fargate workers",
            allow_all_outbound=True,
        )

        # --------------------------------------------------
        # 2. ECS CLUSTER
        # --------------------------------------------------

        self.cluster = ecs.Cluster(
            self,
            "GridShiftCluster",
            vpc=vpc,
            cluster_name="gridshift-cluster",
        )

        # --------------------------------------------------
        # 3. CLOUDWATCH LOGGING
        # --------------------------------------------------

        self.log_group = logs.LogGroup(
            self,
            "GridShiftWorkerLogs",
            log_group_name="/gridshift/worker",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --------------------------------------------------
        # 4. FARGATE TASK DEFINITION
        # --------------------------------------------------

        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "GridShiftTaskDefinition",
            family="gridshift-worker",
            cpu=256,
            memory_limit_mib=512,
        )

        # --------------------------------------------------
        # 5. DOCKER WORKER CONTAINER
        # --------------------------------------------------

        worker_directory = (
            Path(__file__).resolve().parent.parent / "worker"
        )

        self.task_definition.add_container(
            "GridShiftContainer",
            container_name="gridshift-worker",
            image=ecs.ContainerImage.from_asset(
                str(worker_directory)
            ),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="gridshift",
                log_group=self.log_group,
            ),
            environment={
                "JOB_ID": "gridshift-default",
            },
            essential=True,
        )

        # --------------------------------------------------
        # 6. LAMBDA DISPATCHER
        # --------------------------------------------------

        dispatcher_directory = (
            Path(__file__).resolve().parent.parent / "dispatcher"
        )

        self.dispatcher = lambda_.Function(
            self,
            "GridShiftDispatcher",
            function_name="gridshift-dispatcher",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(
                str(dispatcher_directory)
            ),
            timeout=Duration.seconds(30),
            environment={
                "ECS_CLUSTER_ARN": (
                    self.cluster.cluster_arn
                ),
                "ECS_TASK_DEFINITION_ARN": (
                    self.task_definition.task_definition_arn
                ),
                "ECS_SUBNET_IDS": ",".join(
                    subnet.subnet_id
                    for subnet in vpc.public_subnets
                ),
                "ECS_SECURITY_GROUP_ID": (
                    self.worker_security_group.security_group_id
                ),
            },
        )

        # --------------------------------------------------
        # 7. IAM PERMISSIONS
        # --------------------------------------------------

        # Allow Lambda to launch only this task definition
        # in the GridShift cluster.
        self.dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:RunTask",
                ],
                resources=[
                    self.task_definition.task_definition_arn,
                ],
                conditions={
                    "ArnEquals": {
                        "ecs:cluster": self.cluster.cluster_arn,
                    }
                },
            )
        )

        # Allow Lambda to pass the task's IAM roles to ECS.
        self.dispatcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:PassRole",
                ],
                resources=[
                    self.task_definition.execution_role.role_arn,
                    self.task_definition.task_role.role_arn,
                ],
                conditions={
                    "StringEquals": {
                        "iam:PassedToService": (
                            "ecs-tasks.amazonaws.com"
                        )
                    }
                },
            )
        )
