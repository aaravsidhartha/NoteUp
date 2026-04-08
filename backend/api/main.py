import os
import uuid
import hashlib
import fitz  # pymupdf
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from google.cloud import firestore
from google.cloud import storage as gcs
import sys
sys.path.insert(0, os.path.dirname(__file__))
from orchestrator import orchestrator
load_dotenv()

app = FastAPI(title="NoteUp API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ── Firestore client ──────────────────────────────────────────────────────────
db = firestore.Client(project="noteup2", database="noteup-db")
gcs_client = gcs.Client(project="noteup2")
GCS_BUCKET = "noteup2-pdfs"

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Firestore helpers ─────────────────────────────────────────────────────────
def fs_set(collection: str, doc_id: str, data: dict):
    db.collection(collection).document(doc_id).set(data)

def fs_get(collection: str, doc_id: str):
    doc = db.collection(collection).document(doc_id).get()
    return doc.to_dict() if doc.exists else None

def fs_query(collection: str, field: str, value):
    docs = db.collection(collection).where(field, "==", value).stream()
    return [d.to_dict() for d in docs]

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

class SimplifyRequest(BaseModel):
    note_text: str

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
def root():
    return {"status": "NoteUp API is running"}

@app.post("/simplify")
async def simplify_note(req: SimplifyRequest):
    simplified = await orchestrator.answer_question(
        section_title="", selected_text="", page_context="",
        question=f"Rewrite this study note to be clearer and more concise. Keep all key information. Return ONLY the rewritten note, nothing else. Original note: {req.note_text}"
    )
    return {"simplified": simplified}

@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    content   = await file.read()
    pdf_id    = hashlib.md5(content).hexdigest()
    file_path = os.path.join(UPLOAD_DIR, f"{pdf_id}.pdf")

    # ── If already processed, return existing data immediately ────────────────
    existing_pdf = fs_get("pdfs", pdf_id)
    if existing_pdf:
        existing_sections = fs_query("sections", "pdf_id", pdf_id)
        existing_sections.sort(key=lambda x: x["section_order"])
        # Also load all cards for each section
        return {
            "pdf_id":      pdf_id,
            "filename":    file.filename,
            "total_pages": existing_pdf["total_pages"],
            "sections":    existing_sections,
        }

    # ── New PDF — process it ──────────────────────────────────────────────────
    with open(file_path, "wb") as f:
        f.write(content)
    # Also upload to GCS for persistence
    bucket = gcs_client.bucket(GCS_BUCKET)
    blob = bucket.blob(f"{pdf_id}.pdf")
    blob.upload_from_string(content, content_type="application/pdf")

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
        fs_set("sections", section_id, section)
        sections.append(section)

    # Store PDF metadata — pages_text keys must be strings for Firestore
    pages_text_str = {str(k): v for k, v in pages_text.items()}
    fs_set("pdfs", pdf_id, {
        "id":            pdf_id,
        "filename":      f"{pdf_id}.pdf",
        "original_name": file.filename,
        "total_pages":   total_pages,
        "pages_text":    pages_text_str,
    })

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
        try:
            bucket = gcs_client.bucket(GCS_BUCKET)
            blob = bucket.blob(f"{pdf_id}.pdf")
            blob.download_to_filename(file_path)
        except Exception:
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
    section       = fs_get("sections", req.section_id) or {}
    section_title = section.get("title", "Unknown Section")
    pdf           = fs_get("pdfs", req.pdf_id) or {}
    page_context  = pdf.get("pages_text", {}).get(str(req.page_number), "")

    if req.card_type == 'note':
        card_id = str(uuid.uuid4())
        card = {
            "id": card_id, "pdf_id": req.pdf_id, "section_id": req.section_id,
            "title": req.question[:60] + ("..." if len(req.question) > 60 else ""),
            "card_type": "note", "selected_text": req.selected_text, "page_number": req.page_number,
        }
        fs_set("cards", card_id, card)
        msg_id = str(uuid.uuid4())
        fs_set("messages", msg_id, {"id": msg_id, "card_id": card_id, "role": "user", "content": req.question})
        return {"card": card, "messages": [{"role": "user", "content": req.question}]}

    ai_answer = await orchestrator.answer_question(
        section_title=section_title,
        selected_text=req.selected_text,
        page_context=page_context,
        question=req.question,
        pdf_id=req.pdf_id,
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
    fs_set("cards", card_id, card)

    user_msg_id = str(uuid.uuid4())
    ai_msg_id   = str(uuid.uuid4())
    fs_set("messages", user_msg_id, {"id": user_msg_id, "card_id": card_id, "role": "user",      "content": req.question})
    fs_set("messages", ai_msg_id,   {"id": ai_msg_id,   "card_id": card_id, "role": "assistant", "content": ai_answer})

    return {
        "card": card,
        "messages": [
            {"role": "user",      "content": req.question},
            {"role": "assistant", "content": ai_answer},
        ],
    }

@app.post("/message")
async def add_message(req: MessageRequest):
    card = fs_get("cards", req.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    history      = fs_query("messages", "card_id", req.card_id)
    conversation = ""
    for msg in history:
        role = "Student" if msg["role"] == "user" else "Assistant"
        conversation += f"{role}: {msg['content']}\n\n"

    pdf          = fs_get("pdfs", card["pdf_id"]) or {}
    page_context = pdf.get("pages_text", {}).get(str(card["page_number"]), "")
    section      = fs_get("sections", card["section_id"]) or {}

    ai_answer = await orchestrator.answer_question(
        section_title=section.get("title", ""),
        selected_text=card["selected_text"],
        page_context=page_context,
        question=req.question,
        conversation_history=conversation,
        pdf_id=card["pdf_id"],
    )

    user_msg_id = str(uuid.uuid4())
    ai_msg_id   = str(uuid.uuid4())
    fs_set("messages", user_msg_id, {"id": user_msg_id, "card_id": req.card_id, "role": "user",      "content": req.question})
    fs_set("messages", ai_msg_id,   {"id": ai_msg_id,   "card_id": req.card_id, "role": "assistant", "content": ai_answer})

    return {
        "messages": [
            {"role": "user",      "content": req.question},
            {"role": "assistant", "content": ai_answer},
        ]
    }

@app.get("/cards/{pdf_id}")
async def get_cards(pdf_id: str):
    sections = fs_query("sections", "pdf_id", pdf_id)
    sections.sort(key=lambda x: x["section_order"])
    result = []
    for section in sections:
        section_cards = fs_query("cards", "section_id", section["id"])
        result.append({"section": section, "cards": section_cards})
    return result

@app.get("/thread/{card_id}")
async def get_thread(card_id: str):
    card = fs_get("cards", card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    messages = fs_query("messages", "card_id", card_id)
    return {"card": card, "messages": messages}

@app.get("/pdfs")
async def get_all_pdfs():
    docs = db.collection("pdfs").stream()
    pdfs = []
    for doc in docs:
        d = doc.to_dict()
        d.pop("pages_text", None)  # don't send full text to frontend
        pdfs.append(d)
    return pdfs

@app.get("/sections/{pdf_id}")
async def get_sections(pdf_id: str):
    sections = fs_query("sections", "pdf_id", pdf_id)
    sections.sort(key=lambda x: x["section_order"])
    return sections

@app.get("/pdf-file/{pdf_id}")
async def get_pdf_file(pdf_id: str):
    file_path = os.path.join(UPLOAD_DIR, f"{pdf_id}.pdf")
    if not os.path.exists(file_path):
        # Try to download from GCS
        try:
            bucket = gcs_client.bucket(GCS_BUCKET)
            blob = bucket.blob(f"{pdf_id}.pdf")
            blob.download_to_filename(file_path)
        except Exception:
            raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(file_path, media_type="application/pdf")

app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "..", "frontend"), html=True), name="frontend")