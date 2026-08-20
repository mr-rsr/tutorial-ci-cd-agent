# LangSmith Evals Integration — Step-by-Step Tutorial

Stack: FastAPI + LangGraph agent (Gemini) + LangSmith for dataset management, tracing, and LLM-as-judge evaluation.

---

## What you'll have at the end

- A second tool (`get_currency_rate`) added to the agent alongside `get_weather`
- A LangSmith dataset with 5 examples covering both tools
- 3 LLM-as-judge evaluators scoring correctness, tone, and currency accuracy
- A single script (`evals.py`) that runs everything and prints results
- Every agent run traced automatically in the LangSmith UI

---

## Step 1: Add a second tool to the agent

Open `agent.py`. The agent already has `get_weather`. Add `get_currency_rate` below it:

```python
@tool
def get_currency_rate(base: str, target: str) -> dict:
    """Return the exchange rate from base currency to target currency"""
    rates = {
        ("USD", "INR"): 83.5,
        ("INR", "USD"): 0.012,
        ("USD", "EUR"): 0.92,
        ("EUR", "USD"): 1.09,
        ("GBP", "INR"): 106.2,
        ("INR", "GBP"): 0.0094,
    }
    rate = rates.get((base.upper(), target.upper()))
    if rate is None:
        return {"status": "error", "message": f"Rate for {base}/{target} not available"}
    return {"status": "success", "base": base.upper(), "target": target.upper(), "rate": rate}
```

Then register it in the tools list:

```python
tools = [get_weather, get_currency_rate]
```

The agent now picks the right tool automatically based on the user's question — no other changes needed.

---

## Step 2: Get a LangSmith API key

1. Go to [smith.langchain.com](https://smith.langchain.com) and sign in (free tier is enough)
2. Click your avatar → **Settings** → **API Keys** → **Create API Key**
3. Copy the key — you only see it once

---

## Step 3: Add LangSmith env vars to `.env`

```
LANGSMITH_API_KEY=ls__xxxxxxxxxxxxxxxx
LANGSMITH_PROJECT=fastapi-agent-tutorial
LANGCHAIN_TRACING_V2=true
```

- `LANGCHAIN_TRACING_V2=true` — LangChain/LangGraph automatically sends every `graph.invoke` trace to LangSmith. No extra code needed in `agent.py`.
- `LANGSMITH_PROJECT` — groups all runs under one project in the UI.

---

## Step 4: Install dependencies

Make sure your venv is active:

```bash
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

Then install:

```bash
pip install -r requirements.txt
```

`langsmith` is already in `requirements.txt`. If you want to install it alone:

```bash
pip install langsmith
```

---

## Step 5: Understand `evals.py`

### 5.1 The dataset

5 examples covering both tools. Each example has `inputs` (what the agent receives) and `outputs` (ground truth for the evaluator):

```python
examples = [
    {
        "inputs": {"message": "What is the weather in Mumbai?"},
        "outputs": {"expected_city": "Mumbai", "expected_tool": "get_weather"},
    },
    {
        "inputs": {"message": "Tell me the weather in Delhi"},
        "outputs": {"expected_city": "Delhi", "expected_tool": "get_weather"},
    },
    {
        "inputs": {"message": "Weather in London please"},
        "outputs": {"expected_city": "London", "expected_tool": "get_weather"},
    },
    {
        "inputs": {"message": "What is the exchange rate from USD to INR?"},
        "outputs": {"expected_rate": "83.5", "expected_tool": "get_currency_rate"},
    },
    {
        "inputs": {"message": "How many euros do I get for 1 USD?"},
        "outputs": {"expected_rate": "0.92", "expected_tool": "get_currency_rate"},
    },
]
```

`create_dataset()` pushes this to LangSmith once and skips creation on subsequent runs.

### 5.2 Target function

```python
def agent_target(inputs: dict) -> dict:
    reply = run_agent(inputs["message"])
    return {"reply": reply}
```

LangSmith calls this once per example. It wraps `run_agent` and returns a dict that evaluators can read from `run.outputs`.

### 5.3 LLM judge helper

Instead of keyword/regex checks, a second Gemini instance reads the reply and scores it:

```python
judge = ChatGoogleGenerativeAI(model="gemini-2.5-flash", ...)

def llm_judge(prompt: str) -> int:
    response = judge.invoke([HumanMessage(content=prompt)])
    return 1 if response.content.strip().lower().startswith("yes") else 0
```

### 5.4 The 3 evaluators

**`correctness_evaluator`** — for weather examples, asks the judge: did the agent answer for the right city with actual weather info?

```python
def correctness_evaluator(run: Run, example: Example) -> dict:
    # prompt includes: question + expected_city + agent reply
    # judge answers yes/no → score 1/0
    return {"key": "correctness", "score": llm_judge(prompt)}
```

**`tone_evaluator`** — for all examples, asks the judge: is the reply clear, helpful, and conversational? A raw dict dump or error string scores 0.

```python
def tone_evaluator(run: Run, example: Example) -> dict:
    return {"key": "tone", "score": llm_judge(prompt)}
```

**`currency_evaluator`** — for currency examples only, asks the judge: does the reply mention the correct exchange rate? Returns `score: None` for weather examples so LangSmith treats them as not applicable rather than a failure.

```python
def currency_evaluator(run: Run, example: Example) -> dict:
    if expected_tool != "get_currency_rate":
        return {"key": "currency_accuracy", "score": None}  # skip
    # prompt includes: question + expected_rate + agent reply
    return {"key": "currency_accuracy", "score": llm_judge(prompt)}
```

### 5.5 The `evaluate()` call

```python
results = evaluate(
    agent_target,
    data=DATASET_NAME,
    evaluators=[correctness_evaluator, tone_evaluator, currency_evaluator],
    experiment_prefix="weather-agent",
    metadata={"model": "gemini-2.5-flash"},
)
```

- Runs `agent_target` on all 5 examples
- Runs all 3 evaluators on each (run, example) pair
- Logs everything to LangSmith as a new experiment named `weather-agent-<timestamp>`

---

## Step 6: Run the evals

```bash
python evals.py
```

Expected terminal output:

```
Dataset 'weather-agent-evals' created with 5 examples.

=== Eval Results ===
Input  : What is the weather in Mumbai?
Reply  : The current weather in Mumbai is cloudy.
  correctness: 1
  tone: 1
  currency_accuracy: None

Input  : Tell me the weather in Delhi
Reply  : The current weather in Delhi is cloudy.
  correctness: 1
  tone: 1
  currency_accuracy: None

Input  : Weather in London please
Reply  : The current weather in London is cloudy.
  correctness: 1
  tone: 1
  currency_accuracy: None

Input  : What is the exchange rate from USD to INR?
Reply  : The exchange rate from USD to INR is 83.5.
  correctness: 1
  tone: 1
  currency_accuracy: 1

Input  : How many euros do I get for 1 USD?
Reply  : For 1 USD, you get 0.92 euros.
  correctness: 1
  tone: 1
  currency_accuracy: 1
```

On the second run: `Dataset 'weather-agent-evals' already exists, skipping creation.` — dataset is reused, a new experiment is created.

---

## Step 7: Check results in LangSmith UI

1. Go to [smith.langchain.com](https://smith.langchain.com)
2. Open project **fastapi-agent-tutorial** from the left sidebar

**To see the dataset:**
- Click **Datasets & Testing** → **weather-agent-evals**
- All 5 examples are listed with their inputs and expected outputs

**To see eval scores:**
- Click the **Experiments** tab inside the dataset
- Each `python evals.py` run appears as a row named `weather-agent-<timestamp>`
- Click into it → table of all 5 examples with `correctness`, `tone`, `currency_accuracy` columns side by side
- Compare runs over time as you change the agent

**To see traces:**
- Click any individual example row inside an experiment
- Full LangGraph trace: every node (`chatbot` → `tools` → `chatbot`), the tool call with inputs/outputs, and all messages

---

## Troubleshooting

| Error | Fix |
|---|---|
| `AuthenticationError` | `LANGSMITH_API_KEY` is wrong or still the placeholder — regenerate in LangSmith settings |
| `GOOGLE_API_KEY` error | Test the agent alone: `python -c "from agent import run_agent; print(run_agent('weather in Mumbai'))"` |
| Dataset already exists error | That's expected on re-runs — the script skips creation automatically |
| `score: None` showing as failure | That's correct behaviour — `None` means the evaluator was skipped for that example, not a failure |
| Agent returns raw dict instead of text | The `run_agent` function reads `content[0]["text"]` — check the Gemini model name is valid |

---

## File structure

```
fastapi-agent-tutorial/
├── agent.py          ← get_weather + get_currency_rate tools
├── main.py
├── evals.py          ← dataset + 3 LLM-as-judge evaluators
├── requirements.txt  ← langsmith added
├── Dockerfile
├── .dockerignore
├── .gitignore
└── .env              ← GOOGLE_API_KEY + LANGSMITH_* vars
```

---

## Key concepts recap

| Concept | What it is |
|---|---|
| Dataset | Named collection of (input, expected output) pairs stored in LangSmith |
| Target function | Wraps your agent — LangSmith calls it once per example |
| LLM-as-judge | A second LLM that reads the reply and scores it — catches semantic failures regex can't |
| Evaluator | Function that takes `(run, example)` and returns a `key` + `score` |
| `score: None` | Tells LangSmith this evaluator doesn't apply to this example — not a failure |
| Experiment | One full `evaluate()` run — timestamped, comparable across runs in the UI |
| Tracing | Automatic when `LANGCHAIN_TRACING_V2=true` — every LangGraph node recorded |
