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
You are an intelligent study assistant helping a student who is reading a PDF document.

The student may ask questions about:
1. The selected text or page content — answer using that context
2. General knowledge topics triggered by what they're reading — answer freely from your knowledge
3. Topics completely unrelated to the PDF — STILL answer helpfully from your general knowledge

NEVER refuse to answer or say "the document doesn't contain this information."
If the PDF context is irrelevant to the question, simply ignore it and answer from your knowledge.
Be clear, concise, and use bullet points where helpful.
Do not repeat the question back.
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
    page_context:  str
    question:      str
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

    # Only include PDF context if it's actually present and meaningful
    context_block = ""
    if req.selected_text and req.selected_text.strip() and req.selected_text not in ('""', "''"):
        context_block += f"Selected text from PDF: \"{req.selected_text}\"\n"
    if req.page_context and req.page_context.strip():
        context_block += f"Page context: {req.page_context[:1000]}\n"
    if req.section_title and req.section_title.strip():
        context_block += f"Section: {req.section_title}\n"

    if context_block:
        context_block = f"PDF Context (use only if relevant to the question):\n{context_block}\n"

    prompt = (
        f"{context_block}"
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