import aws_cdk as cdk

from infrastructure.gridshift_stack import GridShiftStack

app = cdk.App()

GridShiftStack(
    app,
    "GridShiftStack",
    env=cdk.Environment(
        account="123456789012",
        region="ap-south-1",
    ),
)

app.synth()
