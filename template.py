from troposphere import (
    Ref,
    Template,
    GetAtt,
    Output,
    URLSuffix,
    StackName,
    Partition,
    Join,
    Region,
    Partition,
    AccountId,
)
from troposphere.awslambda import Function, Code, Permission
from troposphere.apigatewayv2 import Api
from troposphere.iam import Role, PolicyType
from troposphere.logs import LogGroup

from awacs.aws import Statement, Allow, PolicyDocument
from awacs.helpers.trust import get_lambda_assumerole_policy
from awacs import logs


import inspect

import kym


def create_template():
    template = Template(Description="Know Your Meme command for Slack")

    role = template.add_resource(
        Role("Role", AssumeRolePolicyDocument=get_lambda_assumerole_policy(),)
    )

    function = template.add_resource(
        Function(
            "Function",
            Handler="index." + kym.handler.__name__,
            Code=Code(ZipFile=inspect.getsource(kym),),
            MemorySize=512,
            Timeout=20,
            Runtime="python3.7",
            Role=GetAtt(role, "Arn"),
        )
    )

    log_group = template.add_resource(
        LogGroup(
            "LogGroup",
            LogGroupName=Join("/", ["/aws/lambda", Ref(function)]),
            RetentionInDays=30,
        )
    )

    policy = template.add_resource(
        PolicyType(
            "Policy",
            Roles=[Ref(role)],
            PolicyName=StackName,
            PolicyDocument=PolicyDocument(
                Statement=[
                    Statement(
                        Effect=Allow,
                        Action=[logs.CreateLogStream, logs.PutLogEvents],
                        Resource=[GetAtt(log_group, "Arn")],
                    ),
                ],
            ),
        )
    )

    permission = template.add_resource(
        Permission(
            "Permission",
            FunctionName=GetAtt(function, "Arn"),
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=Join(
                ":", ["arn", Partition, "execute-api", Region, AccountId, "*"]
            ),
            DependsOn=[policy],
        )
    )

    api = template.add_resource(
        Api(
            "Api",
            Name=StackName,
            ProtocolType="HTTP",
            Target=GetAtt(function, "Arn"),
            DependsOn=[permission],
        )
    )

    template.add_output(
        Output(
            "Url",
            Value=Join(
                "", ["https://", Ref(api), ".execute-api.", Region, ".", URLSuffix,]
            ),
        )
    )
    return template


if __name__ == "__main__":
    print(create_template().to_json())
