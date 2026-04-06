const API = 'http://127.0.0.1:8000';
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

let state = {
    pdfId: null,
    totalPages: 0,
    currentPage: 1,
    sections: [],
    currentCardId: null,
    selectedText: '',
    selectedSectionId: null,
    cardType: 'question',
    pdfDoc: null,
    scale: 1.5,
    isDrawing: false,
    startX: 0,
    startY: 0
};

const uploadScreen = document.getElementById('upload-screen');
const app = document.getElementById('app');
const pdfInput = document.getElementById('pdf-input');
const uploadStatus = document.getElementById('upload-status');
const pageInfo = document.getElementById('page-info');
const pdfNameEl = document.getElementById('pdf-name');
const panelPdfName = document.getElementById('panel-pdf-name');
const prevBtn = document.getElementById('prev-page');
const nextBtn = document.getElementById('next-page');
const sectionsList = document.getElementById('sections-list');
const sectionView = document.getElementById('section-view');
const threadView = document.getElementById('thread-view');
const queryView = document.getElementById('query-view');
const backBtn = document.getElementById('back-btn');
const threadMessages = document.getElementById('thread-messages');
const selectedTextDisplay = document.getElementById('selected-text-display');
const followUpInput = document.getElementById('follow-up-input');
const sendFollowupBtn = document.getElementById('send-followup-btn');
const threadCardType = document.getElementById('thread-card-type');
const cancelQueryBtn = document.getElementById('cancel-query-btn');
const querySelectedText = document.getElementById('query-selected-text');
const queryInput = document.getElementById('query-input');
const submitQueryBtn = document.getElementById('submit-query-btn');
const queryLoading = document.getElementById('query-loading');
const typeButtons = document.querySelectorAll('.type-btn');

// ── Upload ──────────────────────────────────────────────
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

        uploadScreen.classList.add('hidden');
        app.classList.remove('hidden');

        renderPage(1);
        renderSections();

    } catch (err) {
        uploadStatus.textContent = 'Error uploading PDF. Please try again.';
        console.error(err);
    }
});

// ── PDF Rendering ───────────────────────────────────────
async function renderPage(pageNum) {
    state.currentPage = pageNum;
    pageInfo.textContent = 'Page ' + pageNum + ' of ' + state.totalPages;
    prevBtn.disabled = pageNum <= 1;
    nextBtn.disabled = pageNum >= state.totalPages;

    var page = await state.pdfDoc.getPage(pageNum);
    var viewport = page.getViewport({ scale: state.scale });

    var container = document.getElementById('pdf-container');
    container.innerHTML = '';
    container.style.position = 'relative';
    container.style.overflow = 'auto';

    var wrapper = document.createElement('div');
    wrapper.style.position = 'relative';
    wrapper.style.width = viewport.width + 'px';
    wrapper.style.margin = '20px auto';

    var canvas = document.createElement('canvas');
    canvas.id = 'pdf-canvas';
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.display = 'block';

    var overlay = document.createElement('canvas');
    overlay.id = 'pdf-overlay';
    overlay.width = viewport.width;
    overlay.height = viewport.height;
    overlay.style.position = 'absolute';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.cursor = 'crosshair';
    overlay.style.zIndex = '10';

    wrapper.appendChild(canvas);
    wrapper.appendChild(overlay);
    container.appendChild(wrapper);

    await page.render({ canvasContext: canvas.getContext('2d'), viewport: viewport }).promise;

    setupDrawing(overlay);
}

prevBtn.addEventListener('click', function() {
    if (state.currentPage > 1) renderPage(state.currentPage - 1);
});

nextBtn.addEventListener('click', function() {
    if (state.currentPage < state.totalPages) renderPage(state.currentPage + 1);
});

// ── Box Drawing ─────────────────────────────────────────
function setupDrawing(overlay) {
    var ctx = overlay.getContext('2d');
    var startX, startY;

    overlay.addEventListener('mousedown', function(e) {
        var bounds = overlay.getBoundingClientRect();
        state.isDrawing = true;
        startX = e.clientX - bounds.left;
        startY = e.clientY - bounds.top;
    });

    overlay.addEventListener('mousemove', function(e) {
        if (!state.isDrawing) return;
        var bounds = overlay.getBoundingClientRect();
        var currentX = e.clientX - bounds.left;
        var currentY = e.clientY - bounds.top;
        var w = currentX - startX;
        var h = currentY - startY;

        ctx.clearRect(0, 0, overlay.width, overlay.height);
        ctx.strokeStyle = '#6c63ff';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 3]);
        ctx.fillStyle = 'rgba(108, 99, 255, 0.1)';
        ctx.fillRect(startX, startY, w, h);
        ctx.strokeRect(startX, startY, w, h);
    });

    overlay.addEventListener('mouseup', function(e) {
        if (!state.isDrawing) return;
        state.isDrawing = false;

        var bounds = overlay.getBoundingClientRect();
        var endX = e.clientX - bounds.left;
        var endY = e.clientY - bounds.top;
        var width = Math.abs(endX - startX);
        var height = Math.abs(endY - startY);

        if (width < 10 || height < 10) {
            ctx.clearRect(0, 0, overlay.width, overlay.height);
            return;
        }

        var selection = window.getSelection();
        var selectedText = selection ? selection.toString().trim() : '';
        state.selectedText = selectedText.length > 0 ? selectedText : '[Selected area on page ' + state.currentPage + ']';
        state.selectedSectionId = getSectionForPage(state.currentPage);

        openQueryView();
    });
}

// ── Section Lookup ──────────────────────────────────────
function getSectionForPage(pageNum) {
    for (var i = 0; i < state.sections.length; i++) {
        var s = state.sections[i];
        if (pageNum >= s.page_start && pageNum <= s.page_end) {
            return s.id;
        }
    }
    return state.sections.length > 0 ? state.sections[0].id : null;
}

// ── Render Sections ─────────────────────────────────────
function renderSections() {
    sectionsList.innerHTML = '';
    state.sections.forEach(function(section) {
        var sectionEl = document.createElement('div');
        sectionEl.className = 'section-item';

        var titleEl = document.createElement('div');
        titleEl.className = 'section-title';
        titleEl.innerHTML = '<span>' + section.title + '</span><span class="section-pages">pp. ' + section.page_start + '-' + section.page_end + '</span>';
        titleEl.addEventListener('click', function() { renderPage(section.page_start); });

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
    cardEl.innerHTML = '<div class="card-title">' + card.title + '</div><div class="card-meta">' + (card.card_type === 'question' ? '?' : 'N') + ' p.' + card.page_number + '</div>';
    cardEl.addEventListener('click', function() { openThread(card); });
    container.appendChild(cardEl);
}

function addCardToPanel(card) {
    var container = document.getElementById('cards-' + card.section_id);
    if (container) renderCard(card, container);
}

// ── Panel States ────────────────────────────────────────
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

// ── Query View ──────────────────────────────────────────
function openQueryView() {
    querySelectedText.textContent = '"' + state.selectedText + '"';
    queryInput.value = '';
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
}

typeButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
        typeButtons.forEach(function(b) { b.classList.remove('active'); });
        btn.classList.add('active');
        state.cardType = btn.dataset.type;
        updateQueryUI();
    });
});

submitQueryBtn.addEventListener('click', submitQuery);
queryInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitQuery(); }
});

async function submitQuery() {
    var question = queryInput.value.trim();
    if (!question) return;

    if (state.cardType === 'note') {
        submitQueryBtn.disabled = true;
        try {
            var noteRes = await fetch(API + '/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    pdf_id: state.pdfId,
                    section_id: state.selectedSectionId,
                    selected_text: state.selectedText,
                    page_number: state.currentPage,
                    question: question,
                    card_type: 'note'
                })
            });
            var noteData = await noteRes.json();
            state.currentCardId = noteData.card.id;
            addCardToPanel(noteData.card);
            showSectionView();
        } catch (err) {
            console.error(err);
        } finally {
            submitQueryBtn.disabled = false;
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
                pdf_id: state.pdfId,
                section_id: state.selectedSectionId,
                selected_text: state.selectedText,
                page_number: state.currentPage,
                question: question,
                card_type: state.cardType
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

// ── Thread View ─────────────────────────────────────────
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
    messages.forEach(function(msg) { appendMessage(msg.role, msg.content); });
    showThreadView();
    followUpInput.value = '';
    threadMessages.scrollTop = threadMessages.scrollHeight;
}

function appendMessage(role, content) {
    var msgEl = document.createElement('div');
    msgEl.className = 'message message-' + role;
    msgEl.textContent = content;
    threadMessages.appendChild(msgEl);
    threadMessages.scrollTop = threadMessages.scrollHeight;
}

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

    var loadingMsg = document.createElement('div');
    loadingMsg.className = 'message message-assistant';
    loadingMsg.textContent = 'Thinking...';
    threadMessages.appendChild(loadingMsg);

    try {
        var res = await fetch(API + '/message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ card_id: state.currentCardId, question: question })
        });
        var data = await res.json();
        loadingMsg.textContent = data.messages[1].content;
    } catch (err) {
        loadingMsg.textContent = 'Error. Please try again.';
    } finally {
        sendFollowupBtn.disabled = false;
        threadMessages.scrollTop = threadMessages.scrollHeight;
    }
}
