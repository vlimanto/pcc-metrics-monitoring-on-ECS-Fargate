import aws_cdk as core
import aws_cdk.assertions as assertions

from prometheus_ecs_fargate_cdk.prometheus_ecs_fargate_cdk_stack import PrometheusEcsFargateCdkStack

# example tests. To run these tests, uncomment this file along with the example
# resource in prometheus_ecs_fargate_cdk/prometheus_ecs_fargate_cdk_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = PrometheusEcsFargateCdkStack(app, "prometheus-ecs-fargate-cdk")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
