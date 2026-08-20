# CI/CD to Render with LangSmith Evals Gate — Step-by-Step Tutorial

Stack: GitHub Actions (CI/CD) + LangSmith evals (quality gate) + Render (deployment).

Every push to the `ci-cd` branch:
1. Runs `evals.py` — LLM-as-judge scores the agent against the dataset
2. If evals pass → triggers a Render deploy automatically
3. If evals fail → deploy is blocked, results visible in LangSmith UI

---

## Step 1: Deploy the app on Render (first time, manual)

Before automating, you need a live service on Render to deploy to.

1. Go to [render.com](https://render.com) and sign in
2. Click **New** → **Web Service**
3. Connect your GitHub repo (`tutorial-ci-cd-agent`)
4. Fill in the settings:
   - **Branch**: `ci-cd`
   - **Runtime**: Docker
   - **Region**: pick the closest one
5. Under **Environment Variables**, add:
   ```
   GOOGLE_API_KEY=your_actual_key
   ```
6. Click **Deploy** — Render builds the Docker image and starts the service
7. Once live, copy the public URL (e.g. `https://fastapi-agent-xxxx.onrender.com`)

Test it:
```bash
curl -X POST https://fastapi-agent-xxxx.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in Mumbai"}'
```

---

## Step 2: Get the Render Deploy Hook URL

This is the URL GitHub Actions will call to trigger a redeploy.

1. In Render, open your service → **Settings** → **Deploy Hook**
2. Click **Generate Deploy Hook**
3. Copy the URL — it looks like:
   ```
   https://api.render.com/deploy/srv-xxxx?key=yyyy
   ```

---

## Step 3: Add secrets to GitHub

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 3 secrets:

| Secret name | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Google AI API key |
| `LANGSMITH_API_KEY` | Your LangSmith API key |
| `RENDER_DEPLOY_HOOK_URL` | The deploy hook URL from Step 2 |

These are injected into the workflow at runtime — never stored in code.

---

## Step 4: Understand the workflow (`.github/workflows/deploy.yml`)

```yaml
on:
  push:
    branches:
      - ci-cd
```

Triggers only on pushes to the `ci-cd` branch.

### Job 1: `evals`

```yaml
- name: Run evals
  env:
    GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
    LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
    LANGSMITH_PROJECT: fastapi-agent-tutorial
    LANGCHAIN_TRACING_V2: "true"
  run: python evals.py
```

- Installs dependencies, runs `evals.py`
- `evals.py` calls the agent on all 5 dataset examples and scores them with the LLM judge
- If `evals.py` exits with a non-zero code (any exception), the job fails and deploy is blocked
- All runs are logged to LangSmith automatically via `LANGCHAIN_TRACING_V2=true`

### Job 2: `deploy`

```yaml
deploy:
  needs: evals
```

- `needs: evals` means this job only runs if the `evals` job succeeds
- Calls the Render deploy hook URL with a simple `curl POST`
- Render picks up the latest code and rebuilds the Docker image

---

## Step 5: Push to trigger the pipeline

```bash
git add .
git commit -m "add ci/cd workflow with evals gate"
git push origin ci-cd
```

Then go to your GitHub repo → **Actions** tab. You'll see the workflow running with two jobs:

```
CI/CD to Render
├── evals     ← running evals.py, logging to LangSmith
└── deploy    ← triggers Render only if evals passed
```

---

## Step 6: Check results

**GitHub Actions:**
- Green `evals` job → evals passed, deploy triggered
- Red `evals` job → something failed, check the logs, deploy was blocked

**LangSmith UI:**
- Go to [smith.langchain.com](https://smith.langchain.com) → project **fastapi-agent-tutorial**
- Every CI run creates a new experiment `weather-agent-<timestamp>`
- Compare scores across runs to track agent quality over time

**Render:**
- Go to your Render service → **Events** tab
- You'll see a new deploy triggered by the webhook after evals passed

---

## The full flow on every push

```
git push origin ci-cd
        │
        ▼
GitHub Actions: install deps
        │
        ▼
python evals.py
  ├── runs agent on 5 examples
  ├── LLM judge scores correctness + tone + currency_accuracy
  └── logs experiment to LangSmith
        │
   pass?
   ├── NO  → workflow fails, deploy blocked, fix the agent
   └── YES
        │
        ▼
curl Render deploy hook
        │
        ▼
Render rebuilds Docker image → live at your URL
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `evals` job fails with auth error | Check `GOOGLE_API_KEY` and `LANGSMITH_API_KEY` secrets are set correctly in GitHub |
| `deploy` job never runs | `evals` job failed — check Actions logs for the actual error |
| Render deploy not triggered | Check `RENDER_DEPLOY_HOOK_URL` secret — paste it in browser to test manually |
| Evals pass but agent is wrong | Lower the bar isn't the fix — check the LangSmith trace to see what the agent actually returned |

---

## File structure

```
fastapi-agent-tutorial/
├── .github/
│   └── workflows/
│       └── deploy.yml     ← CI/CD pipeline
├── agent.py               ← get_weather + get_currency_rate
├── main.py
├── evals.py               ← quality gate
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
└── .env                   ← never committed, secrets via GitHub
```

---

## Branch learning path

| Branch | What it adds |
|---|---|
| `fastapi-docker` | FastAPI + LangGraph agent + Docker |
| `evals` | LangSmith dataset + LLM-as-judge evaluators |
| `ci-cd` | GitHub Actions pipeline — evals gate + Render auto-deploy |
