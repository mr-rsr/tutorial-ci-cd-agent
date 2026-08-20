# Deploy Docker Image to AWS ECS

This picks up from the `ci-cd` branch. You already have the full pipeline — FastAPI agent, evals, and CI/CD to Render. This branch updates the Dockerfile for production and walks through pushing the image to Amazon ECR so you can deploy it on ECS.

---

## What changed in the Dockerfile

The original Dockerfile from `fastapi-docker` was fine for local dev and Render. For ECS, three things were added:

**Non-root user**
```dockerfile
RUN adduser --disabled-password --no-create-home appuser && \
    chown -R appuser:appuser /app
USER appuser
```
Containers run as root by default. ECS doesn't require it and running as root is a security risk — if the container is compromised, the attacker has root inside it.

**Health check**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"
```
ECS uses this to know when the container is healthy and ready to serve traffic. Without it, ECS has no way to detect a crashed app inside a running container. Uses `urllib` (stdlib) so no extra dependency needed.

**Multiple workers**
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```
2 workers means 2 processes handling requests. Each LLM call blocks a worker for the duration of the API call — a second worker keeps the service responsive while one is busy.

---

## Prerequisites

- AWS account
- AWS CLI installed and configured
- Docker running locally

Verify:
```bash
aws --version
docker --version
aws sts get-caller-identity
```

---

## Step 1: Create an ECR repository

```bash
aws ecr create-repository \
  --repository-name fastapi-agent \
  --region us-east-1
```

Copy the `repositoryUri` from the output:
```
123456789.dkr.ecr.us-east-1.amazonaws.com/fastapi-agent
```

---

## Step 2: Authenticate Docker to ECR

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789.dkr.ecr.us-east-1.amazonaws.com
```

You should see `Login Succeeded`.

---

## Step 3: Build the image

```bash
docker build -t fastapi-agent .
```

---

## Step 4: Tag the image with the ECR URI

```bash
docker tag fastapi-agent:latest \
  123456789.dkr.ecr.us-east-1.amazonaws.com/fastapi-agent:latest
```

---

## Step 5: Push to ECR

```bash
docker push \
  123456789.dkr.ecr.us-east-1.amazonaws.com/fastapi-agent:latest
```

Verify it's there:
```bash
aws ecr list-images --repository-name fastapi-agent --region us-east-1
```

---

## ECS configuration reference

When setting up ECS manually in the AWS console, use these values:

**Container settings**

| Field | Value |
|---|---|
| Image URI | `123456789.dkr.ecr.us-east-1.amazonaws.com/fastapi-agent:latest` |
| Container port | `8000` |
| Protocol | `TCP` |

**Task sizing (Fargate)**

| Field | Value |
|---|---|
| CPU | `0.25 vCPU` (256) |
| Memory | `512 MB` |

**Environment variables**

| Key | Value |
|---|---|
| `GOOGLE_API_KEY` | your actual key |

**Health check**

The Dockerfile already has `HEALTHCHECK` defined — ECS will pick it up automatically. If the console asks for a health check command explicitly:
```
CMD-SHELL, curl -f http://localhost:8000/ || exit 1
```

**Security group inbound rule**

| Type | Port | Source |
|---|---|---|
| Custom TCP | `8000` | `0.0.0.0/0` |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `no basic auth credentials` | Re-run the `get-login-password` command in Step 2 |
| `authorization token has expired` | ECR tokens expire after 12 hours — re-authenticate |
| `repository does not exist` | Region in the URI must match the region you created the repo in |
| Task fails health check | Check CloudWatch logs — likely the app crashed on startup due to missing `GOOGLE_API_KEY` env var in ECS |
| Permission denied writing files | Non-root user — make sure `chown` in Dockerfile covers all paths the app writes to |
