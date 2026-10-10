# GridShift — AWS Deployment Guide

This document describes how to deploy, configure, integrate, and verify the GridShift AWS execution infrastructure.

## 1. Prerequisites

Required tools:

- AWS CLI with valid credentials
- AWS CDK CLI
- Python and project dependencies
- Docker Desktop or a compatible Docker daemon
- AWS account with permissions to deploy the required services

**Target AWS Region:** `ap-south-1` (Mumbai)

The deploying identity must have permissions to create and manage CloudFormation, IAM, Lambda, ECS, ECR, EventBridge Scheduler, CloudWatch Logs, and VPC resources, as well as publish CDK assets.

## 2. Configure AWS Credentials

Check the active AWS identity:

```powershell
aws sts get-caller-identity
```

Check the configured region:

```powershell
aws configure get region
```

Set the deployment region for the current PowerShell session:

```powershell
$env:AWS_DEFAULT_REGION = "ap-south-1"
```

The CDK application explicitly targets `ap-south-1`.

## 3. Validate Locally

Before deployment, run:

```powershell
python -m pytest -q
```

Build the worker:

```powershell
docker build -t gridshift-worker:local ./worker
```

Test the worker:

```powershell
docker run --rm -e JOB_ID=gridshift-smoke-001 gridshift-worker:local
```

Synthesize the infrastructure:

```powershell
cdk synth --output cdk.out
```

Confirm that the synthesized stack contains the expected resources and outputs.

## 4. Bootstrap AWS CDK

CDK bootstrapping prepares the account and region for deploying assets and CloudFormation stacks.

Run:

```powershell
cdk bootstrap aws://ACCOUNT_ID/ap-south-1
```

Replace `ACCOUNT_ID` with the AWS account ID returned by `aws sts get-caller-identity`.

Bootstrapping may require elevated IAM and CloudFormation permissions.

## 5. Deploy the Stack

Run:

```powershell
cdk deploy GridShiftStack
```

The deployment provisions:

- VPC with public subnets
- ECS cluster
- Fargate task definition
- Dispatcher Lambda function
- CloudWatch worker log group
- IAM execution and invocation roles
- Backend scheduling IAM managed policy

CDK also builds and publishes the worker container asset.

**Important:** Deployment is expected to fail or be blocked if the active AWS account has an Organizations Service Control Policy restricting required ECS operations.

Do not bypass organizational restrictions. Use an appropriately authorized AWS account.

## 6. CloudFormation Outputs

A successful deployment exports five values:

| Output                      | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| `DispatcherLambdaArn`       | Lambda invoked by EventBridge Scheduler          |
| `SchedulerRoleArn`          | IAM role assumed by EventBridge Scheduler        |
| `EcsClusterArn`             | ECS cluster used by the dispatcher               |
| `EcsTaskDefinitionArn`      | Worker task definition                           |
| `BackendSchedulerPolicyArn` | Managed IAM policy for backend schedule creation |

Retrieve them with:

```powershell
aws cloudformation describe-stacks --stack-name GridShiftStack --region ap-south-1 --query "Stacks[0].Outputs"
```

These are generated during deployment. Do not substitute placeholder ARNs in a production integration.

## 7. Backend Integration

The backend scheduling module requires these environment variables:

```env
AWS_DEFAULT_REGION=ap-south-1
DISPATCHER_LAMBDA_ARN=<DispatcherLambdaArn>
SCHEDULER_ROLE_ARN=<SchedulerRoleArn>
```

The backend's AWS identity must have the exported `BackendSchedulerPolicyArn` managed policy attached, or equivalent authorized permissions.

The managed policy permits:

- `scheduler:CreateSchedule` for schedules in the default group matching `gridshift-*`
- `iam:PassRole` for the Scheduler execution role, scoped to the Scheduler service

Ensure that backend-generated schedule names match the configured IAM resource pattern.

The backend is responsible for supplying a valid job identifier and scheduled execution time.

## 8. Scheduler Payload

The scheduled Lambda invocation uses this JSON structure:

```json
{
  "job_id": "gridshift-example-001"
}
```

EventBridge Scheduler assumes the configured Scheduler execution role and invokes the dispatcher Lambda.

The dispatcher reads the job identifier and calls ECS `RunTask`.

## 9. Dispatcher Configuration

The Lambda dispatcher receives these environment variables from CDK:

```text
ECS_CLUSTER_ARN
ECS_TASK_DEFINITION_ARN
ECS_SUBNET_IDS
ECS_SECURITY_GROUP_ID
```

The dispatcher launches Fargate tasks using:

- Fargate launch type
- `awsvpc` networking
- Public subnets
- Public IP assignment enabled
- Container environment override for `JOB_ID`

The ECS task definition uses 256 CPU units and 512 MiB memory.

## 10. IAM Permissions

The deployment defines distinct roles and permissions for different responsibilities.

**Backend identity**

Creates one-time EventBridge schedules and passes the designated Scheduler role.

**Scheduler execution role**

Allows EventBridge Scheduler to invoke the dispatcher Lambda.

**Lambda execution role**

Allows the dispatcher to submit ECS tasks and pass the required ECS task roles.

**ECS task execution role**

Allows ECS to retrieve the container image from ECR and publish logs to CloudWatch.

Permissions must be validated in the deployed environment, since local tests and CDK synthesis cannot establish that AWS Organizations policies or other account-level restrictions permit the operations.

## 11. Logging and Monitoring

Worker logs are configured for the CloudWatch log group:

```text
/gridshift/worker
```

The worker emits structured JSON events including:

```text
job_started
job_completed
```

Events include the job identifier and execution timestamps.

Inspect logs using:

```powershell
aws logs tail /gridshift/worker --follow --region ap-south-1
```

The worker currently performs a deterministic demonstration computation.

## 12. Live Verification

After deployment to an authorized AWS account:

1. Confirm the CloudFormation stack reaches `CREATE_COMPLETE` or `UPDATE_COMPLETE`.
2. Verify the ECS cluster and task definition exist.
3. Verify the dispatcher Lambda configuration.
4. Attach the backend scheduling policy to the intended backend execution identity.
5. Create a future one-time schedule using the backend integration.
6. Confirm EventBridge Scheduler invokes Lambda.
7. Confirm Lambda submits an ECS task without failures.
8. Confirm the ECS task starts and stops successfully.
9. Inspect CloudWatch logs for the matching `job_id` and `job_completed` event.

A successful `RunTask` response confirms submission, not successful job execution. Check the ECS task's final status and exit code.

## 13. Known Restrictions

The development AWS account currently has an AWS Organizations Service Control Policy explicitly denying ECS operations, including cluster listing and description.

Because of this:

- Local Docker execution has been verified.
- CDK synthesis has been verified.
- Scheduler and dispatcher behavior has been tested using mocks.
- Live ECS execution has not been verified.

Do not describe the infrastructure as successfully deployed until a real AWS deployment and end-to-end execution have been completed.

## 14. Cost Considerations

Deploying this infrastructure can incur charges for:

- ECS Fargate compute
- Public IPv4 addresses
- EventBridge Scheduler usage
- Lambda invocations
- CloudWatch log storage
- Data transfer and other AWS resources

The VPC configuration does not use NAT gateways, but this does not make the entire infrastructure free.

Review AWS pricing and account billing settings before deployment.

## 15. Cleanup

To remove the deployed CloudFormation stack:

```powershell
cdk destroy GridShiftStack
```

Check for resources that require separate cleanup, including schedules created dynamically by the backend, retained resources, logs, and published container assets.

Only destroy the stack when it is no longer required.

## 16. Deployment Checklist

- [ ] AWS credentials configured
- [ ] Target region confirmed as `ap-south-1`
- [ ] Docker daemon running
- [ ] Local tests passing
- [ ] Worker image builds successfully
- [ ] CDK synthesis successful
- [ ] Required AWS permissions available
- [ ] CDK environment bootstrapped
- [ ] CloudFormation stack deployed
- [ ] All five outputs retrieved
- [ ] Backend IAM policy attached
- [ ] Backend environment variables configured
- [ ] Scheduled Lambda invocation verified
- [ ] ECS task completion verified
- [ ] CloudWatch logs verified

---

**Current status:** Locally validated infrastructure. Live AWS deployment pending account authorization.
