# FastAPI + AI Agent + Docker — Full Tutorial

Stack: FastAPI (serving), LangGraph + LangChain Google GenAI (the agent from your notebook), Postman (testing), Docker (deployment). Editor: VS Code.

Before you start, one thing to decide: your notebook agent has no memory (each `graph.invoke` starts fresh, that's why "what city did I give?" failed). I'll build the API the same way first, then show you how to add memory as an optional step, since that's a natural question once you see it fail again through the API.

---

## Step 0: Project setup in VS Code

Open a terminal in VS Code and set up the folder:

```bash
mkdir fastapi-agent-tutorial
cd fastapi-agent-tutorial
python -m venv venv

# activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

Install what we need for Step 1 first:

```bash
pip install fastapi "uvicorn[standard]"
```

Open the folder in VS Code (`code .`) and install the Python extension if you haven't already.

---

## Step 1: What is FastAPI, and a basic GET/POST app

FastAPI is a Python web framework for building APIs. It's built on top of Starlette (for the web handling) and Pydantic (for data validation). Two things make it worth learning over Flask for this use case:

- **Type hints define your request/response schema.** You write a normal Python class, FastAPI validates incoming JSON against it automatically.
- **Async support is native.** LLM calls are I/O-bound (waiting on a network response), so `async def` endpoints let your server handle other requests while waiting on the model. This matters a lot once you're serving an agent.

It also gives you free interactive docs at `/docs`, which is handy for testing without even opening Postman.

### 1.1 Create `main.py`

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="My First FastAPI App")


# --- GET endpoint ---
@app.get("/")
def read_root():
    return {"message": "Server is up"}


@app.get("/greet/{name}")
def greet(name: str):
    return {"message": f"Hello, {name}!"}


# --- POST endpoint ---
class AddRequest(BaseModel):
    a: int
    b: int


@app.post("/add")
def add_numbers(payload: AddRequest):
    return {"result": payload.a + payload.b}
```

A few things worth noticing:

- `@app.get("/greet/{name}")` — `{name}` is a **path parameter**, FastAPI passes it in as a function argument automatically.
- `AddRequest` is a Pydantic model. If someone POSTs `{"a": "hello"}`, FastAPI rejects it with a 422 before your function even runs. You don't write that validation yourself.

### 1.2 Run it

```bash
uvicorn main:app --reload
```

`main:app` means "look inside `main.py` for a variable called `app`". `--reload` restarts the server on file save, useful in dev, drop it in production.

Go to `http://127.0.0.1:8000/docs`. You get a UI where you can try both endpoints directly. That's Swagger UI, generated automatically from your type hints, not something you wrote.

Quick sanity check with curl:

```bash
curl http://127.0.0.1:8000/
curl -X POST http://127.0.0.1:8000/add -H "Content-Type: application/json" -d '{"a": 2, "b": 3}'
```

---

## Step 2: Build the agent, then serve it

### 2.1 Install agent dependencies

```bash
pip install langgraph langchain-google-genai langchain-core python-dotenv
```

### 2.2 Store your API key properly

Your notebook pulled the key from Colab's `userdata`. Locally, use a `.env` file instead (never hardcode API keys, never commit them).

Create `.env`:

```
GOOGLE_API_KEY=your_actual_key_here
```

Create `.gitignore`:

```
venv/
.env
__pycache__/
```

### 2.3 Build the agent as its own module: `agent.py`

Same graph as your notebook (weather tool + tool-calling loop), just moved out of Colab and into a reusable file.

```python
import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

# --- Model ---
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.environ["GOOGLE_API_KEY"],
)


# --- Tool ---
@tool
def get_weather(city: str) -> dict:
    """Return the current weather in a specified city"""
    return {"status": "success", "city": city, "weather": "Cloudy"}


tools = [get_weather]
llm_with_tools = model.bind_tools(tools)


# --- Graph node ---
def chatbot(state: MessagesState) -> dict:
    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


# --- Build graph ---
builder = StateGraph(MessagesState)
builder.add_node("chatbot", chatbot)
builder.add_node("tools", ToolNode(tools))
builder.add_edge(START, "chatbot")
builder.add_conditional_edges("chatbot", tools_condition)
builder.add_edge("tools", "chatbot")

graph = builder.compile()


def run_agent(user_message: str) -> str:
    """Run one turn through the agent and return the final text reply."""
    result = graph.invoke({"messages": user_message})
    return result['messages'][-1].content[0]["text"]
```

Note: I fixed the model name to `gemini-2.5-flash` — your notebook had `gemini-3.5-flash`, which doesn't exist as a model string. Check the current model list in Google AI Studio if this changes.

### 2.4 Serve it: update `main.py`

```python
from fastapi import FastAPI
from pydantic import BaseModel

from agent import run_agent

app = FastAPI(title="Agent API")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.get("/")
def read_root():
    return {"message": "Agent API is up"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    reply = run_agent(payload.message)
    return ChatResponse(reply=reply)
```

`response_model=ChatResponse` does two things: it validates what your function returns matches that shape, and it documents the response schema in `/docs`.

Run it the same way:

```bash
uvicorn main:app --reload
```

### 2.5 Test with Postman

1. Open Postman, create a new request.
2. Method: `POST`, URL: `http://127.0.0.1:8000/chat`
3. Body tab → raw → JSON:
   ```json
   { "message": "Current weather in Bangalore" }
   ```
4. Headers: Postman sets `Content-Type: application/json` automatically when you pick raw/JSON, but check it's there.
5. Send. You should get back:
   ```json
   { "reply": "The current weather in Bangalore is cloudy." }
   ```

Try a follow-up like `"What city did I ask about?"` in a second request. It'll fail to remember, same as your notebook did, because each call to `/chat` builds a fresh `{"messages": ...}` state with no history. That's expected at this stage, not a bug you introduced.

**If it doesn't work:** check the uvicorn terminal for the actual error before anything else. Missing/invalid API key and rate limits are the two most common failures here, and both show up clearly in the traceback.

### 2.6 (Optional) Give it memory across requests

If you want the follow-up question to work, the simplest fix without a database is an in-memory checkpointer keyed by a session id. This is enough to demo, not something to ship as-is (state is lost on restart, and it's not safe across multiple server processes).

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

def run_agent(user_message: str, session_id: str) -> str:
    config = {"configurable": {"thread_id": session_id}}
    result = graph.invoke({"messages": user_message}, config=config)
    return result["messages"][-1].content
```

And add `session_id: str` to `ChatRequest`, pass it through in `main.py`. I'd skip this until Step 2 is working end to end though, it's an extra moving part.

---

## Step 3: Dockerize it

### 3.1 Freeze your dependencies

Make sure your venv is active, then run:

```bash
pip freeze > requirements.txt
```

Sanity check the file — `pip freeze` sometimes pulls in unrelated packages if your venv is dirty. It should mainly contain: `fastapi`, `uvicorn`, `langgraph`, `langchain-google-genai`, `langchain-core`, `python-dotenv`, plus their sub-dependencies.

### 3.2 Create `.dockerignore`

Create a `.dockerignore` file in the project root:

```
venv/
__pycache__/
.env
*.pyc
.git/
*.md
```

This tells Docker what NOT to copy into the image. Most importantly, `.env` must be excluded — if it gets baked into the image layer, your API key is exposed permanently.

### 3.3 Create `Dockerfile`

Create a `Dockerfile` (no extension) in the project root:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Notes on the choices here:
- `python:3.11-slim` keeps the image smaller than the full `python:3.11`.
- Copying `requirements.txt` first and installing before `COPY . .` is intentional — Docker caches each layer. If your code changes but dependencies don't, it skips the slow `pip install` step on rebuild.
- `--host 0.0.0.0` is required. `127.0.0.1` inside a container only listens for connections from within that same container — your host machine can't reach it.
- No `--reload` in the container command, that's a dev-only flag.

Your project structure should now look like this:

```
fastapi-agent-tutorial/
├── .env                  ← NOT copied into image
├── .dockerignore
├── .gitignore
├── Dockerfile
├── requirements.txt
├── agent.py
└── main.py
```

### 3.4 Build the Docker image

From the project root (where your `Dockerfile` is):

```bash
docker build -t fastapi-agent .
```

- `-t fastapi-agent` tags the image with the name `fastapi-agent`
- `.` tells Docker to use the current directory as the build context

You'll see Docker pulling the base image and running each layer. On subsequent builds, unchanged layers are served from cache.

Verify the image was created:

```bash
docker images
```

You should see `fastapi-agent` in the list.

### 3.5 Run the container with port mapping

Your `.env` file must NOT be in the image, so you pass the API key at runtime using `--env-file`:

```bash
docker run -d -p 8000:8000 --env-file .env --name agent-container fastapi-agent
```

- `-d` runs the container in detached mode (background)
- `-p 8000:8000` maps port 8000 on your host to port 8000 inside the container (`host:container`)
- `--env-file .env` injects your `.env` variables into the container at runtime without baking them into the image
- `--name agent-container` gives the container a readable name

Check it's running:

```bash
docker ps
```

Test it the same way as before:

```bash
curl http://localhost:8000/
curl -X POST http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"message\": \"Current weather in Bangalore\"}"
```

Or open Postman and hit `http://localhost:8000/chat` — same request as Step 2.5.

### 3.6 Useful container commands

```bash
# View logs
docker logs agent-container

# Stop the container
docker stop agent-container

# Remove the container
docker rm agent-container

# Stop and remove in one go
docker rm -f agent-container

# Rebuild after code changes
docker rm -f agent-container
docker build -t fastapi-agent .
docker run -d -p 8000:8000 --env-file .env --name agent-container fastapi-agent
```
in at runtime instead.

### 3.4 Build and run

```bash
docker build -t agent-api .
docker run -d -p 8000:8000 --env-file .env --name agent-api-container agent-api
```

`--env-file .env` injects your environment variables at container start, without baking the key into the image. `-p 8000:8000` maps container port 8000 to your host's port 8000.

Test it exactly the same way as before, Postman request to `http://127.0.0.1:8000/chat` — the container is indistinguishable from the app running locally, which is the whole point.

### 3.5 Useful Docker commands while you're debugging

```bash
docker logs agent-api-container        # see what went wrong
docker exec -it agent-api-container bash   # poke around inside the container
docker stop agent-api-container
docker rm agent-api-container
```

---

## Recap of the file structure you end up with

```
fastapi-agent-tutorial/
├── venv/
├── main.py
├── agent.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
└── .env
```

One thing worth flagging before you build on top of this: this is a synchronous endpoint calling a blocking LLM call. For a single learner/demo this is fine. If you ever put real traffic behind it, switch `chat` to `async def` and use the async client (`ainvoke` instead of `invoke`), otherwise each request blocks a worker thread for the full duration of the LLM call.
