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
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseConnectionParams
from google.genai import types

load_dotenv()

# ── Vertex AI config for ADK ──────────────────────────────────────────────────
os.environ["GOOGLE_CLOUD_PROJECT"]      = os.getenv("PROJECT_ID", "noteup2")
os.environ["GOOGLE_CLOUD_LOCATION"]     = os.getenv("REGION", "us-central1")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── MCP Toolset — connects to NoteUp MCP server via SSE ──────────────────────
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8003/sse")

mcp_toolset = MCPToolset(
    connection_params=SseConnectionParams(
        url=MCP_SERVER_URL,
    )
)

# ── ADK Agent with MCP tools ──────────────────────────────────────────────────
answer_agent = Agent(
    name="answer_agent",
    model=MODEL,
    description="Answers student questions about highlighted PDF text, with access to their saved notes via MCP.",
    instruction="""
You are an intelligent study assistant helping a student reading a PDF document.
You have access to two MCP tools:
- get_student_notes(pdf_id): retrieves all notes and questions the student has saved for this PDF
- get_pdf_sections(pdf_id): retrieves the section structure of the PDF

When answering a question:
1. If a pdf_id is provided, call get_student_notes(pdf_id) to check for relevant prior notes
2. If prior notes are relevant to the question, reference them naturally: "Based on your note on page X..."
3. Answer the student's question using the PDF context provided AND your general knowledge
4. NEVER refuse to answer. If the PDF context is irrelevant, answer from general knowledge.

Be clear, concise, and use bullet points where helpful.
Do not repeat the question back.
""",
    tools=[mcp_toolset],
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
    "description": "Answers student questions about selected PDF text, using MCP to retrieve student notes.",
    "version": "2.0.0",
    "url": "http://localhost:8002",
    "skills": [{
        "id": "answer_question",
        "name": "Answer Student Question",
        "description": "Takes selected text + question + pdf_id and returns a study-focused answer, referencing prior student notes via MCP.",
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
    pdf_id: Optional[str] = ""

@app.get("/.well-known/agent.json")
def agent_card():
    return AGENT_CARD

@app.get("/health")
def health():
    return {"status": "answer_agent running", "port": 8002, "mcp": "enabled"}

@app.post("/run")
async def run(req: AnswerRequest):
    try:
        session = await session_service.create_session(
            state={}, app_name="answer_agent", user_id="orchestrator"
        )

        history_block = ""
        if req.conversation_history:
            history_block = f"\nPrevious conversation:\n{req.conversation_history}\n"

        context_block = ""
        if req.selected_text and req.selected_text.strip():
            context_block += f"Selected text from PDF: \"{req.selected_text}\"\n"
        if req.page_context and req.page_context.strip():
            context_block += f"Page context: {req.page_context[:1000]}\n"
        if req.section_title and req.section_title.strip():
            context_block += f"Section: {req.section_title}\n"
        if context_block:
            context_block = f"PDF Context (use only if relevant):\n{context_block}\n"

        pdf_hint = f"PDF ID for tool calls: {req.pdf_id}\n" if req.pdf_id else ""

        prompt = (
            f"{pdf_hint}"
            f"{context_block}"
            f"{history_block}"
            f"Student's question: {req.question}"
        )

        print(f"\n=== ANSWER AGENT CALLED ===")
        print(f"PDF ID: {req.pdf_id}")
        print(f"Question: {req.question}")
        print(f"Prompt: {prompt[:200]}")

        content = types.Content(role="user", parts=[types.Part(text=prompt)])
        answer_text = ""
        async for event in runner.run_async(
            user_id="orchestrator",
            session_id=session.id,
            new_message=content,
        ):
            print(f"Event: {event}")
            if event.is_final_response() and event.content and event.content.parts:
                answer_text = event.content.parts[0].text
                break

        print(f"Answer: {answer_text[:100]}")
        print(f"===========================\n")
        return {"answer": answer_text, "status": "success"}

    except Exception as e:
        import traceback
        print(f"ERROR in /run: {e}")
        traceback.print_exc()
        return {"answer": f"Error: {str(e)}", "status": "error"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)