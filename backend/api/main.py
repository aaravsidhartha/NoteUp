import os
import uuid
import fitz  # pymupdf
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from orchestrator import orchestrator
load_dotenv()

app = FastAPI(title="NoteUp API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── In-memory storage (AlloyDB swap comes later) ──────────────────────────────
pdfs_store     = {}
sections_store = {}
cards_store    = {}
messages_store = {}

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Models ────────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    card_id:       Optional[str] = None
    pdf_id:        str
    section_id:    str
    selected_text: str
    page_number:   int
    question:      str
    card_type:     str = "question"

class MessageRequest(BaseModel):
    card_id:  str
    question: str

# ── Startup health check ──────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_check():
    status = await orchestrator.check_agents()
    print("=== Agent health check ===")
    for agent, result in status.items():
        print(f"  {agent}: {result}")
    print("==========================")

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
class SimplifyRequest(BaseModel):
    note_text: str

@app.post("/simplify")
async def simplify_note(req: SimplifyRequest):
    simplified = await orchestrator.answer_question(
        section_title="", selected_text="", page_context="",
        question=f"Rewrite this study note to be clearer and more concise. Keep all key information. Return ONLY the rewritten note, nothing else. Original note: {req.note_text}"
    )
    return {"simplified": simplified}
def root():
    return {"status": "NoteUp API is running"}

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    pdf_id    = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{pdf_id}.pdf")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc         = fitz.open(file_path)
    total_pages = len(doc)
    pages_text  = {}
    full_text   = ""
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text()
        pages_text[page_num + 1] = text
        full_text += f"\n--- Page {page_num + 1} ---\n{text}"
    doc.close()

    # A2A call to pdf_splitter agent
    sections_data = await orchestrator.split_pdf(full_text, total_pages)

    sections = []
    for i, sec in enumerate(sections_data):
        section_id = str(uuid.uuid4())
        section = {
            "id":            section_id,
            "pdf_id":        pdf_id,
            "title":         sec["title"],
            "page_start":    sec["page_start"],
            "page_end":      sec["page_end"],
            "summary":       sec.get("summary", ""),
            "section_order": i,
        }
        sections_store[section_id] = section
        sections.append(section)

    pdfs_store[pdf_id] = {
        "id":            pdf_id,
        "filename":      f"{pdf_id}.pdf",
        "original_name": file.filename,
        "total_pages":   total_pages,
        "pages_text":    pages_text,
    }

    return {
        "pdf_id":      pdf_id,
        "filename":    file.filename,
        "total_pages": total_pages,
        "sections":    sections,
    }

@app.get("/pdf/{pdf_id}/page/{page_number}")
async def get_page_image(pdf_id: str, page_number: int):
    file_path = os.path.join(UPLOAD_DIR, f"{pdf_id}.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="PDF not found")

    doc = fitz.open(file_path)
    if page_number < 1 or page_number > len(doc):
        raise HTTPException(status_code=400, detail="Invalid page number")

    page       = doc[page_number - 1]
    mat        = fitz.Matrix(2, 2)
    pix        = page.get_pixmap(matrix=mat)
    image_path = os.path.join(UPLOAD_DIR, f"{pdf_id}_page_{page_number}.png")
    pix.save(image_path)
    doc.close()

    return FileResponse(image_path, media_type="image/png")

@app.post("/query")
async def create_query(req: QueryRequest):
    section       = sections_store.get(req.section_id, {})
    section_title = section.get("title", "Unknown Section")
    pdf           = pdfs_store.get(req.pdf_id, {})
    page_context  = pdf.get("pages_text", {}).get(req.page_number, "")

    # Notes don't get an AI response
    if req.card_type == 'note':
        card_id = str(uuid.uuid4())
        card = {
            "id": card_id, "pdf_id": req.pdf_id, "section_id": req.section_id,
            "title": req.question[:60] + ("..." if len(req.question) > 60 else ""),
            "card_type": "note", "selected_text": req.selected_text, "page_number": req.page_number,
        }
        cards_store[card_id] = card
        msg_id = str(uuid.uuid4())
        messages_store[msg_id] = {"id": msg_id, "card_id": card_id, "role": "user", "content": req.question}
        return {"card": card, "messages": [{"role": "user", "content": req.question}]}

    # A2A call to answer_agent
    ai_answer  = await orchestrator.answer_question(
        section_title=section_title,
        selected_text=req.selected_text,
        page_context=page_context,
        question=req.question,
    )
    card_title = await orchestrator.generate_card_title(req.question)

    card_id = str(uuid.uuid4())
    card = {
        "id":            card_id,
        "pdf_id":        req.pdf_id,
        "section_id":    req.section_id,
        "title":         card_title,
        "card_type":     req.card_type,
        "selected_text": req.selected_text,
        "page_number":   req.page_number,
    }
    cards_store[card_id] = card

    user_msg_id = str(uuid.uuid4())
    ai_msg_id   = str(uuid.uuid4())
    messages_store[user_msg_id] = {"id": user_msg_id, "card_id": card_id, "role": "user",      "content": req.question}
    messages_store[ai_msg_id]   = {"id": ai_msg_id,   "card_id": card_id, "role": "assistant", "content": ai_answer}

    return {
        "card": card,
        "messages": [
            {"role": "user",      "content": req.question},
            {"role": "assistant", "content": ai_answer},
        ],
    }

@app.post("/message")
async def add_message(req: MessageRequest):
    card = cards_store.get(req.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    history = [m for m in messages_store.values() if m["card_id"] == req.card_id]
    conversation = ""
    for msg in history:
        role = "Student" if msg["role"] == "user" else "Assistant"
        conversation += f"{role}: {msg['content']}\n\n"

    pdf          = pdfs_store.get(card["pdf_id"], {})
    page_context = pdf.get("pages_text", {}).get(card["page_number"], "")
    section      = sections_store.get(card["section_id"], {})

    # A2A call to answer_agent with conversation history
    ai_answer = await orchestrator.answer_question(
        section_title=section.get("title", ""),
        selected_text=card["selected_text"],
        page_context=page_context,
        question=req.question,
        conversation_history=conversation,
    )

    user_msg_id = str(uuid.uuid4())
    ai_msg_id   = str(uuid.uuid4())
    messages_store[user_msg_id] = {"id": user_msg_id, "card_id": req.card_id, "role": "user",      "content": req.question}
    messages_store[ai_msg_id]   = {"id": ai_msg_id,   "card_id": req.card_id, "role": "assistant", "content": ai_answer}

    return {
        "messages": [
            {"role": "user",      "content": req.question},
            {"role": "assistant", "content": ai_answer},
        ]
    }

@app.get("/cards/{pdf_id}")
async def get_cards(pdf_id: str):
    sections = [s for s in sections_store.values() if s["pdf_id"] == pdf_id]
    sections.sort(key=lambda x: x["section_order"])
    result = []
    for section in sections:
        section_cards = [c for c in cards_store.values() if c["section_id"] == section["id"]]
        result.append({"section": section, "cards": section_cards})
    return result

@app.get("/thread/{card_id}")
async def get_thread(card_id: str):
    card = cards_store.get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    messages = [m for m in messages_store.values() if m["card_id"] == card_id]
    return {"card": card, "messages": messages}

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "..", "frontend"), html=True), name="frontend")