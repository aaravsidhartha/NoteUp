const API = 'https://noteup-93010491257.us-central1.run.app';
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

let state = {
    pdfId: null, totalPages: 0, currentPage: 1, sections: [],
    currentCardId: null, selectedText: '', selectedSectionId: null,
    cardType: 'question', pdfDoc: null, scale: 1.5
};

const homeScreen      = document.getElementById('home-screen');
const app             = document.getElementById('app');
const pdfInput        = document.getElementById('pdf-input');
const uploadStatus    = document.getElementById('upload-status');
const pageInfo        = document.getElementById('page-info');
const pdfNameEl       = document.getElementById('pdf-name');
const panelPdfName    = document.getElementById('panel-pdf-name');
const prevBtn         = document.getElementById('prev-page');
const nextBtn         = document.getElementById('next-page');
const zoomInBtn       = document.getElementById('zoom-in');
const zoomOutBtn      = document.getElementById('zoom-out');
const homeBtn         = document.getElementById('home-btn');
const sectionsList    = document.getElementById('sections-list');
const sectionView     = document.getElementById('section-view');
const threadView      = document.getElementById('thread-view');
const queryView       = document.getElementById('query-view');
const backBtn         = document.getElementById('back-btn');
const threadMessages  = document.getElementById('thread-messages');
const selectedTextDisplay = document.getElementById('selected-text-display');
const followUpInput   = document.getElementById('follow-up-input');
const sendFollowupBtn = document.getElementById('send-followup-btn');
const threadCardType  = document.getElementById('thread-card-type');
const cancelQueryBtn  = document.getElementById('cancel-query-btn');
const querySelectedText = document.getElementById('query-selected-text');
const queryInput      = document.getElementById('query-input');
const submitQueryBtn  = document.getElementById('submit-query-btn');
const queryLoading    = document.getElementById('query-loading');
const simplifyBtn     = document.getElementById('simplify-btn');
const typeButtons     = document.querySelectorAll('.type-btn');
const pdfLibrary      = document.getElementById('pdf-library');

// ── Load library on startup ───────────────────────────────────────────────────
loadLibrary();
document.body.classList.add('home-active');

async function loadLibrary() {
    try {
        var res = await fetch(API + '/pdfs');
        var pdfs = await res.json();
        renderLibrary(pdfs);
    } catch (err) {
        console.error('Failed to load library', err);
    }
}

function renderLibrary(pdfs) {
    if (!pdfs || pdfs.length === 0) {
        pdfLibrary.innerHTML = '<div class="library-empty">No PDFs yet. Upload one to get started.</div>';
        return;
    }
    pdfLibrary.innerHTML = '';
    pdfs.forEach(function(pdf) {
        var card = document.createElement('div');
        card.className = 'library-card';
        card.innerHTML =
            '<div class="library-card-icon">📄</div>' +
            '<div class="library-card-info">' +
                '<div class="library-card-name">' + pdf.original_name + '</div>' +
                '<div class="library-card-meta">' + pdf.total_pages + ' pages</div>' +
            '</div>' +
            '<button class="library-open-btn">Open →</button>';
        card.querySelector('.library-open-btn').addEventListener('click', function() {
            openPdfFromLibrary(pdf);
        });
        pdfLibrary.appendChild(card);
    });
}

async function exportNotes() {
    if (!state.pdfId) return;
    var res = await fetch(API + '/export/' + state.pdfId);
    var text = await res.text();
    var blob = new Blob([text], {type: 'text/markdown'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = 'study-notes.md';
    a.click(); URL.revokeObjectURL(url);
}

async function generateStudyGuide(mode) {
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
}

async function generateQuiz(mode) {
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
}

async function openPdfFromLibrary(pdf) {
    uploadStatus.textContent = 'Loading ' + pdf.original_name + '...';
    try {
        var fileRes = await fetch(API + '/pdf-file/' + pdf.id);
        var blob = await fileRes.blob();
        var arrayBuffer = await blob.arrayBuffer();
        state.pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        state.totalPages = state.pdfDoc.numPages;
        state.pdfId = pdf.id;
        state.currentPage = 1;
        var sectionsRes = await fetch(API + '/sections/' + pdf.id);
        state.sections = await sectionsRes.json();
        pdfNameEl.textContent = pdf.original_name;
        panelPdfName.textContent = pdf.original_name;
        homeScreen.classList.add('hidden');
        app.classList.remove('hidden');
        document.body.classList.remove('home-active');
    // Add toolbar buttons if not already there
    if (!document.getElementById('export-btn')) {
        var toolbar = document.querySelector('.pdf-toolbar');
        var btnGroup = document.createElement('div');
        btnGroup.style.cssText = 'display:flex;gap:6px;margin-left:auto;';
        btnGroup.innerHTML = '<button id="export-btn" onclick="exportNotes()" style="background:#1e1e1e;border:1px solid #2a2a2a;color:#e8e8e8;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:0.78rem;">⬆ Export</button>';
        toolbar.appendChild(btnGroup);
        // Add modal
        if (!document.getElementById('feature-modal')) {
            var modal = document.createElement('div');
            modal.id = 'feature-modal';
            modal.className = 'hidden';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:99999;display:flex;align-items:center;justify-content:center;';
            modal.innerHTML = '<div style="background:#1a1a1a;border:1px solid #2a2a2a;border-radius:12px;padding:24px;max-width:700px;width:90%;max-height:80vh;overflow-y:auto;position:relative;"><button onclick="document.getElementById(\'feature-modal\').classList.add(\'hidden\')" style="position:absolute;top:12px;right:12px;background:#2a2a2a;border:none;color:#e8e8e8;padding:4px 10px;border-radius:6px;cursor:pointer;">✕</button><h2 id="modal-title" style="color:#e8e8e8;margin-bottom:16px;"></h2><div id="modal-body" style="color:#c8c8c8;font-size:0.9rem;line-height:1.6;"></div></div>';
            document.body.appendChild(modal);
        }
    }
        ensureModalAndExport();
        uploadStatus.textContent = '';
        await renderAllPages();
        renderSections();
        var cardsRes = await fetch(API + '/cards/' + state.pdfId);
        var cardsData = await cardsRes.json();
        cardsData.forEach(function(item) {
            item.cards.forEach(function(card) { addCardToPanel(card); });
        });
    } catch (err) {
        uploadStatus.textContent = 'Error loading PDF.';
        console.error(err);
    }
}

// ── Home button ───────────────────────────────────────────────────────────────
// Add Home label to button
if (homeBtn) homeBtn.innerHTML = '🏠 Home';
homeBtn.addEventListener('click', function() {
    app.classList.add('hidden');
    homeScreen.classList.remove('hidden');
    document.body.classList.add('home-active');
    loadLibrary();
});

// ── Upload ────────────────────────────────────────────────────────────────────
pdfInput.addEventListener('change', async function(e) {
    var file = e.target.files[0];
    if (!file) return;
    uploadStatus.textContent = 'Uploading and analysing PDF...';
    var arrayBuffer = await file.arrayBuffer();
    state.pdfDoc = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    state.totalPages = state.pdfDoc.numPages;
    var formData = new FormData();
    formData.append('file', file);
    try {
        var res = await fetch(API + '/upload', { method: 'POST', body: formData });
        var data = await res.json();
        state.pdfId = data.pdf_id;
        state.sections = data.sections;
        state.currentPage = 1;
        pdfNameEl.textContent = file.name;
        panelPdfName.textContent = file.name;
        homeScreen.classList.add('hidden');
        app.classList.remove('hidden');
        document.body.classList.remove('home-active');
        ensureModalAndExport();
        uploadStatus.textContent = '';
        await renderAllPages();
        renderSections();
        var cardsRes = await fetch(API + '/cards/' + state.pdfId);
        var cardsData = await cardsRes.json();
        cardsData.forEach(function(item) {
            item.cards.forEach(function(card) { addCardToPanel(card); });
        });
    } catch (err) {
        uploadStatus.textContent = 'Error uploading PDF. Please try again.';
        console.error(err);
    }
});

// ── Render ALL pages ──────────────────────────────────────────────────────────

function ensureModalAndExport() {
  if (!document.getElementById('export-btn')) {
    var toolbar = document.querySelector('.pdf-toolbar');
    var btnGroup = document.createElement('div');
    btnGroup.style.cssText = 'display:flex;gap:6px;margin-left:auto;';
    btnGroup.innerHTML = '<button id="export-btn" onclick="exportNotes()" style="padding:6px 14px;background:#6c63ff;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">Export Notes</button>';
    toolbar.appendChild(btnGroup);
  }
  if (!document.getElementById('feature-modal')) {
    var modal = document.createElement('div');
    modal.id = 'feature-modal';
    modal.className = 'hidden';
    modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);z-index:99999;display:flex;align-items:center;justify-content:center;';
    modal.innerHTML = '<div style="background:#1a1a2e;border-radius:12px;padding:32px;max-width:700px;width:90%;max-height:80vh;overflow-y:auto;position:relative;"><button onclick="document.getElementById(&quot;feature-modal&quot;).classList.add(&quot;hidden&quot;)" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#fff;font-size:20px;cursor:pointer;">✕</button><h2 id="modal-title" style="margin:0 0 16px;color:#fff;"></h2><div id="modal-body" style="color:#ccc;line-height:1.6;"></div></div>';
    document.body.appendChild(modal);
  }
}

async function renderAllPages() {
    var container = document.getElementById('pdf-container');
    container.innerHTML = '<div style="color:#888;text-align:center;padding:40px;">Loading pages...</div>';
    await new Promise(r => setTimeout(r, 10));
    container.innerHTML = '';
    container.style.overflowY = 'auto';
    container.style.overflowX = 'auto';
    container.style.background = '#141414';
    for (var i = 1; i <= state.totalPages; i++) {
        var page = await state.pdfDoc.getPage(i);
        var viewport = page.getViewport({ scale: state.scale });
        var pageWrapper = document.createElement('div');
        pageWrapper.className = 'pdf-page-wrapper';
        pageWrapper.dataset.pageNum = i;
        pageWrapper.style.cssText = 'position:relative;width:' + viewport.width + 'px;margin:10px auto;box-shadow:0 4px 20px rgba(0,0,0,0.5);';
        var canvas = document.createElement('canvas');
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.display = 'block';
        var overlay = document.createElement('canvas');
        overlay.width = viewport.width;
        overlay.height = viewport.height;
        overlay.style.cssText = 'position:absolute;top:0;left:0;cursor:crosshair;z-index:10;';
        pageWrapper.appendChild(canvas);
        pageWrapper.appendChild(overlay);
        container.appendChild(pageWrapper);
        await page.render({ canvasContext: canvas.getContext('2d'), viewport: viewport }).promise;
        setupDrawing(overlay, i);
    }
    pageInfo.textContent = 'Page 1 of ' + state.totalPages;
    prevBtn.disabled = true;
    nextBtn.disabled = state.totalPages <= 1;
    container.addEventListener('scroll', function() {
        var wrappers = container.querySelectorAll('.pdf-page-wrapper');
        var containerMid = container.getBoundingClientRect().top + container.getBoundingClientRect().height / 2;
        wrappers.forEach(function(wrapper) {
            var rect = wrapper.getBoundingClientRect();
            if (rect.top <= containerMid && rect.bottom >= containerMid) {
                var pn = parseInt(wrapper.dataset.pageNum);
                if (pn !== state.currentPage) {
                    state.currentPage = pn;
                    pageInfo.textContent = 'Page ' + pn + ' of ' + state.totalPages;
                    prevBtn.disabled = pn <= 1;
                    nextBtn.disabled = pn >= state.totalPages;
                }
            }
        });
    });
}

function scrollToPage(pageNum) {
    var wrapper = document.querySelector('.pdf-page-wrapper[data-page-num="' + pageNum + '"]');
    if (wrapper) {
        wrapper.scrollIntoView({ behavior: 'smooth', block: 'start' });
        state.currentPage = pageNum;
        pageInfo.textContent = 'Page ' + pageNum + ' of ' + state.totalPages;
        prevBtn.disabled = pageNum <= 1;
        nextBtn.disabled = pageNum >= state.totalPages;
    }
}

prevBtn.addEventListener('click', function() { if (state.currentPage > 1) scrollToPage(state.currentPage - 1); });
nextBtn.addEventListener('click', function() { if (state.currentPage < state.totalPages) scrollToPage(state.currentPage + 1); });

zoomInBtn.addEventListener('click', async function() {
    state.scale = Math.min(state.scale + 0.25, 3.5);
    await renderAllPages();
});
zoomOutBtn.addEventListener('click', async function() {
    state.scale = Math.max(state.scale - 0.25, 0.5);
    await renderAllPages();
});

// ── Resizable split panel ─────────────────────────────────────────────────────
var resizer = document.getElementById('resizer');
var isResizing = false;
resizer.addEventListener('mousedown', function(e) {
    isResizing = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
});
document.addEventListener('mousemove', function(e) {
    if (!isResizing) return;
    var appEl = document.getElementById('app');
    var appRect = appEl.getBoundingClientRect();
    var newPdfWidth = e.clientX - appRect.left;
    var newSideWidth = appRect.width - newPdfWidth - 5;
    if (newPdfWidth < 300 || newSideWidth < 260) return;
    var pdfPanel = document.getElementById('pdf-panel');
    var sidePanel = document.getElementById('side-panel');
    pdfPanel.style.flex = 'none';
    pdfPanel.style.width = newPdfWidth + 'px';
    sidePanel.style.width = newSideWidth + 'px';
    sidePanel.style.minWidth = newSideWidth + 'px';
});
document.addEventListener('mouseup', function() {
    if (!isResizing) return;
    isResizing = false;
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
});

// ── Box Drawing ───────────────────────────────────────────────────────────────
function setupDrawing(overlay, pageNum) {
    var ctx = overlay.getContext('2d');
    var startX, startY, drawing = false;
    overlay.addEventListener('mousedown', function(e) {
        var b = overlay.getBoundingClientRect();
        drawing = true;
        startX = e.clientX - b.left;
        startY = e.clientY - b.top;
    });
    overlay.addEventListener('mousemove', function(e) {
        if (!drawing) return;
        var b = overlay.getBoundingClientRect();
        var cx = e.clientX - b.left, cy = e.clientY - b.top;
        ctx.clearRect(0, 0, overlay.width, overlay.height);
        ctx.strokeStyle = '#6c63ff';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 3]);
        ctx.fillStyle = 'rgba(108,99,255,0.1)';
        ctx.fillRect(startX, startY, cx - startX, cy - startY);
        ctx.strokeRect(startX, startY, cx - startX, cy - startY);
    });
    overlay.addEventListener('mouseup', function(e) {
        if (!drawing) return;
        drawing = false;
        var b = overlay.getBoundingClientRect();
        var endX = e.clientX - b.left, endY = e.clientY - b.top;
        if (Math.abs(endX - startX) < 10 || Math.abs(endY - startY) < 10) {
            ctx.clearRect(0, 0, overlay.width, overlay.height);
            return;
        }
        var sel = window.getSelection();
        var selText = sel ? sel.toString().trim() : '';
        state.currentPage = pageNum;
        state.selectedText = selText.length > 0 ? selText : '[Selected area on page ' + pageNum + ']';
        state.selectedSectionId = getSectionForPage(pageNum);
        openQueryView();
    });
}

// ── Section Lookup ────────────────────────────────────────────────────────────
function getSectionForPage(pageNum) {
    for (var i = 0; i < state.sections.length; i++) {
        var s = state.sections[i];
        if (pageNum >= s.page_start && pageNum <= s.page_end) return s.id;
    }
    return state.sections.length > 0 ? state.sections[0].id : null;
}

// ── Render Sections ───────────────────────────────────────────────────────────
function renderSections() {
    sectionsList.innerHTML = '';
    // Add feature buttons at top of side panel
    var featureDiv = document.getElementById('side-feature-btns');
    if (!featureDiv) {
        featureDiv = document.createElement('div');
        featureDiv.id = 'side-feature-btns';
        featureDiv.style.cssText = 'padding:12px;border-bottom:1px solid #2a2a2a;';
        featureDiv.innerHTML = `
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
`;
        sectionsList.parentElement.insertBefore(featureDiv, sectionsList);
    }
    state.sections.forEach(function(section) {
        var sectionEl = document.createElement('div');
        sectionEl.className = 'section-item';
        var titleEl = document.createElement('div');
        titleEl.className = 'section-title';
        titleEl.innerHTML = section.title + ' <span class="section-pages">p.' + section.page_start + '-' + section.page_end + '</span>';
        titleEl.addEventListener('click', function() { scrollToPage(section.page_start); });
        var cardsList = document.createElement('div');
        cardsList.className = 'cards-list';
        cardsList.id = 'cards-' + section.id;
        sectionEl.appendChild(titleEl);
        sectionEl.appendChild(cardsList);
        sectionsList.appendChild(sectionEl);
    });
}

function renderCard(card, container) {
    var cardEl = document.createElement('div');
    cardEl.className = 'card-item card-type-' + card.card_type;
    var label = (card.card_type === 'question' ? 'Question' : 'Note') + ', Page ' + card.page_number;
    cardEl.innerHTML = '<div class="card-title">' + card.title + '</div><div class="card-meta">' + label + '</div>';
    cardEl.addEventListener('click', function() { openThread(card); });
    container.appendChild(cardEl);
}

function addCardToPanel(card) {
    var container = document.getElementById('cards-' + card.section_id);
    if (container) renderCard(card, container);
}

// ── Panel States ──────────────────────────────────────────────────────────────
function showSectionView() {
    sectionView.classList.remove('hidden');
    threadView.classList.add('hidden');
    queryView.classList.add('hidden');
}
function showThreadView() {
    sectionView.classList.add('hidden');
    threadView.classList.remove('hidden');
    queryView.classList.add('hidden');
}
function showQueryView() {
    sectionView.classList.add('hidden');
    threadView.classList.add('hidden');
    queryView.classList.remove('hidden');
}

backBtn.addEventListener('click', showSectionView);
cancelQueryBtn.addEventListener('click', function() {
    showSectionView();
    window.getSelection() && window.getSelection().removeAllRanges();
});

// ── Query View ────────────────────────────────────────────────────────────────
function openQueryView(prefilledText) {
    querySelectedText.textContent = '"' + state.selectedText + '"';
    queryInput.value = prefilledText || '';
    queryLoading.classList.add('hidden');
    showQueryView();
    updateQueryUI();
    queryInput.focus();
}

function updateQueryUI() {
    var isNote = state.cardType === 'note';
    submitQueryBtn.textContent = isNote ? 'Save Note' : 'Ask AI';
    queryInput.placeholder = isNote ? 'Write your note here...' : 'What would you like to ask about this?';
    queryLoading.classList.add('hidden');
    if (simplifyBtn) simplifyBtn.style.display = isNote ? 'block' : 'none';
}

typeButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
        typeButtons.forEach(function(b) { b.classList.remove('active'); });
        btn.classList.add('active');
        state.cardType = btn.dataset.type;
        updateQueryUI();
    });
});

// ── Simplify Note ─────────────────────────────────────────────────────────────
if (simplifyBtn) {
    simplifyBtn.addEventListener('click', async function() {
        var noteText = queryInput.value.trim();
        if (!noteText) return;
        simplifyBtn.disabled = true;
        simplifyBtn.textContent = 'Simplifying...';
        try {
            var res = await fetch(API + '/simplify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ note_text: noteText })
            });
            var data = await res.json();
            queryInput.value = data.simplified;
        } catch (err) { console.error(err); }
        finally {
            simplifyBtn.disabled = false;
            simplifyBtn.textContent = '✨ Simplify Note';
        }
    });
}

// ── Submit Query / Save Note ──────────────────────────────────────────────────
submitQueryBtn.addEventListener('click', submitQuery);
queryInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitQuery(); }
});

async function submitQuery() {
    var question = queryInput.value.trim();
    if (!question) return;

    if (state.cardType === 'note') {
        submitQueryBtn.disabled = true;
        submitQueryBtn.textContent = 'Saving...';
        queryLoading.classList.remove('hidden');
        queryLoading.textContent = 'Saving note...';
        try {
            var noteRes = await fetch(API + '/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pdf_id: state.pdfId, section_id: state.selectedSectionId,
                    selected_text: state.selectedText, page_number: state.currentPage,
                    question: question, card_type: 'note'
                })
            });
            var noteData = await noteRes.json();
            state.currentCardId = noteData.card.id;
            addCardToPanel(noteData.card);
            showSectionView();
        } catch (err) { console.error(err); }
        finally {
            submitQueryBtn.disabled = false;
            submitQueryBtn.textContent = 'Save Note';
            queryLoading.classList.add('hidden');
        }
        return;
    }

    submitQueryBtn.disabled = true;
    queryLoading.classList.remove('hidden');
    queryLoading.textContent = 'Thinking...';
    try {
        var res = await fetch(API + '/query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pdf_id: state.pdfId, section_id: state.selectedSectionId,
                selected_text: state.selectedText, page_number: state.currentPage,
                question: question, card_type: state.cardType
            })
        });
        var data = await res.json();
        state.currentCardId = data.card.id;
        addCardToPanel(data.card);
        openThreadWithMessages(data.card, data.messages);
    } catch (err) {
        queryLoading.textContent = 'Error. Please try again.';
        console.error(err);
    } finally {
        submitQueryBtn.disabled = false;
        queryLoading.classList.add('hidden');
    }
}

// ── Thread View ───────────────────────────────────────────────────────────────
function openThread(card) {
    state.currentCardId = card.id;
    fetch(API + '/thread/' + card.id)
        .then(function(r) { return r.json(); })
        .then(function(data) { openThreadWithMessages(data.card, data.messages); });
}

function openThreadWithMessages(card, messages) {
    selectedTextDisplay.textContent = '"' + card.selected_text + '"';
    threadCardType.textContent = card.card_type === 'question' ? 'Question' : 'Note';
    threadMessages.innerHTML = '';
    messages.forEach(function(msg) { appendMessage(msg.role, msg.content, card.card_type); });
    showThreadView();
    followUpInput.value = '';
    var threadInput = document.querySelector('.thread-input');
    if (threadInput) threadInput.style.display = 'none';
    var editArea = document.getElementById('note-edit-area');
    if (editArea) editArea.remove();
    if (card.card_type === 'note') {
        var editDiv = document.createElement('div');
        editDiv.id = 'note-edit-area';
        editDiv.style.cssText = 'padding:12px;border-top:1px solid #2a2a2a;';
        editDiv.innerHTML = '<textarea id="note-edit-input" style="width:100%;background:#1e1e1e;border:1px solid #2a2a2a;border-radius:8px;color:#e8e8e8;padding:10px;font-size:0.85rem;resize:vertical;min-height:80px;font-family:inherit;box-sizing:border-box;" placeholder="Edit your note..."></textarea><div style="display:flex;gap:8px;margin-top:8px;"><button id="note-simplify-btn" style="flex:1;background:#1e1e1e;border:1px solid #2a2a2a;color:#e8e8e8;padding:8px;border-radius:8px;cursor:pointer;font-size:0.8rem;">✨ Simplify</button><button id="note-save-btn" style="flex:1;background:#6c63ff;border:none;color:white;padding:8px;border-radius:8px;cursor:pointer;font-size:0.8rem;font-weight:600;">Save Note</button></div>';
        threadMessages.parentElement.appendChild(editDiv);
        var noteInput = document.getElementById('note-edit-input');
        var currentNote = '';
        if (threadMessages.children.length > 0) {
            currentNote = threadMessages.children[0].textContent;
        }
        noteInput.value = currentNote;
        document.getElementById('note-simplify-btn').addEventListener('click', async function() {
            var txt = noteInput.value.trim();
            if (!txt) return;
            this.textContent = 'Simplifying...';
            this.disabled = true;
            try {
                var r = await fetch(API + '/simplify', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({note_text: txt})});
                var d = await r.json();
                noteInput.value = d.simplified;
            } catch(e) { console.error(e); }
            finally { this.textContent = '✨ Simplify'; this.disabled = false; }
        });
        document.getElementById('note-save-btn').addEventListener('click', async function() {
            var txt = noteInput.value.trim();
            if (!txt) return;
            this.textContent = 'Saving...';
            this.disabled = true;
            try {
                await fetch(API + '/message', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({card_id: card.id, question: txt})});
                threadMessages.innerHTML = '<div class="message message-user">' + txt + '</div>';
            } catch(e) { console.error(e); }
            finally { this.textContent = 'Save Note'; this.disabled = false; }
        });
    } else {
        if (threadInput) threadInput.style.display = 'flex';
    }
    threadMessages.scrollTop = threadMessages.scrollHeight;
}

function appendMessage(role, content, cardType) {
    var msgEl = document.createElement('div');
    msgEl.className = 'message message-' + role;
    if (role === 'assistant' && cardType !== 'note') {
        var contentEl = document.createElement('div');
        contentEl.className = 'message-content';
        contentEl.innerHTML = marked.parse(content);
        msgEl.appendChild(contentEl);
        var convertBtn = document.createElement('button');
        convertBtn.className = 'convert-to-note-btn';
        convertBtn.textContent = '📝 Convert to Note';
        convertBtn.addEventListener('click', function() { convertToNote(content); });
        msgEl.appendChild(convertBtn);
    } else {
        msgEl.textContent = content;
    }
    threadMessages.appendChild(msgEl);
    threadMessages.scrollTop = threadMessages.scrollHeight;
}

function convertToNote(content) {
    typeButtons.forEach(function(b) {
        b.classList.remove('active');
        if (b.dataset.type === 'note') b.classList.add('active');
    });
    state.cardType = 'note';
    openQueryView(content);
}

// ── Follow-up Messages ────────────────────────────────────────────────────────
sendFollowupBtn.addEventListener('click', sendFollowup);
followUpInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendFollowup(); }
});

async function sendFollowup() {
    var question = followUpInput.value.trim();
    if (!question || !state.currentCardId) return;
    appendMessage('user', question);
    followUpInput.value = '';
    sendFollowupBtn.disabled = true;
    var loadingEl = document.createElement('div');
    loadingEl.className = 'message message-assistant';
    loadingEl.textContent = 'Thinking...';
    threadMessages.appendChild(loadingEl);
    threadMessages.scrollTop = threadMessages.scrollHeight;
    try {
        var res = await fetch(API + '/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_id: state.currentCardId, question: question })
        });
        var data = await res.json();
        threadMessages.removeChild(loadingEl);
        appendMessage('assistant', data.messages[1].content, 'question');
    } catch (err) {
        loadingEl.textContent = 'Error. Please try again.';
    } finally {
        sendFollowupBtn.disabled = false;
        threadMessages.scrollTop = threadMessages.scrollHeight;
    }
}