#!/usr/bin/env python3
"""CDK app entrypoint for the Musnad ECS Fargate stack."""

from __future__ import annotations

import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from infra import ensure_node_for_jsii

ensure_node_for_jsii()

import aws_cdk as cdk
from infra.musnad_stack import MusnadStack, MusnadStackConfig


def _ctx_or_env(app: cdk.App, ctx_key: str, env_key: str, default: str | None = None) -> str | None:
    raw = app.node.try_get_context(ctx_key)
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip()
    env_val = os.getenv(env_key)
    if env_val is not None and env_val.strip() != "":
        return env_val.strip()
    return default


def main() -> None:
    app = cdk.App(outdir=os.getenv("CDK_OUTDIR", str(REPO_ROOT / "cdk.out")))

    stack_cfg = MusnadStackConfig(
        repository_name=_ctx_or_env(app, "repository_name", "MUSNAD_ECR_REPO", "musnad-demo") or "musnad-demo",
        image_tag=_ctx_or_env(app, "image_tag", "MUSNAD_IMAGE_TAG", "latest") or "latest",
        cpu=int(_ctx_or_env(app, "cpu", "MUSNAD_ECS_CPU", "512") or 512),
        memory_limit_mib=int(_ctx_or_env(app, "memory_limit_mib", "MUSNAD_ECS_MEMORY", "1024") or 1024),
        desired_count=int(_ctx_or_env(app, "desired_count", "MUSNAD_ECS_DESIRED_COUNT", "1") or 1),
        daily_cap=int(_ctx_or_env(app, "daily_cap", "MUSNAD_DAILY_CAP", "200") or 200),
        session_limit=int(_ctx_or_env(app, "session_limit", "MUSNAD_SESSION_LIMIT", "10") or 10),
        ip_hourly_limit=int(_ctx_or_env(app, "ip_hourly_limit", "MUSNAD_IP_HOURLY_LIMIT", "20") or 20),
        gcp_project=_ctx_or_env(app, "gcp_project", "GOOGLE_CLOUD_PROJECT", "") or "",
        gcp_location=_ctx_or_env(app, "gcp_location", "GOOGLE_CLOUD_LOCATION", "us-central1") or "us-central1",
        certificate_arn=_ctx_or_env(app, "certificate_arn", "MUSNAD_CERTIFICATE_ARN", None),
        domain_name=_ctx_or_env(app, "domain_name", "MUSNAD_DOMAIN_NAME", None),
        budget_email=_ctx_or_env(app, "budget_email", "MUSNAD_BUDGET_EMAIL", None),
        monthly_budget_usd=float(_ctx_or_env(app, "monthly_budget_usd", "MUSNAD_MONTHLY_BUDGET_USD", "50") or 50.0),
    )

    env = cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION", "us-east-1"),
    )
    MusnadStack(app, "MusnadDemoStack", config=stack_cfg, env=env)
    app.synth()


if __name__ == "__main__":
    main()
