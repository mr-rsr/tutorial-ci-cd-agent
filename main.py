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