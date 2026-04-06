import os
import httpx
from typing import Any, Optional
from dotenv import load_dotenv

load_dotenv()

PDF_SPLITTER_URL = os.getenv("PDF_SPLITTER_URL", "http://localhost:8001")
ANSWER_AGENT_URL = os.getenv("ANSWER_AGENT_URL", "http://localhost:8002")

# Timeout for agent calls (Gemini can take a few seconds)
TIMEOUT = httpx.Timeout(60.0)


class NoteUpOrchestrator:
    """
    Orchestrator for NoteUp agents.
    Uses A2A protocol (HTTP POST to /run) to call sub-agents.
    Called directly by main.py — not a standalone server.
    """

    def __init__(self):
        self.pdf_splitter_url = PDF_SPLITTER_URL
        self.answer_agent_url = ANSWER_AGENT_URL

    # ── Agent Health Checks ────────────────────────────────────────────────────

    async def check_agents(self) -> dict:
        """Verify both agents are reachable. Called on API startup."""
        results = {}
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for name, url in [
                ("pdf_splitter", self.pdf_splitter_url),
                ("answer_agent", self.answer_agent_url),
            ]:
                try:
                    r = await client.get(f"{url}/health")
                    results[name] = r.json()
                except Exception as e:
                    results[name] = {"status": "unreachable", "error": str(e)}
        return results

    # ── Task: Split PDF into Sections ─────────────────────────────────────────

    async def split_pdf(self, pdf_text: str, total_pages: int) -> list[Any]:
        """
        Calls the pdf_splitter agent via A2A.
        Returns list of section dicts: {title, page_start, page_end, summary}
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{self.pdf_splitter_url}/run",
                json={"pdf_text": pdf_text, "total_pages": total_pages},
            )
            response.raise_for_status()
            data = response.json()
            return data["sections"]

    # ── Task: Answer a Question ───────────────────────────────────────────────

    async def answer_question(
        self,
        section_title: str,
        selected_text: str,
        page_context: str,
        question: str,
        conversation_history: Optional[str] = "",
    ) -> str:
        """
        Calls the answer_agent via A2A.
        Returns the AI answer string.
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{self.answer_agent_url}/run",
                json={
                    "section_title": section_title,
                    "selected_text": selected_text,
                    "page_context": page_context,
                    "question": question,
                    "conversation_history": conversation_history or "",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["answer"]

    # ── Task: Generate Card Title ─────────────────────────────────────────────

    async def generate_card_title(self, question: str) -> str:
        """
        Re-uses the answer_agent to generate a short card title.
        No section context needed — just the question.
        """
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"{self.answer_agent_url}/run",
                json={
                    "section_title": "",
                    "selected_text": "",
                    "page_context": "",
                    "question": (
                        f"Create a short 5-7 word title for this question: "
                        f'"{question}". Return ONLY the title, nothing else.'
                    ),
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["answer"].strip()


# Singleton — main.py imports this
orchestrator = NoteUpOrchestrator()