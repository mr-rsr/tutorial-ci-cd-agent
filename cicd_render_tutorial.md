# CI/CD to Render with LangSmith Evals Gate — Step-by-Step Tutorial

Stack: GitHub Actions (CI/CD) + LangSmith evals (quality gate) + Render (deployment).

Every push to the `ci-cd` branch:
1. Runs `evals.py` — LLM-as-judge scores the agent against the dataset
2. If pass rate ≥ 80% → triggers a Render deploy automatically
3. If pass rate < 80% → deploy is blocked, fix the agent and push again

---

## Branch learning path

| Branch | What it adds |
|---|---|
| `fastapi-docker` | FastAPI + LangGraph agent + Docker |
| `evals` | LangSmith dataset + LLM-as-judge evaluators |
| `ci-cd` | GitHub Actions pipeline — evals gate + Render auto-deploy |

Checkout each branch in order to follow along.

---

## Step 1: Create the Render service (one time only)

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

Test it manually:
```bash
curl -X POST https://fastapi-agent-xxxx.onrender.com/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Weather in Mumbai"}'
```

---

## Step 2: Get the Render Deploy Hook URL

This is the URL GitHub Actions calls to trigger a redeploy automatically.

1. In Render, open your service → **Settings**
2. Scroll down to **Deploy Hook**
3. Copy the URL — it looks like:
   ```
   https://api.render.com/deploy/srv-xxxx?key=yyyy
   ```

---

## Step 3: Add secrets to GitHub

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add these 3:

| Secret name | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Google AI API key |
| `LANGSMITH_API_KEY` | Your LangSmith API key |
| `RENDER_DEPLOY_HOOK_URL` | The deploy hook URL from Step 2 |

These are injected into the workflow at runtime — never stored in code or visible in logs.

---

## Step 4: Understand the workflow (`.github/workflows/deploy.yml`)

Triggers on every push to `ci-cd`:

```yaml
on:
  push:
    branches:
      - ci-cd
```

### Job 1: `evals`

Installs dependencies and runs `evals.py` with all secrets injected as env vars:

```yaml
- name: Run evals
  env:
    GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
    LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
    LANGSMITH_PROJECT: fastapi-agent-tutorial
    LANGCHAIN_TRACING_V2: "true"
  run: python evals.py
```

- Runs the agent on all 5 dataset examples
- LLM judge scores `correctness`, `tone`, `currency_accuracy` per example
- Calculates overall pass rate
- If pass rate < 80% → `sys.exit(1)` → job fails → deploy is blocked
- All runs logged to LangSmith automatically

### Job 2: `deploy`

```yaml
deploy:
  needs: evals
```

- Only runs if `evals` job succeeds
- Calls the Render deploy hook with a `curl POST`
- Render picks up the latest code and rebuilds the Docker image

---

## Step 5: Understand the eval gate in `evals.py`

```python
PASS_THRESHOLD = 0.8  # 80% of scored evals must pass

pass_rate = sum(all_scores) / len(all_scores)

if pass_rate < PASS_THRESHOLD:
    print("EVALS FAILED — deploy blocked.")
    sys.exit(1)

print("EVALS PASSED — deploy allowed.")
```

- `None` scores (currency evaluator skipping weather examples) are excluded from the calculation
- `sys.exit(1)` is what makes GitHub Actions mark the job as failed and skip deploy
- Adjust `PASS_THRESHOLD` at the top of `evals.py` to make the gate stricter or looser

---

## Step 6: Push to trigger the pipeline

```bash
git add .
git commit -m "your message"
git push origin ci-cd
```

Go to your GitHub repo → **Actions** tab. You'll see:

```
CI/CD to Render
├── evals     ← running evals.py, logging to LangSmith
└── deploy    ← triggers Render only if evals passed
```

---

## Step 7: Check results

**GitHub Actions:**
- Green `evals` + green `deploy` → evals passed, Render is deploying
- Red `evals` → evals failed, check the logs for pass rate and which examples failed

**LangSmith UI:**
- Go to [smith.langchain.com](https://smith.langchain.com) → project **fastapi-agent-tutorial**
- Every CI run creates a new experiment `weather-agent-<timestamp>`
- Click into it → per-example scores for `correctness`, `tone`, `currency_accuracy`
- Click any row → full LangGraph trace showing every node and tool call

**Render:**
- Go to your service → **Events** tab
- You'll see a new deploy triggered by the webhook after evals passed

---

## Full flow on every push

```
git push origin ci-cd
        │
        ▼
GitHub Actions: install deps
        │
        ▼
python evals.py
  ├── runs agent on 5 examples
  ├── LLM judge scores each reply
  ├── logs experiment to LangSmith
  └── calculates pass rate
        │
   pass rate ≥ 80%?
   ├── NO  → sys.exit(1) → workflow fails → deploy blocked ❌
   └── YES → workflow passes
                │
                ▼
        curl Render deploy hook
                │
                ▼
        Render rebuilds Docker image → live ✅
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `evals` job fails with API key error | Secret is missing or empty in GitHub — go to Settings → Secrets, delete and re-add it |
| `deploy` job never runs | `evals` job failed — check Actions logs for the pass rate and error |
| Render deploy not triggered | Verify `RENDER_DEPLOY_HOOK_URL` — paste it directly in the browser, it should return `{"id":"..."}` |
| Evals pass locally but fail in CI | Check that all 3 secrets are added in GitHub, not just locally in `.env` |
| Want to re-run without a new push | Actions tab → failed run → **Re-run jobs** → **Re-run all jobs** |

---

## File structure

```
fastapi-agent-tutorial/
├── .github/
│   └── workflows/
│       └── deploy.yml     ← CI/CD pipeline
├── agent.py               ← get_weather + get_currency_rate
├── main.py
├── evals.py               ← quality gate (sys.exit(1) on failure)
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
└── .env                   ← never committed, secrets live in GitHub
```
