import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

# ── Vertex AI config for ADK ──────────────────────────────────────────────────
os.environ["GOOGLE_CLOUD_PROJECT"]      = os.getenv("PROJECT_ID", "noteup2")
os.environ["GOOGLE_CLOUD_LOCATION"]     = os.getenv("REGION", "us-central1")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── ADK Agent definition ──────────────────────────────────────────────────────
answer_agent = Agent(
    name="answer_agent",
    model=MODEL,
    description="Answers student questions about highlighted PDF text.",
    instruction="""
You are a helpful study assistant. A student is reading a PDF and has highlighted
some text to ask a question about.

You will receive the section title, the exact highlighted text, surrounding page
context, and the student's question. If a previous conversation history is included,
use it to give a better follow-up answer.

Be clear and concise. Use bullet points when helpful. Do not repeat the question.
""",
)

session_service = InMemorySessionService()
runner = Runner(
    agent=answer_agent,
    app_name="answer_agent",
    session_service=session_service,
)

# ── A2A FastAPI server (runs on port 8002) ────────────────────────────────────
app = FastAPI(title="Answer Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

AGENT_CARD = {
    "name": "answer_agent",
    "description": "Answers student questions about selected PDF text.",
    "version": "1.0.0",
    "url": "http://localhost:8002",
    "skills": [{
        "id": "answer_question",
        "name": "Answer Student Question",
        "description": "Takes selected text + question and returns a study-focused answer.",
        "inputModes": ["text"],
        "outputModes": ["text"],
    }],
}

class AnswerRequest(BaseModel):
    section_title: str
    selected_text: str
    page_context: str
    question: str
    conversation_history: Optional[str] = ""

@app.get("/.well-known/agent.json")
def agent_card():
    return AGENT_CARD

@app.get("/health")
def health():
    return {"status": "answer_agent running", "port": 8002}

@app.post("/run")
async def run(req: AnswerRequest):
    session = await session_service.create_session(
        state={}, app_name="answer_agent", user_id="orchestrator"
    )

    history_block = ""
    if req.conversation_history:
        history_block = f"\nPrevious conversation:\n{req.conversation_history}\n"

    prompt = (
        f"Section: {req.section_title}\n"
        f"Selected text: \"{req.selected_text}\"\n"
        f"Page context: {req.page_context[:2000]}\n"
        f"{history_block}"
        f"Student's question: {req.question}"
    )

    content = types.Content(role="user", parts=[types.Part(text=prompt)])

    answer_text = ""
    async for event in runner.run_async(
        user_id="orchestrator",
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            answer_text = event.content.parts[0].text
            break

    return {"answer": answer_text, "status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)