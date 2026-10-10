import os

import aws_cdk as cdk

from infrastructure.gridshift_stack import GridShiftStack

app = cdk.App()

GridShiftStack(
    app,
    "GridShiftStack",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region="ap-south-1"
    ),
)

app.synth()
