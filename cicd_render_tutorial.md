# CI/CD to Render with LangSmith Evals Gate

This picks up from the `evals` branch. You already have:
- A FastAPI + LangGraph agent running locally
- LangSmith evals with LLM-as-judge scoring the agent

This branch adds a GitHub Actions pipeline that runs those evals on every push and only deploys to Render if they pass.

---

## What you'll have at the end

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

---

## Step 1: Create the GitHub Actions workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: CI/CD to Render

on:
  push:
    branches:
      - ci-cd

jobs:
  evals:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run evals
        env:
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
          LANGSMITH_PROJECT: fastapi-agent-tutorial
          LANGCHAIN_TRACING_V2: "true"
        run: python evals.py

  deploy:
    needs: evals
    runs-on: ubuntu-latest

    steps:
      - name: Trigger Render deploy
        run: |
          curl -X POST "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
```

`needs: evals` is the gate — `deploy` only runs if `evals` succeeds.

---

## Step 2: Understand the eval gate in `evals.py`

The gate is already in `evals.py` from the previous branch:

```python
PASS_THRESHOLD = 0.8

pass_rate = sum(all_scores) / len(all_scores)

if pass_rate < PASS_THRESHOLD:
    print("EVALS FAILED — deploy blocked.")
    sys.exit(1)

print("EVALS PASSED — deploy allowed.")
```

`sys.exit(1)` makes GitHub Actions mark the `evals` job as failed, which prevents `deploy` from running. Adjust `PASS_THRESHOLD` to make the gate stricter or looser.

---

## Step 3: Create the Render service (one time)

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo (`tutorial-ci-cd-agent`)
3. Set:
   - **Branch**: `ci-cd`
   - **Runtime**: Docker
4. Under **Environment Variables** add:
   ```
   GOOGLE_API_KEY=your_actual_key
   ```
5. Click **Deploy** — Render builds the Docker image and starts the service
6. Once live, test it:
   ```bash
   curl -X POST https://fastapi-agent-xxxx.onrender.com/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Weather in Mumbai"}'
   ```

---

## Step 4: Get the Render Deploy Hook URL

1. In Render, open your service → **Settings**
2. Scroll down to **Deploy Hook**
3. Copy the URL:
   ```
   https://api.render.com/deploy/srv-xxxx?key=yyyy
   ```

This is what GitHub Actions calls to trigger a redeploy.

---

## Step 5: Add secrets to GitHub

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these 3:

| Secret name | Value |
|---|---|
| `GOOGLE_API_KEY` | Your Google AI API key |
| `LANGSMITH_API_KEY` | Your LangSmith API key |
| `RENDER_DEPLOY_HOOK_URL` | The deploy hook URL from Step 4 |

These are injected at runtime — never stored in code or visible in logs.

---

## Step 6: Push and watch it run

```bash
git add .
git commit -m "add ci/cd workflow with evals gate"
git push origin ci-cd
```

Go to your repo → **Actions** tab:

```
CI/CD to Render
├── evals     ← runs evals.py, logs to LangSmith
└── deploy    ← triggers Render only if evals passed
```

---

## Step 7: Check results

**GitHub Actions:**
- Green `evals` + green `deploy` → evals passed, Render is deploying
- Red `evals` → check the logs for pass rate and which examples failed, deploy was blocked

**LangSmith UI:**
- Go to [smith.langchain.com](https://smith.langchain.com) → project **fastapi-agent-tutorial**
- Every CI run creates a new experiment `weather-agent-<timestamp>`
- Click into it → per-example scores for `correctness`, `tone`, `currency_accuracy`
- Click any row → full LangGraph trace

**Render:**
- Go to your service → **Events** tab
- You'll see a new deploy triggered by the webhook after evals passed

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `API key required` error in evals job | Secret is missing or empty — go to GitHub Settings → Secrets, delete and re-add it |
| `deploy` job never runs | `evals` job failed — check Actions logs for the pass rate |
| Render deploy not triggered | Paste `RENDER_DEPLOY_HOOK_URL` directly in the browser — should return `{"id":"..."}` |
| Evals pass locally but fail in CI | All 3 secrets must be in GitHub, not just in local `.env` |
| Want to re-run without a new push | Actions tab → failed run → **Re-run jobs** → **Re-run all jobs** |

---

## File structure added in this branch

```
fastapi-agent-tutorial/
├── .github/
│   └── workflows/
│       └── deploy.yml     ← CI/CD pipeline
└── evals.py               ← now has sys.exit(1) gate
```
