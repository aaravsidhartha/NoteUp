import os
import httpx
from typing import Optional, Any
from dotenv import load_dotenv

load_dotenv()

PDF_SPLITTER_URL = os.getenv("PDF_SPLITTER_URL", "http://localhost:8001")
ANSWER_AGENT_URL = os.getenv("ANSWER_AGENT_URL", "http://localhost:8002")
TIMEOUT = httpx.Timeout(60.0)


class NoteUpOrchestrator:
    """
    Calls pdf_splitter and answer_agent via A2A (HTTP POST to /run).
    Sits inside the main API process — not a standalone server.
    """

    async def check_agents(self) -> dict:
        """Health check both agents. Called on API startup."""
        results = {}
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            for name, url in [
                ("pdf_splitter", PDF_SPLITTER_URL),
                ("answer_agent", ANSWER_AGENT_URL),
            ]:
                try:
                    r = await client.get(f"{url}/health")
                    results[name] = r.json()
                except Exception as e:
                    results[name] = {"status": "unreachable", "error": str(e)}
        return results

    async def split_pdf(self, pdf_text: str, total_pages: int) -> list[Any]:
        """A2A call → pdf_splitter agent. Returns list of section dicts."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{PDF_SPLITTER_URL}/run",
                json={"pdf_text": pdf_text, "total_pages": total_pages},
            )
            r.raise_for_status()
            return r.json()["sections"]

    async def answer_question(
        self,
        section_title: str,
        selected_text: str,
        page_context: str,
        question: str,
        conversation_history: Optional[str] = "",
    ) -> str:
        """A2A call → answer_agent. Returns the AI answer string."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{ANSWER_AGENT_URL}/run",
                json={
                    "section_title": section_title,
                    "selected_text": selected_text,
                    "page_context": page_context,
                    "question": question,
                    "conversation_history": conversation_history or "",
                },
            )
            r.raise_for_status()
            return r.json()["answer"]

    async def generate_card_title(self, question: str) -> str:
        """Reuses answer_agent to make a short card title."""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(
                f"{ANSWER_AGENT_URL}/run",
                json={
                    "section_title": "",
                    "selected_text": "",
                    "page_context": "",
                    "question": (
                        f"Create a short 5-7 word title for this question: "
                        f'"{question}". Return ONLY the title, nothing else.'
                    ),
                    "conversation_history": "",
                },
            )
            r.raise_for_status()
            return r.json()["answer"].strip()


# Singleton imported by main.py
orchestrator = NoteUpOrchestrator()