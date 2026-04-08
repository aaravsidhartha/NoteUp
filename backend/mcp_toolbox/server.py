"""
NoteUp MCP Server
Exposes student notes and PDF sections as MCP tools
so the answer_agent can retrieve them during Q&A.
"""
import os
from dotenv import load_dotenv
from google.cloud import firestore
from mcp.server.fastmcp import FastMCP

load_dotenv()

db = firestore.Client(project=os.getenv("PROJECT_ID", "noteup2"), database="noteup-db")
mcp = FastMCP("noteup-tools")


@mcp.tool()
def get_student_notes(pdf_id: str) -> str:
    """
    Retrieve all saved notes and questions the student has made
    while reading a specific PDF. Returns a formatted summary
    so the AI can reference prior study context.
    """
    try:
        cards_ref = db.collection("cards").where("pdf_id", "==", pdf_id).stream()
        cards = [c.to_dict() for c in cards_ref]

        if not cards:
            return "No prior notes or questions found for this PDF."

        notes = []
        questions = []
        for card in cards:
            if card.get("card_type") == "note":
                notes.append(f"- [Note, Page {card.get('page_number', '?')}] {card.get('title', '')}")
            else:
                questions.append(f"- [Question, Page {card.get('page_number', '?')}] {card.get('title', '')}")

        result = ""
        if notes:
            result += "Student's saved notes:\n" + "\n".join(notes) + "\n\n"
        if questions:
            result += "Student's previous questions:\n" + "\n".join(questions)

        return result.strip() if result.strip() else "No prior notes found."
    except Exception as e:
        return f"Could not retrieve notes: {str(e)}"


@mcp.tool()
def get_pdf_sections(pdf_id: str) -> str:
    """
    Retrieve the section structure of a PDF document —
    titles, page ranges, and summaries of each section.
    Useful for giving the student context about where they are in the document.
    """
    try:
        sections_ref = db.collection("sections").where("pdf_id", "==", pdf_id).stream()
        sections = [s.to_dict() for s in sections_ref]

        if not sections:
            return "No sections found for this PDF."

        sections.sort(key=lambda x: x.get("section_order", 0))
        lines = []
        for s in sections:
            lines.append(
                f"- {s.get('title', 'Untitled')} "
                f"(Pages {s.get('page_start', '?')}–{s.get('page_end', '?')})"
            )

        return "PDF sections:\n" + "\n".join(lines)
    except Exception as e:
        return f"Could not retrieve sections: {str(e)}"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8003)