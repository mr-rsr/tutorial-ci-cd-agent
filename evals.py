import os
from dotenv import load_dotenv
from langsmith import Client, evaluate
from langsmith.schemas import Run, Example
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from agent import run_agent

load_dotenv()

client = Client()

judge = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.environ["GOOGLE_API_KEY"],
)

DATASET_NAME = "weather-agent-evals"

# --- Dataset examples ---
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


def create_dataset():
    """Create dataset in LangSmith if it doesn't exist."""
    existing = [d.name for d in client.list_datasets()]
    if DATASET_NAME in existing:
        print(f"Dataset '{DATASET_NAME}' already exists, skipping creation.")
        return client.read_dataset(dataset_name=DATASET_NAME)

    dataset = client.create_dataset(DATASET_NAME, description="Weather agent eval set")
    client.create_examples(
        inputs=[e["inputs"] for e in examples],
        outputs=[e["outputs"] for e in examples],
        dataset_id=dataset.id,
    )
    print(f"Dataset '{DATASET_NAME}' created with {len(examples)} examples.")
    return dataset


# --- Target function ---
def agent_target(inputs: dict) -> dict:
    reply = run_agent(inputs["message"])
    return {"reply": reply}


# --- LLM judge helper ---
def llm_judge(prompt: str) -> int:
    response = judge.invoke([HumanMessage(content=prompt)])
    return 1 if response.content.strip().lower().startswith("yes") else 0


# --- LLM-as-judge evaluators ---
def currency_evaluator(run: Run, example: Example) -> dict:
    """Judge whether the reply correctly states the expected exchange rate."""
    expected_tool = (example.outputs or {}).get("expected_tool", "")
    if expected_tool != "get_currency_rate":
        return {"key": "currency_accuracy", "score": None}  # skip for non-currency examples

    reply: str = (run.outputs or {}).get("reply", "")
    question: str = (example.inputs or {}).get("message", "")
    expected_rate: str = (example.outputs or {}).get("expected_rate", "")

    prompt = f"""You are evaluating an AI currency assistant.

User question: {question}
Expected rate in the reply: {expected_rate}
Agent reply: {reply}

Does the reply mention the correct exchange rate ({expected_rate}) clearly and accurately?
Answer with only 'yes' or 'no'."""

    return {"key": "currency_accuracy", "score": llm_judge(prompt)}


def correctness_evaluator(run: Run, example: Example) -> dict:
    """Judge whether the reply correctly answers the weather question for the right city."""
    reply: str = (run.outputs or {}).get("reply", "")
    question: str = (example.inputs or {}).get("message", "")
    expected_city: str = (example.outputs or {}).get("expected_city", "")

    prompt = f"""You are evaluating an AI weather assistant.

User question: {question}
Expected city: {expected_city}
Agent reply: {reply}

Does the reply correctly provide weather information specifically for {expected_city}?
Answer with only 'yes' or 'no'."""

    return {"key": "correctness", "score": llm_judge(prompt)}


def tone_evaluator(run: Run, example: Example) -> dict:
    """Judge whether the reply is clear, helpful, and conversational."""
    reply: str = (run.outputs or {}).get("reply", "")

    prompt = f"""You are evaluating the quality of an AI assistant's response.

Agent reply: {reply}

Is this reply clear, helpful, and written in a natural conversational tone?
A raw Python dict, an error message, or a one-word answer should be marked 'no'.
Answer with only 'yes' or 'no'."""

    return {"key": "tone", "score": llm_judge(prompt)}


if __name__ == "__main__":
    create_dataset()

    results = evaluate(
        agent_target,
        data=DATASET_NAME,
        evaluators=[correctness_evaluator, tone_evaluator, currency_evaluator],
        experiment_prefix="weather-agent",
        metadata={"model": "gemini-2.5-flash"},
    )

    print("\n=== Eval Results ===")
    for r in results:
        msg = r["run"].inputs.get("message", "")
        reply = (r["run"].outputs or {}).get("reply", "")
        scores = {res.key: res.score for res in r["evaluation_results"]["results"]}
        print(f"Input  : {msg}")
        print(f"Reply  : {reply}")
        for key, score in scores.items():
            print(f"  {key}: {score}")
        print()
