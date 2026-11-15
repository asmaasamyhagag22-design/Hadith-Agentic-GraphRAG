# Deploying Musnad on AWS (ECS Fargate + ALB) and GCP Vertex AI

This runbook deploys the slim cloud container (`Dockerfile`, `MUSNAD_CLOUD=1`) defined in [`infra/`](../infra/) behind an AWS Application Load Balancer with WebSocket stickiness, backed by AWS Secrets Manager, DynamoDB usage caps, CloudWatch Logs, AWS Budgets, and a least-privilege Google Cloud service account for Vertex AI.

Every step below is labeled **`[Terminal]`** or **`[Console]`** so you know where to run it.

---

## 1. Prerequisites

### Terminal tools (`[Terminal]`)
- **AWS CLI v2** configured with deployment permissions (`aws sts get-caller-identity` succeeds).
- **Docker Engine** (`docker --version`) able to build `linux/amd64` images.
- **Node.js (v20/v22/v24 LTS) & AWS CDK CLI**:
  ```bash
  node --version
  npx aws-cdk --version   # or: npm install -g aws-cdk && cdk --version
  ```
- **uv** (`uv --version`) and local Python environment (`uv sync --frozen`).
- **Google Cloud SDK (`gcloud`)** optional if you create the GCP service account in the browser console.

Verify prerequisites and inspect local CDK synthesis cleanly before touching AWS:
```bash
aws sts get-caller-identity
uv run pytest tests/test_infra_cdk.py tests/test_usage_guard.py
```

---

## 2. GCP Setup (Vertex AI + Budget Alert)

Never give the demo service account `Owner`, `Editor`, GCS, or BigQuery roles. Use a dedicated service account scoped exclusively to Vertex AI inference.

1. **`[Console]` Enable Vertex AI API**
   - Google Cloud Console -> select your project -> **APIs & Services -> Library** -> enable **Vertex AI API** (`aiplatform.googleapis.com`).
2. **`[Console]` Create a least-privilege Service Account** (or run `gcloud` below)
   - Google Cloud Console -> **IAM & Admin -> Service Accounts -> Create Service Account**
   - Name: `musnad-demo-vertex`
   - Role: **`Vertex AI User`** (`roles/aiplatform.user`) **only**
   - Open the created service account -> **Keys -> Add Key -> Create new key -> JSON**. Save it temporarily outside the repository (e.g. `~/musnad-sa-tmp.json`, NEVER inside the git repo).

   *Equivalent `[Terminal]` option (`gcloud`):*
   ```bash
   export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
   gcloud services enable aiplatform.googleapis.com --project="$GOOGLE_CLOUD_PROJECT"
   gcloud iam service-accounts create musnad-demo-vertex \
     --display-name="Musnad Demo Vertex AI User" \
     --project="$GOOGLE_CLOUD_PROJECT"
   gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
     --member="serviceAccount:musnad-demo-vertex@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com" \
     --role="roles/aiplatform.user"
   gcloud iam service-accounts keys create ~/musnad-sa-tmp.json \
     --iam-account="musnad-demo-vertex@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
   ```
3. **`[Console]` Create a GCP Billing Budget Alert**
   - Google Cloud Console -> **Billing -> Budgets & alerts -> Create budget**
   - Scope to your GCP project (and optionally filter to Vertex AI services).
   - Set email alerts at e.g. 50%, 80%, and 100% of your monthly cap.
   - Note: GCP billing budgets send email alerts and do not halt API traffic automatically; `app/usage_guard.py` enforces `MUSNAD_DAILY_CAP` (default `200`), `MUSNAD_SESSION_LIMIT` (`10`), and `MUSNAD_IP_HOURLY_LIMIT` (`20`) and switches smoothly to offline Replay mode once hit.

---

## 3. Initial AWS Deployment (Ordered Steps)

Export your deployment variables once in your shell (`[Terminal]`):
```bash
export AWS_REGION="us-east-1"   # or preferred region
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export CDK_DEFAULT_ACCOUNT="$AWS_ACCOUNT_ID"
export CDK_DEFAULT_REGION="$AWS_REGION"
export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
export BUDGET_EMAIL="you@example.com"
```

### Step 3.1 — `[Terminal]` Bootstrap CDK (once per AWS account + region)
```bash
cd infra
npx aws-cdk bootstrap "aws://${AWS_ACCOUNT_ID}/${AWS_REGION}"
```

### Step 3.2 — `[Terminal]` Provision base resources first (`desired_count=0`)
Creating ECR, Secrets Manager, DynamoDB, VPC, ALB, and Budgets with `desired_count=0` first avoids ECS pull/secret startup retries before the image and GCP secret exist.
```bash
cd infra
npx aws-cdk deploy \
  -c desired_count=0 \
  -c gcp_project="$GOOGLE_CLOUD_PROJECT" \
  -c gcp_location="$GOOGLE_CLOUD_LOCATION" \
  -c budget_email="$BUDGET_EMAIL" \
  -c monthly_budget_usd=50 \
  --parameters "BudgetEmail=${BUDGET_EMAIL}"
```
Note the stack outputs printed at the end (`EcrRepositoryUri`, `EcsClusterName`, `EcsServiceName`, `GcpSecretArn`, `ServiceUrl`, `LogGroupName`).

### Step 3.3 — `[Terminal]` Build & push the cloud image to ECR
From the **repository root**:
```bash
export ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/musnad-demo"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Normal checkout (real data/processed directory):
docker build --platform linux/amd64 -t musnad-demo:latest .

# Optional: if building directly from a symlinked worktree where data/processed is a symlink:
# tar -chf - --exclude='__pycache__' --exclude='*.pyc' --exclude='.env*' --exclude='*service-account*.json' \
#   pyproject.toml uv.lock .dockerignore Dockerfile app src \
#   data/demo/recorded_runs.json \
#   data/processed/vectors_matn_gemini001_3072.npy \
#   data/processed/chunk_ids_matn.json \
#   data/processed/muslim_chunks.json \
#   data/processed/sanad_graph.sqlite \
#   | docker build --platform linux/amd64 -t musnad-demo:latest -

docker tag musnad-demo:latest "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"
```

### Step 3.4 — `[Terminal]` Store the GCP key in AWS Secrets Manager & shred local copy
```bash
aws secretsmanager put-secret-value \
  --region "$AWS_REGION" \
  --secret-id "musnad/gcp-service-account" \
  --secret-string "file://${HOME}/musnad-sa-tmp.json"

shred -u ~/musnad-sa-tmp.json 2>/dev/null || rm -f ~/musnad-sa-tmp.json
```

### Step 3.5 — `[Terminal]` Scale ECS Fargate service up (`desired_count=1`)
**HTTP only (default, no custom domain/cert needed):**
```bash
cd infra
npx aws-cdk deploy \
  -c desired_count=1 \
  -c gcp_project="$GOOGLE_CLOUD_PROJECT" \
  -c gcp_location="$GOOGLE_CLOUD_LOCATION" \
  -c budget_email="$BUDGET_EMAIL" \
  -c monthly_budget_usd=50 \
  --parameters "BudgetEmail=${BUDGET_EMAIL}"
```

**Optional HTTPS with ACM certificate (adds 443 listener + HTTP->HTTPS 301 redirect):**
First request or import an ACM certificate in the same AWS region (`$AWS_REGION`), validate DNS, then pass `certificate_arn` and `domain_name`, and point your DNS alias (`Route 53` / registrar CNAME) at `AlbDnsName`:
```bash
cd infra
npx aws-cdk deploy \
  -c desired_count=1 \
  -c gcp_project="$GOOGLE_CLOUD_PROJECT" \
  -c gcp_location="$GOOGLE_CLOUD_LOCATION" \
  -c certificate_arn="arn:aws:acm:${AWS_REGION}:${AWS_ACCOUNT_ID}:certificate/YOUR_CERT_ID" \
  -c domain_name="musnad.yourdomain.com" \
  -c budget_email="$BUDGET_EMAIL" \
  --parameters "BudgetEmail=${BUDGET_EMAIL}"
```

Optional runtime sizing or quota overrides can also be passed via `-c cpu=1024 -c memory_limit_mib=2048 -c daily_cap=200 -c session_limit=10 -c ip_hourly_limit=20`.

---

## 4. Browser / Console Verification (`[Console]`)

1. **Confirm AWS Budgets Email Subscription (`[Console]` / Inbox)**:
   - Open the email sent to `$BUDGET_EMAIL` (`AWS Notification - Subscription Confirmation`) and click **Confirm subscription**. Without clicking the confirmation link, budget alerts remain `Pending confirmation`.
   - You can also inspect **AWS Billing and Cost Management -> Budgets -> `musnad-demo-monthly-budget`** to verify alert status (`80% ACTUAL` & `100% FORECASTED`).
2. **Check ECS Task & ALB Health (`[Console]`)**:
   - **ECS -> Clusters -> `MusnadCluster` -> Service**: verify Running count is `1/1`.
   - **EC2 -> Load Balancers / Target Groups**: verify the target on port `8501` reports **`healthy`** via `/_stcore/health`, and check Target group attributes show `stickiness.enabled = true` (`lb_cookie`).
3. **Inspect Application Logs (`[Console]` or `[Terminal]`)**:
   - Console: **CloudWatch -> Log groups -> `/ecs/musnad-demo`** (14-day retention).
   - Terminal: `aws logs tail /ecs/musnad-demo --follow --region "$AWS_REGION"`.
4. **Open Live Demo & Update README (`[Console]`)**:
   - Visit the `ServiceUrl` output from `cdk deploy` in a browser and test one question + verify the trace streams cleanly.
   - Copy `ServiceUrl` into the `Live demo` link in `README.md`.

---

## 5. Updating the Deployed Image

Whenever you update app code or data and want to roll a new container (`[Terminal]`):
```bash
export ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/musnad-demo"
docker build --platform linux/amd64 -t musnad-demo:latest .
docker tag musnad-demo:latest "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"

aws ecs update-service \
  --region "$AWS_REGION" \
  --cluster "<EcsClusterName-from-stack-output>" \
  --service "<EcsServiceName-from-stack-output>" \
  --force-new-deployment
```

---

## 6. Teardown After the Job Fair (`[Terminal]` + `[Console]`)

All stateful demo resources (`MusnadRepository` with `empty_on_delete=True`, `MusnadLogGroup`, `GcpServiceAccountSecret`, `MusnadUsageTable`, and `MusnadVpc`) are configured with `RemovalPolicy.DESTROY`.

1. **`[Terminal]` Destroy the stack cleanly**:
   ```bash
   cd infra
   npx aws-cdk destroy
   ```
   *(If you created an optional `musnad-sa-tmp.json` / GCP service account exclusively for the demo, optionally disable or delete the GCP SA key in **GCP IAM & Admin -> Service Accounts -> Keys**).*
2. **`[Console]` Double-check zero dangling billable resources**:
   - **EC2 -> Load Balancers**: confirm the Musnad ALB is deleted.
   - **ECS -> Clusters**: confirm no running Fargate tasks remain.
   - **ECR -> Repositories**: confirm `musnad-demo` is deleted.

---

## 7. Cost Drivers (No Invented Prices — Check Current Regional Pricing)

Consult the official AWS Pricing Calculator and Google Cloud Vertex AI Pricing pages for current rates in your chosen region (`us-east-1` is typically lowest):

- **Fixed / Hourly AWS Infrastructure (running continuously while `desired_count=1`)**:
  - **Application Load Balancer**: base hourly runtime charge + LCU usage. *(Stopped only on `cdk destroy`.)*
  - **ECS Fargate compute**: per-vCPU-hour + per-GB-RAM-hour for `0.5 vCPU / 1 GB` (`desired_count=1`). *(Scaling `desired_count=0` pauses Fargate compute billing while preserving ALB/ECR; `0` NAT Gateways saves the entire hourly NAT Gateway charge.)*
- **Near-Zero / Usage-Driven AWS Resources**:
  - **DynamoDB (`PAY_PER_REQUEST`)**: per-read/write request only when users query; `$0` request charges when idle; old rows auto-expire via TTL (`expires_at`).
  - **ECR / CloudWatch Logs / Secrets Manager**: tiny container registry storage (~300 MB compressed, capped at 5 images via lifecycle rule), 14-day log ingestion/retention, and 1 active secret.
- **Variable GCP Vertex AI Cost (Per Live Question)**:
  - Each uncached live text question triggers HyDE generation (`gemini-2.5-flash`), embedding (`gemini-embedding-001`), and answer generation (`gemini-2.5-pro`); agentic chain queries add multi-turn tool calls.
  - Hard-capped at container runtime by `MUSNAD_DAILY_CAP=200`, `MUSNAD_SESSION_LIMIT=10`, and `MUSNAD_IP_HOURLY_LIMIT=20` before auto-falling back to Replay mode (`0` API calls).

---

## 8. Security Checklist

- [ ] `.env` and `*service-account*.json` remain git-ignored and excluded by `.dockerignore`.
- [ ] `docker history musnad-demo:latest` inspected — zero secrets baked into layers.
- [ ] Container runs as unprivileged user `musnad` (`uid=999`) with slim `cloud` dependency profile (`0` local heavy model packages).
- [ ] GCP service account holds **only** `Vertex AI User` (`roles/aiplatform.user`), stored **only** in AWS Secrets Manager (`musnad/gcp-service-account`), with local temp key file deleted immediately after upload.
- [ ] ECS TaskRole granted least-privilege access strictly to the single DynamoDB counter table ARN (`GetItem`, `PutItem`, `UpdateItem`) and single Secrets Manager secret ARN (`GetSecretValue`, `DescribeSecret`).
- [ ] Only the ALB accepts public HTTP/HTTPS traffic; ECS task security group allows port `8501` exclusively from the ALB security group.
- [ ] `MUSNAD_DAILY_CAP`, `MUSNAD_SESSION_LIMIT`, `MUSNAD_IP_HOURLY_LIMIT`, AWS Budgets email alert, and GCP billing budget alert are all active.
