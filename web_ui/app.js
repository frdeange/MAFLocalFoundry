/**
 * Travel Planner — Web UI Application Logic
 * ==========================================
 * Handles user interaction, SSE streaming from the API,
 * message rendering, and localStorage history persistence.
 */

// ──────────────────────────────────────────────────────────────
// Constants
// ──────────────────────────────────────────────────────────────

const API_BASE = '';  // Same origin — Nginx proxies /api/ to FastAPI
const HISTORY_KEY = 'travel-planner-history';
const MAX_HISTORY = 50;

// Agent visual configuration
const AGENT_CONFIG = {
    Researcher:      { icon: '🔍', cssClass: 'researcher',      label: 'Researcher' },
    WeatherAnalyst:  { icon: '🌤️', cssClass: 'weatheranalyst',  label: 'Weather Analyst' },
    Planner:         { icon: '📋', cssClass: 'planner',          label: 'Planner' },
};

// ──────────────────────────────────────────────────────────────
// DOM Elements
// ──────────────────────────────────────────────────────────────

const elements = {
    form:            document.getElementById('query-form'),
    input:           document.getElementById('query-input'),
    submitBtn:       document.getElementById('submit-btn'),
    messages:        document.getElementById('messages'),
    messagesContainer: document.getElementById('messages-container'),
    agentProgress:   document.getElementById('agent-progress'),
    progressAgent:   document.getElementById('progress-agent-name'),
    connectionStatus: document.getElementById('connection-status'),
    historyList:     document.getElementById('history-list'),
    clearHistoryBtn: document.getElementById('clear-history-btn'),
    toggleSidebar:   document.getElementById('toggle-sidebar-btn'),
    sidebar:         document.getElementById('sidebar'),
};


// ──────────────────────────────────────────────────────────────
// State
// ──────────────────────────────────────────────────────────────

let isProcessing = false;
let currentEventSource = null;
let completedAgents = [];


// ──────────────────────────────────────────────────────────────
// Initialization
// ──────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    setupEventListeners();
    autoResizeTextarea();
});


function setupEventListeners() {
    // Form submission
    elements.form.addEventListener('submit', (e) => {
        e.preventDefault();
        handleSubmit();
    });

    // Enter to send, Shift+Enter for newline
    elements.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    });

    // Auto-resize textarea
    elements.input.addEventListener('input', autoResizeTextarea);

    // Sidebar toggle
    elements.toggleSidebar.addEventListener('click', () => {
        elements.sidebar.classList.toggle('collapsed');
        elements.sidebar.classList.toggle('open');
    });

    // Clear history
    elements.clearHistoryBtn.addEventListener('click', () => {
        if (confirm('Clear all history?')) {
            localStorage.removeItem(HISTORY_KEY);
            elements.historyList.innerHTML = '';
        }
    });
}


function autoResizeTextarea() {
    elements.input.style.height = 'auto';
    elements.input.style.height = Math.min(elements.input.scrollHeight, 120) + 'px';
}


// ──────────────────────────────────────────────────────────────
// Query Submission
// ──────────────────────────────────────────────────────────────

async function handleSubmit() {
    const query = elements.input.value.trim();
    if (!query || isProcessing) return;

    // Start telemetry span
    const span = window.TravelTelemetry?.startSpan('user.submit_query', { query });

    isProcessing = true;
    elements.submitBtn.disabled = true;
    elements.input.value = '';
    autoResizeTextarea();

    // Add user message to chat
    addMessage({ role: 'user', text: query });

    // Reset agent tracking
    completedAgents = [];

    // Update status
    setStatus('busy', 'Processing...');

    // Track current session messages for history
    const sessionMessages = [];

    try {
        await streamWorkflow(query, sessionMessages);

        // Save to history
        saveToHistory(query, sessionMessages);

    } catch (error) {
        addMessage({ role: 'error', text: `Connection error: ${error.message}` });
        setStatus('error', 'Error');
    } finally {
        isProcessing = false;
        elements.submitBtn.disabled = false;
        hideProgress();
        setStatus('ready', 'Ready');
        elements.input.focus();
        if (span) span.end();
    }
}


// ──────────────────────────────────────────────────────────────
// SSE Streaming
// ──────────────────────────────────────────────────────────────

function streamWorkflow(query, sessionMessages) {
    return new Promise((resolve, reject) => {
        const streamSpan = window.TravelTelemetry?.startSpan('ui.stream_started', { query });

        // Use fetch + ReadableStream for POST-based SSE
        // (EventSource only supports GET)
        fetch(`${API_BASE}/api/plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function processStream() {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        if (streamSpan) streamSpan.end();
                        resolve();
                        return;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop(); // Keep incomplete line in buffer

                    let eventType = null;
                    for (const line of lines) {
                        if (line.startsWith('event:')) {
                            eventType = line.substring(6).trim();
                        } else if (line.startsWith('data:')) {
                            const dataStr = line.substring(5).trim();
                            if (dataStr) {
                                try {
                                    const data = JSON.parse(dataStr);
                                    handleSSEEvent(eventType || 'message', data, sessionMessages);
                                } catch (e) {
                                    console.warn('Failed to parse SSE data:', dataStr);
                                }
                            }
                            eventType = null; // Reset after consuming
                        }
                    }

                    processStream();
                }).catch(error => {
                    if (streamSpan) streamSpan.end();
                    reject(error);
                });
            }

            processStream();
        })
        .catch(error => {
            if (streamSpan) streamSpan.end();
            reject(error);
        });
    });
}


function handleSSEEvent(eventType, data, sessionMessages) {
    const AGENT_SEQUENCE = ['Researcher', 'WeatherAnalyst', 'Planner'];
    const totalAgents = AGENT_SEQUENCE.length;

    switch (eventType) {
        case 'agent_started': {
            const stepIndex = completedAgents.length + 1;
            showProgress(data.agent, stepIndex, totalAgents);
            break;
        }

        case 'agent_completed':
            if (data.agent && !completedAgents.includes(data.agent)) {
                completedAgents.push(data.agent);
            }
            // Don't hide progress — wait for the message to arrive
            break;

        case 'message': {
            // Hide progress when the agent's message arrives
            hideProgress();

            const agentMsg = {
                role: 'agent',
                author: data.author,
                text: data.text,
            };
            addMessage(agentMsg);
            sessionMessages.push(agentMsg);

            // Telemetry: agent message rendered
            window.TravelTelemetry?.startSpan('ui.agent_message_rendered', {
                agent: data.author,
                step: completedAgents.length,
            })?.end();
            break;
        }

        case 'output':
            hideProgress();
            setStatus('ready', `Done in ${data.duration_seconds}s`);
            window.TravelTelemetry?.startSpan('ui.stream_complete', {
                duration: data.duration_seconds,
                agent_count: data.agent_count,
            })?.end();
            break;

        case 'error':
            hideProgress();
            addMessage({ role: 'error', text: `${data.type}: ${data.error}` });
            setStatus('error', 'Error');
            break;

        case 'done':
            // Stream complete
            break;

        case 'status':
            // Optional: could show in UI
            console.log('Workflow status:', data);
            break;

        default:
            console.log('Unknown event:', eventType, data);
    }
}


// ──────────────────────────────────────────────────────────────
// Message Rendering
// ──────────────────────────────────────────────────────────────

function addMessage({ role, text, author }) {
    const messageEl = document.createElement('div');

    if (role === 'user') {
        messageEl.className = 'message user-message';
        messageEl.innerHTML = `
            <div class="message-header">
                <span class="agent-icon">👤</span>
                <span class="agent-name user">You</span>
            </div>
            <div class="message-content">${escapeHtml(text)}</div>
        `;
    } else if (role === 'agent') {
        const config = getAgentConfig(author);
        messageEl.className = `message agent-message ${config.cssClass}`;
        messageEl.innerHTML = `
            <div class="message-header">
                <span class="agent-icon">${config.icon}</span>
                <span class="agent-name ${config.cssClass}">${config.label}</span>
            </div>
            <div class="message-content">${formatAgentText(text)}</div>
        `;
    } else if (role === 'error') {
        messageEl.className = 'message error-message';
        messageEl.innerHTML = `
            <div class="message-header">
                <span class="agent-icon">⚠️</span>
                <span class="agent-name" style="color: var(--error-text)">Error</span>
            </div>
            <div class="message-content">${escapeHtml(text)}</div>
        `;
    }

    elements.messages.appendChild(messageEl);
    scrollToBottom();
}


function getAgentConfig(authorName) {
    // Match agent name from the author field
    for (const [key, config] of Object.entries(AGENT_CONFIG)) {
        if (authorName && authorName.toLowerCase().includes(key.toLowerCase())) {
            return config;
        }
    }
    // Fallback for unknown agents
    return { icon: '🤖', cssClass: 'researcher', label: authorName || 'Agent' };
}


function formatAgentText(text) {
    if (!text) return '';
    // Basic markdown-like formatting
    let html = escapeHtml(text);
    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Italic: *text*
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    return html;
}


function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


function scrollToBottom() {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}


// ──────────────────────────────────────────────────────────────
// Progress Indicator
// ──────────────────────────────────────────────────────────────

function showProgress(agentName, step, total) {
    const config = getAgentConfig(agentName);
    elements.progressAgent.textContent = `${config.icon} ${config.label} (step ${step}/${total})`;
    elements.agentProgress.style.display = 'block';
    setStatus('busy', `${config.label} working... (${step}/${total})`);
}


function hideProgress() {
    elements.agentProgress.style.display = 'none';
}


// ──────────────────────────────────────────────────────────────
// Connection Status
// ──────────────────────────────────────────────────────────────

function setStatus(state, text) {
    const dot = elements.connectionStatus.querySelector('.status-dot');
    const label = elements.connectionStatus.querySelector('.status-text');

    dot.className = 'status-dot';
    if (state === 'busy') dot.classList.add('busy');
    if (state === 'error') dot.classList.add('error');

    label.textContent = text;
}


// ──────────────────────────────────────────────────────────────
// History (localStorage)
// ──────────────────────────────────────────────────────────────

function getHistory() {
    try {
        return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    } catch {
        return [];
    }
}


function saveToHistory(query, messages) {
    const history = getHistory();
    history.unshift({
        id: Date.now(),
        query,
        messages,
        timestamp: new Date().toISOString(),
    });

    // Keep only the last N entries
    if (history.length > MAX_HISTORY) {
        history.length = MAX_HISTORY;
    }

    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
    loadHistory();
}


function loadHistory() {
    const history = getHistory();
    elements.historyList.innerHTML = '';

    for (const entry of history) {
        const li = document.createElement('li');
        li.className = 'history-item';
        li.textContent = entry.query;
        li.title = `${entry.query}\n${new Date(entry.timestamp).toLocaleString()}`;
        li.addEventListener('click', () => replayHistory(entry));
        elements.historyList.appendChild(li);
    }
}


function replayHistory(entry) {
    // Load the query into the input for re-execution
    elements.input.value = entry.query;
    autoResizeTextarea();
    elements.input.focus();
}
