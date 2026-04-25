// project-search.js
document.addEventListener('DOMContentLoaded', function () {
    const i18nDataElement = document.getElementById('search-i18n-data');
    if (i18nDataElement) {
        try {
            window.SEARCH_I18N = JSON.parse(i18nDataElement.textContent);
        } catch (e) {
            console.error("Failed to parse SEARCH_I18N JSON:", e);
            window.SEARCH_I18N = {};
        }
    } else {
        window.SEARCH_I18N = {};
    }

    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const chatMessages = document.getElementById('chatMessages');
    const welcomeMessage = document.getElementById('welcomeMessage');
    const clearBtn = document.getElementById('clearChatBtn');

    if (!chatInput || !sendBtn || !chatMessages) return;

    chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 150) + 'px';
    });

    chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    sendBtn.addEventListener('click', sendMessage);

    if (clearBtn) {
        clearBtn.addEventListener('click', function () {
            if (confirm(window.SEARCH_I18N?.confirm_clear || "Clear chat history?")) {
                chatMessages.innerHTML = '';
                if (welcomeMessage) {
                    const welcomeClone = welcomeMessage.cloneNode(true);
                    welcomeClone.hidden = false;
                    chatMessages.appendChild(welcomeClone);
                }
            }
        });
    }

    // Global event delegation for dynamically inserted elements 
    // and elements that no longer use inline onclick=""
    document.addEventListener('click', function (e) {
        // Quick Question Chips
        if (e.target.classList.contains('ask-chip')) {
            chatInput.value = e.target.textContent;
            sendMessage();
            return;
        }

        // Document Source Links
        const sourceBtn = e.target.closest('.view-source-btn');
        if (sourceBtn) {
            const docId = sourceBtn.dataset.docId;
            const chunkId = sourceBtn.dataset.chunkId || '';
            if (!docId) return;
            const projectId = window.SEARCH_I18N?.projectId;
            if (!projectId) return;
            const params = new URLSearchParams();
            params.set('source_view', 'answer');
            if (chunkId) {
                params.set('highlight', chunkId);
            }
            window.open(`/researcher/projects/${projectId}/documents/${docId}/view?${params.toString()}`, '_blank');
        }
    });

    function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;
        if (welcomeMessage) welcomeMessage.hidden = true;

        const projectId = window.SEARCH_I18N?.projectId;
        if (!projectId) {
            appendMessage('assistant', 'Project ID not found.');
            return;
        }

        // ── Slash command interception ────────────────────────────────
        if (text.startsWith('/')) {
            appendMessage('user', text);
            chatInput.value = '';
            chatInput.style.height = 'auto';
            const typingId = showTyping();

            if (text.startsWith('/generate-flashcards')) {
                fetch(`/projects/${projectId}/flashcards`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ limit: 5 }),
                })
                    .then(r => r.json())
                    .then(data => {
                        hideTyping(typingId);
                        const cards = data.flashcards || [];
                        if (!cards.length) {
                            appendMessage('assistant', '⚠️ No flashcards could be generated. Make sure you have uploaded documents with text content.');
                            return;
                        }
                        let html = `✅ Generated **${cards.length}** flashcards!\n\n`;
                        cards.forEach((c, i) => {
                            html += `**${i + 1}. Q:** ${c.front}\n**A:** ${c.back}\n\n`;
                        });
                        html += `_Method: ${data.method || 'auto'}_`;
                        appendMessage('assistant', html);
                    })
                    .catch(e => { hideTyping(typingId); appendMessage('assistant', '❌ Error generating flashcards: ' + e.message); });
                return;
            }

            if (text.startsWith('/generate-quiz')) {
                const name = text.replace('/generate-quiz', '').trim() || 'Chat Quiz';
                fetch(`/projects/${projectId}/quiz`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name, limit: 5 }),
                })
                    .then(r => r.json())
                    .then(data => {
                        hideTyping(typingId);
                        if (!data.quiz_id) {
                            appendMessage('assistant', '⚠️ No quiz questions could be generated.');
                            return;
                        }
                        appendMessage('assistant',
                            `✅ Quiz "${data.name}" created with **${data.question_count}** questions!\n\n` +
                            `Go to the **Quizzes** page to take it, or ` +
                            `<a href="/researcher/projects/${projectId}/quizzes/${data.quiz_id}/take" data-spa-link>take it now</a>.` +
                            `\n\n_Method: ${data.method || 'auto'}_`
                        );
                    })
                    .catch(e => { hideTyping(typingId); appendMessage('assistant', '❌ Error generating quiz: ' + e.message); });
                return;
            }

            if (text.startsWith('/extract')) {
                hideTyping(typingId);
                appendMessage('assistant',
                    '📋 To run an extraction, go to the **Extraction** page:\n\n' +
                    '1. Create or select a schema\n' +
                    '2. Choose documents\n' +
                    '3. Click **Extract**\n\n' +
                    `<a href="/researcher/projects/${projectId}/extraction" data-spa-link>Open Extraction →</a>`
                );
                return;
            }

            // Unknown slash command — show help
            hideTyping(typingId);
            appendMessage('assistant',
                '📝 **Available commands:**\n\n' +
                '• `/generate-flashcards` — Generate 5 study flashcards from your documents\n' +
                '• `/generate-quiz [name]` — Generate a quiz with 5 MCQ questions\n' +
                '• `/extract` — Open the extraction workflow\n\n' +
                'Or just type a question to chat with your documents!'
            );
            return;
        }
        // ── End slash command interception ────────────────────────────

        appendMessage('user', text);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        fetch(`/api/projects/${projectId}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                quality_mode: document.getElementById('qualityMode')?.value || 'balanced',
                rewrite_query: document.getElementById('rewriteQuery')?.checked ?? true,
                hybrid_search: document.getElementById('hybridSearch')?.checked ?? true,
                rerank: document.getElementById('rerank')?.checked ?? true,
                grounded_only: document.getElementById('groundedOnly')?.checked ?? true
            })
        })
            .then(r => r.json())
            .then(data => {
                hideTyping(typingId);
                appendMessage('assistant',
                    data.response || data.message?.content || '',
                    data.sources,
                    data.grounding_score,
                    data.flagged,
                    data.warning);
            })
            .catch((err) => {
                console.error(err);
                hideTyping(typingId);
                appendMessage('assistant', window.SEARCH_I18N?.error_generic || "An error occurred fetching the response.");
            });
    }

    function appendMessage(role, content, sources, groundingScore, flagged, warning) {
        const icon = role === 'user' ? 'person' : 'robot';
        let srcHtml = '';
        if (sources && sources.length > 0) {
            const sourcesLabel = window.SEARCH_I18N?.sources_label || "Used from your files";
            const openFileLabel = window.SEARCH_I18N?.support_open_file || "Open file";
            srcHtml = `<div class="msg-sources"><span class="msg-sources-label">${sourcesLabel}</span>`;
            srcHtml += sources.map(s =>
                `<a class="msg-source-link view-source-btn" data-doc-id="${s.doc_id}" data-chunk-id="${s.chunk_id || ''}">
                 <i class="bi bi-file-earmark-text"></i> ${s.name}
                 <span class="visually-hidden"> - ${openFileLabel}</span></a>`
            ).join('');
            srcHtml += '</div>';
        }

        let groundingHtml = '';
        if (role === 'assistant' && groundingScore != null) {
            const pct = Math.round(groundingScore * 100);
            let lvl, cls;
            if (groundingScore >= 0.8) {
                lvl = window.SEARCH_I18N?.grounding?.high || "High";
                cls = 'grounding-high';
            } else if (groundingScore >= 0.5) {
                lvl = window.SEARCH_I18N?.grounding?.medium || "Medium";
                cls = 'grounding-medium';
            } else {
                lvl = window.SEARCH_I18N?.grounding?.low || "Low";
                cls = 'grounding-low';
            }

            const gLabel = window.SEARCH_I18N?.grounding?.label || "Support in your project files";
            groundingHtml = `<div class="msg-grounding">
                <span class="grounding-badge ${cls}" title="${gLabel}: ${pct}%">
                <i class="bi bi-shield-check"></i> ${pct}% ${lvl}</span>`;

            if (flagged) {
                const fLabel = window.SEARCH_I18N?.grounding?.flagged || "Review carefully";
                groundingHtml += `<span class="grounding-flag">${fLabel}</span>`;
            }
            if (warning) {
                groundingHtml += `<span class="grounding-warning">${warning}</span>`;
            }
            groundingHtml += '</div>';
        }

        let evidenceHtml = '';
        if (role === 'assistant' && (srcHtml || groundingHtml)) {
            const supportTitle = window.SEARCH_I18N?.support_title || "Why this answer";
            const filesUsedLabel = window.SEARCH_I18N?.support_files_used || "Files used";
            const fileCount = Array.isArray(sources) ? sources.length : 0;
            evidenceHtml = `<div class="msg-evidence">
                <div class="msg-evidence-summary">
                    <span class="msg-evidence-pill"><i class="bi bi-search"></i> <strong>${supportTitle}</strong></span>
                    ${fileCount > 0 ? `<span class="msg-evidence-pill"><i class="bi bi-folder2-open"></i> ${filesUsedLabel}: <strong>${fileCount}</strong></span>` : ''}
                </div>
                ${groundingHtml}
                ${srcHtml}
            </div>`;
        }

        const addToReportHtml = role === 'assistant'
            ? `<div class="msg-add-report">
                <button class="btn btn-sm add-to-report-btn msg-add-report-button" type="button">
                    <i class="bi bi-journal-plus me-1"></i>${window.SEARCH_I18N?.add_to_report || '+ Add to Report'}
                </button>
               </div>`
            : '';

        chatMessages.insertAdjacentHTML('beforeend',
            `<div class="spa-chat-msg ${role}">
                <div class="spa-chat-msg-avatar"><i class="bi bi-${icon}"></i></div>
                <div class="spa-chat-msg-bubble">
                    <div class="msg-text">${content}</div>
                    ${evidenceHtml}
                    ${addToReportHtml}
                </div>
            </div>`
        );
        // Wire up the Add to Report button
        const lastMsg = chatMessages.lastElementChild;
        const addBtn = lastMsg && lastMsg.querySelector('.add-to-report-btn');
        if (addBtn) {
            addBtn.addEventListener('click', function () {
                const reportUrl = window.SEARCH_I18N?.report_append_url;
                const payload = { content: content, sources: sources || [] };
                // Write to localStorage for report page to pick up
                const key = `report_pending_${window.SEARCH_I18N?.projectId}`;
                const existing = JSON.parse(localStorage.getItem(key) || '[]');
                existing.push(payload);
                localStorage.setItem(key, JSON.stringify(existing));
                addBtn.disabled = true;
                addBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>' + (window.SEARCH_I18N?.add_to_report_done || 'Added');
                // Also POST to backend for server awareness
                if (reportUrl) {
                    fetch(reportUrl, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }).catch(() => {});
                }
            });
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showTyping() {
        const id = 'typing-' + Date.now();
        chatMessages.insertAdjacentHTML('beforeend',
            `<div class="spa-chat-msg assistant" id="${id}">
                <div class="spa-chat-msg-avatar"><i class="bi bi-robot"></i></div>
                <div class="spa-chat-msg-bubble">
                    <div class="typing-indicator"><span></span><span></span><span></span></div>
                </div>
            </div>`
        );
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return id;
    }

    function hideTyping(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }
});
