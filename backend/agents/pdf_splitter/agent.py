import os
import json
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
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
pdf_splitter_agent = Agent(
    name="pdf_splitter",
    model=MODEL,
    description="Analyzes PDF text and splits it into logical sections.",
    instruction="""
You are a PDF section analyzer.
Given raw PDF text and a total page count, identify the main sections or chapters.

Return ONLY a JSON array in exactly this format — no extra text, no markdown:
[
    {"title": "Introduction", "page_start": 1, "page_end": 3, "summary": "brief summary"},
    {"title": "Chapter 1: Topic", "page_start": 4, "page_end": 8, "summary": "brief summary"}
]

Rules:
- Maximum 10 sections
- No gaps — every page must be in exactly one section
- Last section must end on the total page number given
- Return ONLY the raw JSON array
""",
)

session_service = InMemorySessionService()
runner = Runner(
    agent=pdf_splitter_agent,
    app_name="pdf_splitter",
    session_service=session_service,
)

# ── A2A FastAPI server (runs on port 8001) ────────────────────────────────────
app = FastAPI(title="PDF Splitter Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

AGENT_CARD = {
    "name": "pdf_splitter",
    "description": "Splits PDF text into logical sections using Gemini on Vertex AI.",
    "version": "1.0.0",
    "url": "http://localhost:8001",
    "skills": [{
        "id": "split_sections",
        "name": "Split PDF into Sections",
        "description": "Analyzes raw PDF text and returns structured section metadata.",
        "inputModes": ["text"],
        "outputModes": ["text"],
    }],
}

class SplitRequest(BaseModel):
    pdf_text: str
    total_pages: int

@app.get("/.well-known/agent.json")
def agent_card():
    return AGENT_CARD

@app.get("/health")
def health():
    return {"status": "pdf_splitter running", "port": 8001}

@app.post("/run")
async def run(req: SplitRequest):
    session = await session_service.create_session(
        state={}, app_name="pdf_splitter", user_id="orchestrator"
    )
    prompt = (
        f"Total pages: {req.total_pages}\n\n"
        f"PDF Text (first 8000 chars):\n{req.pdf_text[:8000]}"
    )
    content = types.Content(role="user", parts=[types.Part(text=prompt)])

    response_text = ""
    async for event in runner.run_async(
        user_id="orchestrator",
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = event.content.parts[0].text
            break

    # Strip markdown fences if Gemini wrapped the JSON
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:].strip()

    try:
        sections = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"JSON parse failed: {e}\nRaw: {response_text[:300]}")

    return {"sections": sections, "status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)