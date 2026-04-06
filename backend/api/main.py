import os
import uuid
import fitz  # pymupdf
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = FastAPI(title="NoteUp API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini client using Vertex AI
PROJECT_ID = os.getenv("PROJECT_ID", "noteup2")
REGION = os.getenv("REGION", "us-central1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

# In-memory storage
pdfs_store = {}
sections_store = {}
cards_store = {}
messages_store = {}

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ─── Models ───────────────────────────────────────────────

class QueryRequest(BaseModel):
    card_id: Optional[str] = None
    pdf_id: str
    section_id: str
    selected_text: str
    page_number: int
    question: str
    card_type: str = "question"

class MessageRequest(BaseModel):
    card_id: str
    question: str


# ─── Routes ───────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "NoteUp API is running"}


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF, extract text, split into sections."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    pdf_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{pdf_id}.pdf")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = fitz.open(file_path)
    total_pages = len(doc)
    pages_text = {}
    full_text = ""

    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text()
        pages_text[page_num + 1] = text
        full_text += f"\n--- Page {page_num + 1} ---\n{text}"

    doc.close()

    sections = await split_into_sections(pdf_id, full_text, total_pages)

    pdfs_store[pdf_id] = {
        "id": pdf_id,
        "filename": f"{pdf_id}.pdf",
        "original_name": file.filename,
        "total_pages": total_pages,
        "pages_text": pages_text
    }

    return {
        "pdf_id": pdf_id,
        "filename": file.filename,
        "total_pages": total_pages,
        "sections": sections
    }


async def split_into_sections(pdf_id: str, full_text: str, total_pages: int):
    """Use Gemini to identify sections in the PDF."""
    prompt = f"""
    Analyze this PDF text and identify the main sections or chapters.
    The PDF has {total_pages} pages.

    Return a JSON array of sections in this exact format:
    [
        {{"title": "Introduction", "page_start": 1, "page_end": 3, "summary": "brief summary"}},
        {{"title": "Chapter 1: Topic Name", "page_start": 4, "page_end": 8, "summary": "brief summary"}}
    ]

    Rules:
    - Maximum 10 sections
    - Every page must be covered
    - Last section must end on page {total_pages}
    - Return ONLY the JSON array, no other text

    PDF Text (first 8000 chars):
    {full_text[:8000]}
    """

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )

    response_text = response.text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    sections_data = json.loads(response_text)

    sections = []
    for i, sec in enumerate(sections_data):
        section_id = str(uuid.uuid4())
        section = {
            "id": section_id,
            "pdf_id": pdf_id,
            "title": sec["title"],
            "page_start": sec["page_start"],
            "page_end": sec["page_end"],
            "summary": sec.get("summary", ""),
            "section_order": i
        }
        sections_store[section_id] = section
        sections.append(section)

    return sections


@app.get("/pdf/{pdf_id}/page/{page_number}")
async def get_page_image(pdf_id: str, page_number: int):
    """Return a specific page of the PDF as an image."""
    file_path = os.path.join(UPLOAD_DIR, f"{pdf_id}.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF not found")

    doc = fitz.open(file_path)
    if page_number < 1 or page_number > len(doc):
        raise HTTPException(status_code=400, detail="Invalid page number")

    page = doc[page_number - 1]
    mat = fitz.Matrix(2, 2)
    pix = page.get_pixmap(matrix=mat)

    image_path = os.path.join(UPLOAD_DIR, f"{pdf_id}_page_{page_number}.png")
    pix.save(image_path)
    doc.close()

    return FileResponse(image_path, media_type="image/png")


@app.post("/query")
async def create_query(req: QueryRequest):
    """Create a new card and get AI answer."""
    section = sections_store.get(req.section_id, {})
    section_title = section.get("title", "Unknown Section")

    pdf = pdfs_store.get(req.pdf_id, {})
    page_text = pdf.get("pages_text", {}).get(req.page_number, "")

    prompt = f"""
    You are a helpful study assistant. A student is reading a PDF and has a question.

    Section: {section_title}
    Selected text: "{req.selected_text}"
    Page context: {page_text[:2000]}

    Student's question: {req.question}

    Give a clear, concise answer. Use simple language. If helpful, use bullet points.
    """

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )
    ai_answer = response.text

    title_prompt = f"Create a short 5-7 word title for this question: {req.question}. Return only the title, nothing else."
    title_response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=title_prompt
    )
    card_title = title_response.text.strip()

    card_id = str(uuid.uuid4())
    card = {
        "id": card_id,
        "pdf_id": req.pdf_id,
        "section_id": req.section_id,
        "title": card_title,
        "card_type": req.card_type,
        "selected_text": req.selected_text,
        "page_number": req.page_number,
    }
    cards_store[card_id] = card

    user_msg_id = str(uuid.uuid4())
    ai_msg_id = str(uuid.uuid4())

    messages_store[user_msg_id] = {
        "id": user_msg_id,
        "card_id": card_id,
        "role": "user",
        "content": req.question
    }
    messages_store[ai_msg_id] = {
        "id": ai_msg_id,
        "card_id": card_id,
        "role": "assistant",
        "content": ai_answer
    }

    return {
        "card": card,
        "messages": [
            {"role": "user", "content": req.question},
            {"role": "assistant", "content": ai_answer}
        ]
    }


@app.post("/message")
async def add_message(req: MessageRequest):
    """Add a follow-up message to an existing card thread."""
    card = cards_store.get(req.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    history = [
        m for m in messages_store.values()
        if m["card_id"] == req.card_id
    ]

    conversation = ""
    for msg in history:
        role = "Student" if msg["role"] == "user" else "Assistant"
        conversation += f"{role}: {msg['content']}\n\n"

    section = sections_store.get(card["section_id"], {})

    prompt = f"""
    You are a helpful study assistant continuing a conversation.

    Section: {section.get('title', '')}
    Selected text: "{card['selected_text']}"

    Previous conversation:
    {conversation}

    Student's follow-up: {req.question}

    Continue helping the student. Be concise and clear.
    """

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )
    ai_answer = response.text

    user_msg_id = str(uuid.uuid4())
    ai_msg_id = str(uuid.uuid4())

    messages_store[user_msg_id] = {
        "id": user_msg_id,
        "card_id": req.card_id,
        "role": "user",
        "content": req.question
    }
    messages_store[ai_msg_id] = {
        "id": ai_msg_id,
        "card_id": req.card_id,
        "role": "assistant",
        "content": ai_answer
    }

    return {
        "messages": [
            {"role": "user", "content": req.question},
            {"role": "assistant", "content": ai_answer}
        ]
    }


@app.get("/cards/{pdf_id}")
async def get_cards(pdf_id: str):
    """Get all cards for a PDF, grouped by section."""
    sections = [s for s in sections_store.values() if s["pdf_id"] == pdf_id]
    sections.sort(key=lambda x: x["section_order"])

    result = []
    for section in sections:
        section_cards = [
            c for c in cards_store.values()
            if c["section_id"] == section["id"]
        ]
        result.append({
            "section": section,
            "cards": section_cards
        })

    return result


@app.get("/thread/{card_id}")
async def get_thread(card_id: str):
    """Get all messages for a card."""
    card = cards_store.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    messages = [
        m for m in messages_store.values()
        if m["card_id"] == card_id
    ]

    return {
        "card": card,
        "messages": messages
    }


# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")