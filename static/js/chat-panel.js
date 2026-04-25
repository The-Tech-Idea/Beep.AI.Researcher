/**
 * AI Chat Panel - Collapsible chat interface
 * Works with Beep.AI.Server middleware
 * Updated for SPA shell layout
 */
(function () {
    'use strict';

    // DOM Elements — support both old and new IDs
    const panel = document.getElementById('chat-panel');
    const closeBtn = document.getElementById('chat-panel-close');
    const messagesContainer = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const statusDot = document.getElementById('chat-status-dot');
    const clearBtn = document.getElementById('chat-clear-btn');
    const quickPromptButtons = document.querySelectorAll('.chat-option-btn');

    if (!panel) return;

    // State
    let isOpen = false;
    let isConnected = false;
    let isSending = false;
    let messages = [];
    let sessionId = null;
    const projectId = (function () {
        // In SPA mode, use the project from workspace controller
        if (window.BeepSPA?.getCurrentProject) return window.BeepSPA.getCurrentProject();
        const path = window.location.pathname || '';
        const match = path.match(/\/researcher\/projects\/(\d+)/) || path.match(/\/projects\/(\d+)/);
        return match ? match[1] : null;
    })();
    const chatEndpoint = projectId ? `/projects/${projectId}/chat` : '/api/chat';
    const chatMode = projectId ? 'rag' : 'local';

    // Load saved state
    const savedMessages = localStorage.getItem('researcher_chat_messages');
    if (savedMessages) {
        try {
            messages = JSON.parse(savedMessages);
            renderMessages();
        } catch (e) {
            messages = [];
        }
    }

    // Toggle panel
    function togglePanel() {
        isOpen = !isOpen;
        panel.classList.toggle('open', isOpen);

        if (isOpen) {
            chatInput?.focus();
            scrollToBottom();
        }
    }

    // Close button
    closeBtn?.addEventListener('click', () => {
        isOpen = false;
        panel.classList.remove('open');
    });

    // Close on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isOpen) {
            togglePanel();
        }
    });

    // Open from any trigger
    document.querySelectorAll('[data-open-chat-panel]').forEach((el) => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            if (!isOpen) togglePanel();
        });
    });

    // Render messages
    function renderMessages() {
        if (!messagesContainer) return;

        if (messages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="chat-message system">
                    <i class="bi bi-robot"></i> Hi! I'm your AI research assistant. Ask me anything about your projects or documents.
                </div>
            `;
            return;
        }

        messagesContainer.innerHTML = messages.map(msg => `
            <div class="chat-message ${msg.role}">
                ${escapeHtml(msg.content)}
            </div>
        `).join('');

        scrollToBottom();
    }

    function scrollToBottom() {
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function saveMessages() {
        localStorage.setItem('researcher_chat_messages', JSON.stringify(messages.slice(-50)));
    }

    // Show typing indicator
    function showTyping() {
        const typing = document.createElement('div');
        typing.className = 'chat-typing';
        typing.id = 'chat-typing';
        typing.innerHTML = '<span></span><span></span><span></span>';
        messagesContainer?.appendChild(typing);
        scrollToBottom();
    }

    function hideTyping() {
        document.getElementById('chat-typing')?.remove();
    }

    // Add message
    function addMessage(role, content) {
        messages.push({ role, content, timestamp: Date.now() });
        saveMessages();
        renderMessages();
    }

    // Send message
    async function sendMessage(content) {
        if (!content.trim() || isSending) return;

        isSending = true;
        sendBtn.disabled = true;

        // Add user message
        addMessage('user', content);
        chatInput.value = '';
        autoResizeInput();

        // Show typing indicator
        showTyping();

        try {
            const response = await fetch(chatEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: content,
                    session_id: sessionId,
                    mode: chatMode
                })
            });

            const data = await response.json();

            hideTyping();

            if (data.success && data.reply) {
                addMessage('assistant', data.reply);
                if (data.session_id) {
                    sessionId = data.session_id;
                }
                isConnected = true;
                updateStatus(true);
            } else if (data.error) {
                addMessage('system', `Error: ${data.error}`);
                updateStatus(false);
            }
        } catch (error) {
            hideTyping();
            addMessage('system', `Connection error: ${error.message}`);
            isConnected = false;
            updateStatus(false);
        } finally {
            isSending = false;
            sendBtn.disabled = false;
            chatInput?.focus();
        }
    }

    // Form submit
    chatForm?.addEventListener('submit', (e) => {
        e.preventDefault();
        sendMessage(chatInput?.value || '');
    });

    // Auto-resize textarea
    function autoResizeInput() {
        if (!chatInput) return;
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    }

    chatInput?.addEventListener('input', autoResizeInput);

    // Enter to send (shift+enter for newline)
    chatInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage(chatInput.value);
        }
    });

    // Clear chat
    clearBtn?.addEventListener('click', () => {
        messages = [];
        sessionId = null;
        saveMessages();
        renderMessages();
    });

    // Quick prompt buttons
    quickPromptButtons.forEach((btn) => {
        btn.addEventListener('click', () => {
            const prompt = btn.getAttribute('data-prompt') || '';
            if (!prompt) return;
            chatInput.value = prompt;
            autoResizeInput();
            sendMessage(prompt);
        });
    });

    // Update connection status
    function updateStatus(connected) {
        isConnected = connected;
        if (statusDot) {
            statusDot.classList.toggle('connected', connected);
            statusDot.classList.toggle('error', !connected);
        }
    }

    // Check AI server status
    async function checkStatus() {
        try {
            const response = await fetch('/check-ai-server');
            const status = await response.json();
            updateStatus(status.token_valid || false);
        } catch (e) {
            updateStatus(false);
        }
    }

    // Initialize
    renderMessages();
    checkStatus();

    // Auto-open if URL has openChat=1
    const params = new URLSearchParams(window.location.search);
    if (params.get('openChat') === '1') {
        togglePanel();
    }

    // Export toggle and messaging for external callers
    window.BeepChat = {
        toggle: togglePanel,
        open: function () { if (!isOpen) togglePanel(); },
        send: function (text) {
            if (!isOpen) togglePanel();
            sendMessage(text);
        }
    };

})();
