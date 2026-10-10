# GridShift — AWS Execution Infrastructure

**Event-driven infrastructure for scheduling and executing compute workloads on AWS.**

GridShift's AWS execution layer accepts scheduled job requests from a backend, invokes a dispatcher at the scheduled time, and launches containerized workloads on Amazon ECS Fargate.

The infrastructure is defined using AWS CDK in Python.

## Architecture

```text
GridShift Backend
       |
       | CreateSchedule
       v
Amazon EventBridge Scheduler
       |
       | Scheduled invocation
       v
AWS Lambda Dispatcher
       |
       | ECS RunTask
       v
Amazon ECS Fargate
       |
       | Container execution
       v
Amazon CloudWatch Logs
```

The backend determines when a job should run. The AWS infrastructure handles scheduled dispatch and execution.

## AWS Components

| Component | Responsibility |
|---|---|
| EventBridge Scheduler | Creates one-time job schedules |
| AWS Lambda | Dispatches scheduled jobs to ECS |
| Amazon ECS Fargate | Runs containerized workloads |
| Amazon ECR | Stores container images published during CDK deployment |
| Amazon CloudWatch | Collects worker execution logs |
| AWS IAM | Controls scheduling, dispatch, and execution permissions |
| Amazon VPC | Provides networking for Fargate tasks |
| AWS CDK | Defines and provisions infrastructure |

## Repository Structure

```text
gridshift-aws/
├── app.py
├── infrastructure/
│   └── gridshift_stack.py
├── scheduler/
│   └── schedule_job.py
├── dispatcher/
│   └── handler.py
├── worker/
│   ├── Dockerfile
│   └── main.py
├── tests/
│   ├── test_scheduler.py
│   ├── test_dispatcher.py
│   └── test_aws_integration.py
├── README.md
└── AWS_DEPLOYMENT.md
```

## Execution Flow

1. The backend submits a job identifier and a scheduled UTC execution time.
2. EventBridge Scheduler creates a one-time schedule.
3. At the scheduled time, Scheduler invokes the dispatcher Lambda with the job identifier.
4. The dispatcher starts an ECS Fargate task.
5. The job identifier is passed into the container as `JOB_ID`.
6. The worker executes and emits structured logs to CloudWatch.

A successful dispatch indicates that ECS accepted the task submission. It does not guarantee successful worker completion.

## Technology Stack

- Python 3.12 for the deployed Lambda and worker runtime
- AWS CDK for infrastructure as code
- Boto3 for AWS API integration
- Docker for containerized execution
- Pytest for automated testing

## Local Development

Create and activate a Python virtual environment, then install the project dependencies.

Run the automated tests:

```powershell
python -m pytest -q
```

Build the worker container:

```powershell
docker build -t gridshift-worker:local ./worker
```

Run a local execution:

```powershell
docker run --rm -e JOB_ID=gridshift-test-001 gridshift-worker:local
```

Synthesize the CloudFormation stack:

```powershell
cdk synth --output cdk.out
```

## Verification Status

| Check | Result |
|---|---|
| Automated tests | 8 passed |
| Docker image build | Passed |
| Local worker execution | Passed |
| CDK synthesis | Passed |
| Infrastructure configuration checks | Passed |
| CloudFormation output verification | Passed |
| Live ECS deployment | Not yet verified |

**Deployment limitation:** The AWS account used for development has an AWS Organizations restriction that denies certain ECS operations. Consequently, live Fargate execution has not been verified.

## Deployment

See [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md) for the deployment procedure, required permissions, environment variables, and integration instructions.

## Scope

This repository implements GridShift's AWS execution infrastructure. The workload optimization logic and application backend are maintained separately.

The current worker is a deterministic demonstration workload, not the complete GridShift optimization engine.
