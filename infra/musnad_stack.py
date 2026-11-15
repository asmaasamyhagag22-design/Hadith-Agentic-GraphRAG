"""AWS CDK stack for hosting the Musnad Streamlit demo on ECS Fargate behind ALB."""

from __future__ import annotations

from dataclasses import dataclass

import aws_cdk as cdk
from aws_cdk import (
    CfnOutput,
    CfnParameter,
    Duration,
    RemovalPolicy,
    aws_budgets as budgets,
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct


@dataclass(frozen=True)
class MusnadStackConfig:
    """Configurable sizing, domain/TLS, quota, and budget settings for MusnadStack."""

    repository_name: str = "musnad-demo"
    image_tag: str = "latest"
    cpu: int = 512
    memory_limit_mib: int = 1024
    desired_count: int = 1
    daily_cap: int = 200
    session_limit: int = 10
    ip_hourly_limit: int = 20
    gcp_project: str = ""
    gcp_location: str = "us-central1"
    secret_name: str = "musnad/gcp-service-account"
    log_retention_days: int = 14
    certificate_arn: str | None = None
    domain_name: str | None = None
    budget_email: str | None = None
    monthly_budget_usd: float = 50.0


def _resolve_retention(days: int) -> logs.RetentionDays:
    if days <= 14:
        return logs.RetentionDays.TWO_WEEKS
    if days <= 30:
        return logs.RetentionDays.ONE_MONTH
    return logs.RetentionDays.THREE_MONTHS


class MusnadStack(cdk.Stack):
    """ECS Fargate + ALB + ECR + Secrets Manager + DynamoDB + CloudWatch + Budgets."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        config: MusnadStackConfig | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)  # type: ignore[arg-type]
        cfg = config or MusnadStackConfig()

        # CloudFormation parameter for AWS Budgets monthly alert email
        email_param_kwargs: dict[str, object] = {
            "type": "String",
            "description": "Email address that receives AWS Budgets monthly cost threshold alerts.",
        }
        if cfg.budget_email:
            email_param_kwargs["default"] = cfg.budget_email
        budget_email_param = CfnParameter(self, "BudgetEmail", **email_param_kwargs)

        # Public-only 2-AZ VPC with zero NAT gateways to eliminate idle NAT cost
        vpc = ec2.Vpc(
            self,
            "MusnadVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        # ECR repository for the slim cloud container image
        ecr_repo = ecr.Repository(
            self,
            "MusnadRepository",
            repository_name=cfg.repository_name,
            image_scan_on_push=True,
            empty_on_delete=True,
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    max_image_count=5,
                    description="Retain at most 5 container images to limit ECR storage cost.",
                )
            ],
        )

        # CloudWatch log group with 14-day retention
        log_group = logs.LogGroup(
            self,
            "MusnadLogGroup",
            log_group_name="/ecs/musnad-demo",
            retention=_resolve_retention(cfg.log_retention_days),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Secrets Manager secret storing the Vertex AI service-account JSON key
        gcp_secret = secretsmanager.Secret(
            self,
            "GcpServiceAccountSecret",
            secret_name=cfg.secret_name,
            description="Least-privilege GCP Vertex AI User service-account JSON key for Musnad.",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # On-demand DynamoDB table with TTL for global daily and per-IP hourly usage caps
        usage_table = dynamodb.Table(
            self,
            "MusnadUsageTable",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # ECS Cluster + Fargate TaskDefinition
        cluster = ecs.Cluster(
            self,
            "MusnadCluster",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.DISABLED,
        )

        task_def = ecs.FargateTaskDefinition(
            self,
            "MusnadTaskDefinition",
            cpu=cfg.cpu,
            memory_limit_mib=cfg.memory_limit_mib,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.X86_64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )

        # Least-privilege Task Role: ONLY this table (Get/Put/Update) and ONLY this secret
        usage_table.grant(
            task_def.task_role,
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
        )
        gcp_secret.grant_read(task_def.task_role)

        container = task_def.add_container(
            "MusnadWeb",
            image=ecs.ContainerImage.from_ecr_repository(ecr_repo, tag=cfg.image_tag),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="musnad",
                log_group=log_group,
            ),
            environment={
                "MUSNAD_CLOUD": "1",
                "MUSNAD_RETRIEVAL_PIPELINE": "upgraded",
                "MUSNAD_DEMO_REPLAY": "0",
                "MUSNAD_USAGE_TABLE": usage_table.table_name,
                "MUSNAD_DAILY_CAP": str(cfg.daily_cap),
                "MUSNAD_SESSION_LIMIT": str(cfg.session_limit),
                "MUSNAD_IP_HOURLY_LIMIT": str(cfg.ip_hourly_limit),
                "GOOGLE_CLOUD_PROJECT": cfg.gcp_project,
                "GOOGLE_CLOUD_LOCATION": cfg.gcp_location,
            },
            secrets={
                "GCP_SERVICE_ACCOUNT_JSON": ecs.Secret.from_secrets_manager(gcp_secret),
            },
            health_check=ecs.HealthCheck(
                command=[
                    "CMD-SHELL",
                    "python -c \"import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4).status == 200 else 1)\"",
                ],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(30),
            ),
        )
        container.add_port_mappings(
            ecs.PortMapping(container_port=8501, protocol=ecs.Protocol.TCP)
        )

        fargate_service = ecs.FargateService(
            self,
            "MusnadService",
            cluster=cluster,
            task_definition=task_def,
            desired_count=cfg.desired_count,
            assign_public_ip=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            health_check_grace_period=Duration.seconds(90),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),
        )

        # ALB + TargetGroup with Streamlit health check and WebSocket sticky sessions
        alb = elbv2.ApplicationLoadBalancer(
            self,
            "MusnadAlb",
            vpc=vpc,
            internet_facing=True,
            idle_timeout=Duration.seconds(300),
        )

        target_group = elbv2.ApplicationTargetGroup(
            self,
            "MusnadTargetGroup",
            vpc=vpc,
            port=8501,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            deregistration_delay=Duration.seconds(15),
            stickiness_cookie_duration=Duration.days(1),
            health_check=elbv2.HealthCheck(
                path="/_stcore/health",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
                healthy_http_codes="200",
            ),
        )
        fargate_service.attach_to_application_target_group(target_group)

        if cfg.certificate_arn:
            alb.add_listener(
                "HttpsListener",
                port=443,
                protocol=elbv2.ApplicationProtocol.HTTPS,
                certificates=[elbv2.ListenerCertificate.from_arn(cfg.certificate_arn)],
                ssl_policy=elbv2.SslPolicy.RECOMMENDED_TLS,
                default_action=elbv2.ListenerAction.forward([target_group]),
            )
            alb.add_listener(
                "HttpRedirectListener",
                port=80,
                protocol=elbv2.ApplicationProtocol.HTTP,
                default_action=elbv2.ListenerAction.redirect(
                    protocol="HTTPS",
                    port="443",
                    permanent=True,
                ),
            )
            public_url = (
                f"https://{cfg.domain_name}"
                if cfg.domain_name
                else f"https://{alb.load_balancer_dns_name}"
            )
        else:
            alb.add_listener(
                "HttpListener",
                port=80,
                protocol=elbv2.ApplicationProtocol.HTTP,
                default_action=elbv2.ListenerAction.forward([target_group]),
            )
            public_url = f"http://{alb.load_balancer_dns_name}"

        # AWS Budgets monthly cost alarm (80% actual & 100% forecasted)
        budgets.CfnBudget(
            self,
            "MusnadMonthlyBudget",
            budget=budgets.CfnBudget.BudgetDataProperty(
                budget_name="musnad-demo-monthly-budget",
                budget_type="COST",
                time_unit="MONTHLY",
                budget_limit=budgets.CfnBudget.SpendProperty(
                    amount=cfg.monthly_budget_usd,
                    unit="USD",
                ),
            ),
            notifications_with_subscribers=[
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type="ACTUAL",
                        threshold=80,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[
                        budgets.CfnBudget.SubscriberProperty(
                            subscription_type="EMAIL",
                            address=budget_email_param.value_as_string,
                        )
                    ],
                ),
                budgets.CfnBudget.NotificationWithSubscribersProperty(
                    notification=budgets.CfnBudget.NotificationProperty(
                        comparison_operator="GREATER_THAN",
                        notification_type="FORECASTED",
                        threshold=100,
                        threshold_type="PERCENTAGE",
                    ),
                    subscribers=[
                        budgets.CfnBudget.SubscriberProperty(
                            subscription_type="EMAIL",
                            address=budget_email_param.value_as_string,
                        )
                    ],
                ),
            ],
        )

        self.vpc = vpc
        self.ecr_repo = ecr_repo
        self.log_group = log_group
        self.gcp_secret = gcp_secret
        self.usage_table = usage_table
        self.cluster = cluster
        self.task_definition = task_def
        self.fargate_service = fargate_service
        self.alb = alb
        self.target_group = target_group

        CfnOutput(self, "ServiceUrl", value=public_url)
        CfnOutput(self, "AlbDnsName", value=alb.load_balancer_dns_name)
        CfnOutput(self, "EcrRepositoryUri", value=ecr_repo.repository_uri)
        CfnOutput(self, "EcsClusterName", value=cluster.cluster_name)
        CfnOutput(self, "EcsServiceName", value=fargate_service.service_name)
        CfnOutput(self, "GcpSecretArn", value=gcp_secret.secret_arn)
        CfnOutput(self, "UsageTableName", value=usage_table.table_name)
        CfnOutput(self, "LogGroupName", value=log_group.log_group_name)
