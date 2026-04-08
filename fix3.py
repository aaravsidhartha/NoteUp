with open('frontend/app.js', 'r') as f:
    js = f.read()

# Replace generateStudyGuide
old_sg = """async function generateStudyGuide(mode) {
    if (!state.pdfId) return;
    var btn = event ? event.target : document.querySelector('[onclick*=\"generateStudyGuide\"]');
    btn.textContent = 'Generating...';
    btn.disabled = true;
    try {
        var res = await fetch(API + '/study-guide', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pdf_id: state.pdfId})
        });
        var data = await res.json();
        var modal = document.getElementById('feature-modal');
        var modalTitle = document.getElementById('modal-title');
        var modalBody = document.getElementById('modal-body');
        modalTitle.textContent = 'Study Guide';
        modalBody.innerHTML = marked.parse(data.guide);
        modal.classList.remove('hidden');
    } catch(e) {
        console.error(e);
    } finally {
        btn.textContent = '📚 Study Guide';
        btn.disabled = false;
    }
}"""

new_sg = """async function generateStudyGuide(mode) {
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
        modalBody.innerHTML = '<p style="color:red">Error generating study guide.</p>';
        console.error(e);
    }
}"""

old_quiz = """async function generateQuiz(mode) {
    if (!state.pdfId) return;
    var btn = event ? event.target : document.querySelector('[onclick*=\"generateQuiz\"]');
    btn.textContent = 'Generating...';
    btn.disabled = true;
    try {
        var res = await fetch(API + '/quiz', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({pdf_id: state.pdfId})
        });
        var data = await res.json();
        var modal = document.getElementById('feature-modal');
        var modalTitle = document.getElementById('modal-title');
        var modalBody = document.getElementById('modal-body');
        modalTitle.textContent = 'Quiz';
        modalBody.innerHTML = marked.parse(data.quiz);
        modal.classList.remove('hidden');
    } catch(e) {
        console.error(e);
    } finally {
        btn.textContent = '🧠 Quiz Me';
        btn.disabled = false;
    }
}"""

new_quiz = """async function generateQuiz(mode) {
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
        modalBody.innerHTML = '<p style="color:red">Error generating quiz.</p>';
        console.error(e);
    }
}"""

old_buttons = ("featureDiv.innerHTML = '\\n\\n' +\n"
"        '\\n\\n📋 Summarised Notes\\n\\n' +\n"
"        '\\n\\n' +\n"
"        'Entire PDF' +\n"
"        'Notes & Questions' +\n"
"        '\\n\\n' +\n"
"        '\\n\\n' +\n"
"        '\\n\\n🧠 Quiz Me\\n\\n' +\n"
"        '\\n\\n' +\n"
"        'Entire PDF' +\n"
"        'Notes & Questions' +\n"
"        '\\n\\n';")

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

if old_sg in js:
    js = js.replace(old_sg, new_sg)
    print("study guide replaced")
else:
    print("ERROR: study guide old text not found")

if old_quiz in js:
    js = js.replace(old_quiz, new_quiz)
    print("quiz replaced")
else:
    print("ERROR: quiz old text not found")

if old_buttons in js:
    js = js.replace(old_buttons, new_buttons)
    print("buttons replaced")
else:
    print("buttons string not found - trying partial match")
    if "📋 Summarised Notes" in js:
        import re
        js = re.sub(r"featureDiv\.innerHTML = '[^;]+';", new_buttons, js, flags=re.DOTALL)
        print("buttons replaced via regex")

with open('frontend/app.js', 'w') as f:
    f.write(js)
print("Done!")
