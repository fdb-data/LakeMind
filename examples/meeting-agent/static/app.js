const recordBtn = document.getElementById('record-btn');
const statusText = document.getElementById('status-text');
const timerEl = document.getElementById('timer');
const chunkCount = document.getElementById('chunk-count');
const transcriptEl = document.getElementById('transcript');
const minutesEl = document.getElementById('minutes');
const knowledgeEl = document.getElementById('knowledge');
const knowledgeCount = document.getElementById('knowledge-count');
const searchBtn = document.getElementById('search-btn');
const searchView = document.getElementById('search-view');
const mainView = document.getElementById('main-view');
const backBtn = document.getElementById('back-btn');
const doSearchBtn = document.getElementById('do-search');
const searchQuery = document.getElementById('search-query');
const searchResults = document.getElementById('search-results');

let recording = false;
let audioStream = null;
let mediaRecorder = null;
let meetingId = null;
let chunkNum = 0;
let startTime = 0;
let timerInterval = null;
let chunkTimer = null;
let sseSource = null;
let knowledgeList = [];
let pendingChunks = [];

const CHUNK_MS = 10000;

function formatTime(ms) {
    const s = Math.floor(ms / 1000);
    return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

function connectSSE() {
    sseSource = new EventSource('/api/stream');
    sseSource.addEventListener('transcript', (e) => {
        const data = JSON.parse(e.data);
        const div = document.createElement('div');
        div.className = 'entry';
        div.textContent = `[${data.timestamp}] ${data.text}`;
        transcriptEl.appendChild(div);
        transcriptEl.scrollTop = transcriptEl.scrollHeight;
    });
    sseSource.addEventListener('minutes', (e) => {
        const data = JSON.parse(e.data);
        minutesEl.textContent = data.minutes;
    });
    sseSource.addEventListener('knowledge', (e) => {
        const data = JSON.parse(e.data);
        data.concepts.forEach(c => {
            knowledgeList.push(c);
            const div = document.createElement('div');
            div.className = 'entry';
            const title = document.createElement('div');
            title.className = 'title';
            title.textContent = c.title;
            const body = document.createElement('div');
            body.textContent = c.body || '';
            div.appendChild(title);
            div.appendChild(body);
            knowledgeEl.appendChild(div);
        });
        knowledgeCount.textContent = `(${knowledgeList.length})`;
    });
    sseSource.addEventListener('status', (e) => {
        const data = JSON.parse(e.data);
        chunkCount.textContent = `chunks: ${data.chunks}`;
    });
}

function startMediaRecorder() {
    if (!audioStream || !recording) return;
    mediaRecorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm' });
    const chunks = [];
    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
        if (chunks.length > 0) {
            const blob = new Blob(chunks, { type: 'audio/webm' });
            pendingChunks.push(blob);
        }
        if (recording) {
            startMediaRecorder();
        }
    };
    mediaRecorder.start();
    setTimeout(() => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
    }, CHUNK_MS);
}

async function sendPendingChunks() {
    while (pendingChunks.length > 0) {
        const blob = pendingChunks.shift();
        chunkNum++;
        try {
            await fetch(`/api/chunk?meeting_id=${meetingId}`, {
                method: 'POST',
                body: blob,
            });
        } catch (e) {
            console.error('chunk send failed:', e);
        }
    }
}

async function startRecording() {
    const title = document.getElementById('meeting-title').value;
    const participants = document.getElementById('participants').value;

    const resp = await fetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({title, participants}),
    });
    const data = await resp.json();
    meetingId = data.meeting_id;

    audioStream = await navigator.mediaDevices.getUserMedia({audio: true});

    recording = true;
    recordBtn.classList.add('recording');
    recordBtn.textContent = '⏹ 停止';
    statusText.textContent = '状态: 录音中';
    startTime = Date.now();
    chunkNum = 0;
    pendingChunks = [];

    timerInterval = setInterval(() => {
        timerEl.textContent = formatTime(Date.now() - startTime);
    }, 1000);

    connectSSE();
    startMediaRecorder();

    chunkTimer = setInterval(sendPendingChunks, 2000);
}

async function stopRecording() {
    recording = false;
    clearInterval(timerInterval);
    clearInterval(chunkTimer);

    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
    }

    await new Promise(r => setTimeout(r, 1500));
    await sendPendingChunks();

    if (audioStream) audioStream.getTracks().forEach(t => t.stop());

    recordBtn.classList.remove('recording');
    recordBtn.textContent = '● 录音';
    statusText.textContent = '状态: 处理中...';

    const resp = await fetch('/api/stop', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({meeting_id: meetingId}),
    });
    const data = await resp.json();
    statusText.textContent = `状态: 已结束 (时长 ${data.duration}s, ${data.chunks} chunks)`;
}

recordBtn.addEventListener('click', () => {
    if (recording) stopRecording();
    else startRecording();
});

searchBtn.addEventListener('click', () => {
    mainView.classList.add('hidden');
    searchView.classList.remove('hidden');
});

backBtn.addEventListener('click', () => {
    searchView.classList.add('hidden');
    mainView.classList.remove('hidden');
});

doSearchBtn.addEventListener('click', async () => {
    const query = searchQuery.value.trim();
    if (!query) return;
    searchResults.innerHTML = '搜索中...';
    const resp = await fetch(`/api/search?query=${encodeURIComponent(query)}&top_k=10`);
    const data = await resp.json();
    const hits = data.hits || [];
    if (hits.length === 0) {
        searchResults.innerHTML = '<p>无结果</p>';
        return;
    }
    searchResults.innerHTML = `<p>结果 (${hits.length} 条):</p>`;
    hits.forEach(h => {
        const div = document.createElement('div');
        div.className = 'result-item';
        const title = document.createElement('div');
        title.className = 'title';
        title.textContent = h.title || h.content?.substring(0, 50) || '(无标题)';
        const score = document.createElement('div');
        score.className = 'score';
        score.textContent = `score: ${h._distance ?? '?'}`;
        const body = document.createElement('div');
        body.className = 'body';
        body.textContent = h.content || h.body || '';
        div.appendChild(title);
        div.appendChild(score);
        div.appendChild(body);
        searchResults.appendChild(div);
    });
});

searchQuery.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doSearchBtn.click();
});
