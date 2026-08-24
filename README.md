# FastAPI AI Agent — Full Tutorial Series

A step-by-step series for building, evaluating, and deploying an AI agent using FastAPI, LangGraph, and AWS.

---

## What this series covers

| Branch | Tutorial | What you build |
|---|---|---|
| `fastapi-docker` | FastAPI + Agent + Docker | FastAPI app serving a LangGraph agent, containerized with Docker |
| `evals` | LangSmith Evals | LLM-as-judge evaluation suite with dataset management and tracing |
| `ci-cd` | CI/CD to Render | GitHub Actions pipeline with an evals gate before deployment |
| `ecs-deploy` | Deploy to AWS ECS | Push Docker image to ECR and deploy on ECS Fargate |

Follow the branches in order — each one builds on the previous.

---

## Stack

- **FastAPI** — API framework
- **LangGraph + LangChain Google GenAI** — agent with tool-calling
- **Docker** — containerization
- **LangSmith** — evaluation and tracing
- **GitHub Actions** — CI/CD pipeline
- **Render** — cloud deployment (CI/CD branch)
- **AWS ECR + ECS Fargate** — production deployment

---

## Branch 1: `fastapi-docker` — FastAPI + Agent + Docker

Full tutorial: [`fastapi_agent_tutorial.md`](fastapi_agent_tutorial.md)

### What you build
- A basic FastAPI app with GET/POST endpoints
- A LangGraph agent (Gemini + weather tool) served via `/chat`
- Dockerized with proper port mapping and secret handling

### Quick start

```bash
git checkout fastapi-docker
python -m venv venv
venv\Scripts\activate        # Windows
pip install fastapi "uvicorn[standard]" langgraph langchain-google-genai langchain-core python-dotenv
```

Create `.env`:
```
GOOGLE_API_KEY=your_key_here
```

Run locally:
```bash
uvicorn main:app --reload
```

Build and run with Docker:
```bash
docker build -t fastapi-agent .
docker run -d -p 8000:8000 --env-file .env --name agent-container fastapi-agent
```

Test:
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Current weather in Bangalore"}'
```

### File structure
```
fastapi-agent-tutorial/
├── main.py
├── agent.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
└── .env
```

---

## Branch 2: `evals` — LangSmith Evals

Full tutorial: [`langsmith_evals_tutorial.md`](langsmith_evals_tutorial.md)

### What you build
- A second tool (`get_currency_rate`) added to the agent
- A LangSmith dataset with 5 examples covering both tools
- 3 LLM-as-judge evaluators: correctness, tone, currency accuracy
- A single `evals.py` script that runs everything and prints results

### Quick start

```bash
git checkout evals
pip install -r requirements.txt
```

Add to `.env`:
```
LANGSMITH_API_KEY=ls__your_key_here
LANGSMITH_PROJECT=fastapi-agent-tutorial
LANGCHAIN_TRACING_V2=true
```

Run evals:
```bash
python evals.py
```

### Key concepts

| Concept | What it is |
|---|---|
| Dataset | Named collection of (input, expected output) pairs in LangSmith |
| Target function | Wraps your agent — LangSmith calls it once per example |
| LLM-as-judge | A second LLM that scores the reply semantically |
| `score: None` | Evaluator skipped for that example — not a failure |
| Experiment | One full `evaluate()` run, timestamped and comparable in the UI |

### File structure added
```
fastapi-agent-tutorial/
└── evals.py
```

---

## Branch 3: `ci-cd` — CI/CD to Render

Full tutorial: [`cicd_render_tutorial.md`](cicd_render_tutorial.md)

### What you build
- GitHub Actions workflow that runs evals on every push
- An eval gate (`sys.exit(1)` if pass rate < 80%) that blocks deployment on failure
- Automatic deploy to Render only when evals pass

### Pipeline flow

```
git push origin ci-cd
        │
        ▼
GitHub Actions runs evals.py
        │
   pass rate ≥ 80%?
   ├── NO  → deploy blocked ❌
   └── YES → Render deploys automatically ✅
```

### GitHub secrets required

| Secret | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Google AI API key |
| `LANGSMITH_API_KEY` | Your LangSmith API key |
| `RENDER_DEPLOY_HOOK_URL` | From Render service → Settings → Deploy Hook |

### File structure added
```
fastapi-agent-tutorial/
└── .github/
    └── workflows/
        └── deploy.yml
```

---

## Branch 4: `ecs-deploy` — Deploy to AWS ECS

Full tutorial: [`ecs_deployment_tutorial.md`](ecs_deployment_tutorial.md)

### What you build
- A production-hardened Dockerfile (non-root user, health check, multiple workers)
- Docker image pushed to Amazon ECR
- ECS Fargate task definition and service configuration

### Prerequisites
- AWS account with CLI configured
- Docker running locally

Verify:
```bash
aws --version && docker --version && aws sts get-caller-identity
```

### Steps

```bash
# 1. Create ECR repo
aws ecr create-repository --repository-name fastapi-agent --region us-east-1

# 2. Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  <account_id>.dkr.ecr.us-east-1.amazonaws.com

# 3. Build, tag, push
docker build -t fastapi-agent .
docker tag fastapi-agent:latest <account_id>.dkr.ecr.us-east-1.amazonaws.com/fastapi-agent:latest
docker push <account_id>.dkr.ecr.us-east-1.amazonaws.com/fastapi-agent:latest
```

### ECS task sizing (Fargate)

| Field | Value |
|---|---|
| CPU | 0.25 vCPU (256) |
| Memory | 512 MB |
| Container port | 8000 |

---

## Prerequisites (all branches)

- Python 3.11+
- Docker Desktop
- VS Code
- Postman (for testing)
- Google AI Studio API key
- LangSmith account (free tier) — needed from branch 2 onwards
- GitHub account
- Render account — needed for branch 3
- AWS account with CLI configured — needed for branch 4
