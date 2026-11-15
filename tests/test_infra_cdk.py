"""AWS CDK synthesis and resource-assertion tests for infra/musnad_stack.py."""

from __future__ import annotations

import json
from pathlib import Path

from infra import ensure_node_for_jsii

ensure_node_for_jsii()

import aws_cdk as cdk
from aws_cdk.assertions import Capture, Match, Template

from infra.musnad_stack import MusnadStack, MusnadStackConfig


def _find_task_role_logical_id(raw_template: dict) -> str:
    task_defs = [
        res
        for res in raw_template.get("Resources", {}).values()
        if res.get("Type") == "AWS::ECS::TaskDefinition"
    ]
    assert len(task_defs) == 1
    ref = task_defs[0]["Properties"]["TaskRoleArn"]["Fn::GetAtt"][0]
    assert isinstance(ref, str)
    return ref


def test_default_http_stack_resources_and_least_privilege() -> None:
    app = cdk.App()
    stack = MusnadStack(app, "MusnadTestDefault")
    template = Template.from_stack(stack)
    raw = template.to_json()

    # 2-AZ public-only VPC with zero NAT gateways
    template.resource_count_is("AWS::EC2::VPC", 1)
    template.resource_count_is("AWS::EC2::Subnet", 2)
    template.resource_count_is("AWS::EC2::NatGateway", 0)
    template.all_resources_properties("AWS::EC2::Subnet", {"MapPublicIpOnLaunch": True})

    # ECR repository
    template.resource_count_is("AWS::ECR::Repository", 1)
    template.has_resource_properties(
        "AWS::ECR::Repository",
        {
            "RepositoryName": "musnad-demo",
            "ImageScanningConfiguration": {"ScanOnPush": True},
        },
    )

    # ECS cluster + Fargate task (0.5 vCPU / 1 GB) + Fargate service with public IP
    template.resource_count_is("AWS::ECS::Cluster", 1)
    template.has_resource_properties(
        "AWS::ECS::TaskDefinition",
        {
            "Cpu": "512",
            "Memory": "1024",
            "RequiresCompatibilities": ["FARGATE"],
            "ContainerDefinitions": Match.array_with(
                [
                    Match.object_like(
                        {
                            "PortMappings": Match.array_with([Match.object_like({"ContainerPort": 8501})]),
                            "Secrets": Match.array_with(
                                [Match.object_like({"Name": "GCP_SERVICE_ACCOUNT_JSON"})]
                            ),
                            "Environment": Match.array_with(
                                [
                                    {"Name": "MUSNAD_CLOUD", "Value": "1"},
                                    {"Name": "MUSNAD_DAILY_CAP", "Value": "200"},
                                ]
                            ),
                        }
                    )
                ]
            ),
        },
    )
    template.has_resource_properties(
        "AWS::ECS::Service",
        {
            "LaunchType": "FARGATE",
            "DesiredCount": 1,
            "NetworkConfiguration": {
                "AwsvpcConfiguration": Match.object_like({"AssignPublicIp": "ENABLED"})
            },
        },
    )

    # ALB + sticky sessions TargetGroup + health check on /_stcore/health + HTTP-only listener
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::LoadBalancer",
        {"Type": "application", "Scheme": "internet-facing"},
    )
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::TargetGroup",
        {
            "Port": 8501,
            "HealthCheckPath": "/_stcore/health",
            "TargetType": "ip",
            "TargetGroupAttributes": Match.array_with(
                [
                    {"Key": "stickiness.enabled", "Value": "true"},
                    {"Key": "stickiness.type", "Value": "lb_cookie"},
                ]
            ),
        },
    )
    template.resource_count_is("AWS::ElasticLoadBalancingV2::Listener", 1)
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::Listener",
        {"Port": 80, "Protocol": "HTTP"},
    )

    # CloudWatch 14-day retention + Secrets Manager + On-Demand DynamoDB TTL
    template.has_resource_properties("AWS::Logs::LogGroup", {"RetentionInDays": 14})
    template.has_resource_properties(
        "AWS::SecretsManager::Secret", {"Name": "musnad/gcp-service-account"}
    )
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "BillingMode": "PAY_PER_REQUEST",
            "KeySchema": [{"AttributeName": "pk", "KeyType": "HASH"}],
            "TimeToLiveSpecification": {"AttributeName": "expires_at", "Enabled": True},
        },
    )

    # AWS Budgets monthly alarm referencing BudgetEmail parameter
    assert "BudgetEmail" in raw.get("Parameters", {})
    template.has_resource_properties(
        "AWS::Budgets::Budget",
        {
            "Budget": Match.object_like({"BudgetType": "COST", "TimeUnit": "MONTHLY"}),
            "NotificationsWithSubscribers": Match.array_with(
                [
                    Match.object_like(
                        {
                            "Subscribers": [
                                {"SubscriptionType": "EMAIL", "Address": {"Ref": "BudgetEmail"}}
                            ]
                        }
                    )
                ]
            ),
        },
    )

    # Least-privilege Task Role check: only scoped DynamoDB + SecretsManager actions (no "*" resource)
    task_role_id = _find_task_role_logical_id(raw)
    task_policies = [
        res["Properties"]["PolicyDocument"]["Statement"]
        for res in raw.get("Resources", {}).values()
        if res.get("Type") == "AWS::IAM::Policy"
        and {"Ref": task_role_id} in res["Properties"].get("Roles", [])
    ]
    assert task_policies, "Expected least-privilege policy attached to ECS task role"
    all_actions: set[str] = set()
    for stmts in task_policies:
        for stmt in stmts:
            assert stmt["Effect"] == "Allow"
            assert stmt["Resource"] != "*"
            actions = stmt["Action"] if isinstance(stmt["Action"], list) else [stmt["Action"]]
            for act in actions:
                assert not act.endswith(":*"), f"Wildcard action not allowed: {act}"
                all_actions.add(act)
    assert {"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"}.issubset(all_actions)
    assert "secretsmanager:GetSecretValue" in all_actions


def test_optional_https_and_custom_task_sizing() -> None:
    app = cdk.App()
    cert_arn = "arn:aws:acm:us-east-1:123456789012:certificate/11111111-2222-3333-4444-555555555555"
    stack = MusnadStack(
        app,
        "MusnadTestHttps",
        config=MusnadStackConfig(
            cpu=1024,
            memory_limit_mib=2048,
            desired_count=2,
            certificate_arn=cert_arn,
            domain_name="musnad.example.com",
            budget_email="alerts@example.com",
            monthly_budget_usd=35.0,
        ),
    )
    template = Template.from_stack(stack)

    template.has_resource_properties(
        "AWS::ECS::TaskDefinition",
        {"Cpu": "1024", "Memory": "2048"},
    )
    template.has_resource_properties(
        "AWS::ECS::Service",
        {"DesiredCount": 2},
    )
    template.resource_count_is("AWS::ElasticLoadBalancingV2::Listener", 2)
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::Listener",
        {
            "Port": 443,
            "Protocol": "HTTPS",
            "Certificates": [{"CertificateArn": cert_arn}],
        },
    )
    template.has_resource_properties(
        "AWS::ElasticLoadBalancingV2::Listener",
        {
            "Port": 80,
            "Protocol": "HTTP",
            "DefaultActions": [
                {
                    "Type": "redirect",
                    "RedirectConfig": {
                        "Protocol": "HTTPS",
                        "Port": "443",
                        "StatusCode": "HTTP_301",
                    },
                }
            ],
        },
    )

    cap = Capture()
    template.has_output("ServiceUrl", {"Value": cap})
    assert cap.as_string() == "https://musnad.example.com"


def test_cdk_synth_writes_valid_cloudformation_artifact(tmp_path: Path) -> None:
    app = cdk.App(outdir=str(tmp_path))
    MusnadStack(app, "MusnadDemoStack")
    assembly = app.synth()
    tpl_path = Path(assembly.directory) / "MusnadDemoStack.template.json"
    assert tpl_path.is_file()
    payload = json.loads(tpl_path.read_text(encoding="utf-8"))
    assert "Resources" in payload
    assert len(payload["Resources"]) >= 15
