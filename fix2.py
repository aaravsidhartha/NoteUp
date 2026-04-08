import re

with open('backend/api/main.py', 'r') as f:
    content = f.read()

new_endpoints = '''
class PdfSummaryRequest(BaseModel):
    pdf_id: str

@app.post("/summarize-pdf")
async def summarize_full_pdf(req: PdfSummaryRequest):
    pdf = fs_get("pdfs", req.pdf_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    pages_text = pdf.get("pages_text", {})
    full_text = ""
    for k in sorted(pages_text.keys(), key=lambda x: int(x)):
        full_text += pages_text[k] + "\\n"
        if len(full_text) > 8000:
            break
    guide = await orchestrator.answer_question(
        section_title="", selected_text="", page_context="",
        question=f"Create a comprehensive study guide summarizing the key topics, concepts, findings, and conclusions of this document. Organize clearly with headings.\\n\\nDocument content:\\n{full_text}"
    )
    return {"guide": guide}

@app.post("/quiz-pdf")
async def quiz_full_pdf(req: PdfSummaryRequest):
    pdf = fs_get("pdfs", req.pdf_id)
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF not found")
    pages_text = pdf.get("pages_text", {})
    full_text = ""
    for k in sorted(pages_text.keys(), key=lambda x: int(x)):
        full_text += pages_text[k] + "\\n"
        if len(full_text) > 8000:
            break
    quiz = await orchestrator.answer_question(
        section_title="", selected_text="", page_context="",
        question=f"Generate a quiz with 5 multiple choice questions based on this document. For each question provide: the question, 4 options (A/B/C/D), and the correct answer. Format clearly.\\n\\nDocument content:\\n{full_text}"
    )
    return {"quiz": quiz}
'''

content = content.replace('app.mount("/",', new_endpoints + '\napp.mount("/",')

with open('backend/api/main.py', 'w') as f:
    f.write(content)
print("main.py done")

with open('frontend/app.js', 'r') as f:
    js = f.read()

new_study_guide = '''async function generateStudyGuide(mode) {
    if (!state.pdfId) return;
    var modal = document.getElementById('feature-modal');
    var modalTitle = document.getElementById('modal-title');
    var modalBody = document.getElementById('modal-body');
    modalTitle.textContent = 'Study Guide';
    modalBody.innerHTML = '<p>Generating...</p>';
    modal.classList.remove('hidden');
    try {
        var endpoint = (mode === 'pdf') ? '/summarize-pdf' : '/study-guide';
        var res = await fetch(API + endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pdf_id: state.pdfId})
        });
        var data = await res.json();
        modalBody.innerHTML = (data.guide && data.guide.includes('No notes'))
            ? '<p style="color:#aaa">No notes yet. Add cards first.</p>'
            : marked.parse(data.guide);
    } catch(e) {
        modalBody.innerHTML = '<p style="color:red">Error.</p>';
    }
}'''

new_quiz = '''async function generateQuiz(mode) {
    if (!state.pdfId) return;
    var modal = document.getElementById('feature-modal');
    var modalTitle = document.getElementById('modal-title');
    var modalBody = document.getElementById('modal-body');
    modalTitle.textContent = 'Quiz';
    modalBody.innerHTML = '<p>Generating quiz...</p>';
    modal.classList.remove('hidden');
    try {
        var endpoint = (mode === 'pdf') ? '/quiz-pdf' : '/quiz';
        var res = await fetch(API + endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pdf_id: state.pdfId})
        });
        var data = await res.json();
        modalBody.innerHTML = (data.quiz && data.quiz.includes('No notes'))
            ? '<p style="color:#aaa">No notes yet. Add cards first.</p>'
            : marked.parse(data.quiz);
    } catch(e) {
        modalBody.innerHTML = '<p style="color:red">Error.</p>';
    }
}'''

new_buttons = """featureDiv.innerHTML = `
  <div style="margin-bottom:10px;">
    <div style="font-size:11px;color:#888;margin-bottom:6px;font-weight:600;">SUMMARISE</div>
    <div style="display:flex;gap:6px;">
      <button onclick="generateStudyGuide('pdf')" style="flex:1;padding:6px 8px;background:#1e1e2e;border:1px solid #6c63ff;color:#c9c9ff;border-radius:6px;cursor:pointer;font-size:12px;">Entire PDF</button>
      <button onclick="generateStudyGuide('cards')" style="flex:1;padding:6px 8px;background:#1e1e2e;border:1px solid #6c63ff;color:#c9c9ff;border-radius:6px;cursor:pointer;font-size:12px;">My Notes</button>
    </div>
  </div>
  <div>
    <div style="font-size:11px;color:#888;margin-bottom:6px;font-weight:600;">QUIZ ME</div>
    <div style="display:flex;gap:6px;">
      <button onclick="generateQuiz('pdf')" style="flex:1;padding:6px 8px;background:#1e1e2e;border:1px solid #6c63ff;color:#c9c9ff;border-radius:6px;cursor:pointer;font-size:12px;">Entire PDF</button>
      <button onclick="generateQuiz('cards')" style="flex:1;padding:6px 8px;background:#1e1e2e;border:1px solid #6c63ff;color:#c9c9ff;border-radius:6px;cursor:pointer;font-size:12px;">My Notes</button>
    </div>
  </div>
`;"""

js = re.sub(r'async function generateStudyGuide\(mode\).*?^\}',
            new_study_guide, js, flags=re.DOTALL|re.MULTILINE)
js = re.sub(r'async function generateQuiz\(mode\).*?^\}',
            new_quiz, js, flags=re.DOTALL|re.MULTILINE)
js = re.sub(r"featureDiv\.innerHTML = '.*?';",
            new_buttons, js, flags=re.DOTALL)

with open('frontend/app.js', 'w') as f:
    f.write(js)
print("app.js done")
print("All done!")
