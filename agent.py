import os
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

# --- Model ---
model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash",
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