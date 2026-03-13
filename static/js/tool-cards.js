/**
 * Tool Card JavaScript Component
 * Handles rendering and WebSocket updates for tool execution results
 */

class ToolCardManager {
    constructor(options = {}) {
        this.options = {
            wsEnabled: options.wsEnabled || false,
            wsUrl: options.wsUrl || null,
            animationDuration: options.animationDuration || 300,
            ...options
        };
        
        this.ws = null;
        this.activeExecutions = new Map();
        
        if (this.options.wsEnabled && this.options.wsUrl) {
            this.initWebSocket();
        }
    }
    
    // ==================== WebSocket ====================
    
    initWebSocket() {
        if (!this.options.wsUrl) return;
        
        try {
            this.ws = new WebSocket(this.options.wsUrl);
            
            this.ws.onopen = () => {
                console.log('[ToolCard] WebSocket connected');
                this.authenticate();
            };
            
            this.ws.onmessage = (event) => {
                this.handleMessage(JSON.parse(event.data));
            };
            
            this.ws.onclose = () => {
                console.log('[ToolCard] WebSocket disconnected');
                this.reconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('[ToolCard] WebSocket error:', error);
            };
            
        } catch (e) {
            console.error('[ToolCard] Failed to init WebSocket:', e);
        }
    }
    
    authenticate() {
        // Send session info for authentication
        const sessionId = this.getSessionId();
        if (sessionId && this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'auth',
                data: { session_id: sessionId }
            }));
        }
    }
    
    reconnect() {
        // Auto-reconnect after delay
        setTimeout(() => {
            if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
                this.initWebSocket();
            }
        }, 3000);
    }
    
    handleMessage(message) {
        const { type, data } = message;
        
        switch (type) {
            case 'tool_update':
                this.handleToolUpdate(data);
                break;
            case 'tool_complete':
                this.handleToolComplete(data);
                break;
            case 'stream_chunk':
                this.handleStreamChunk(data);
                break;
            case 'error':
                this.handleError(data);
                break;
        }
    }
    
    // ==================== Tool Update Handlers ====================
    
    handleToolUpdate(data) {
        const { execution_id, status, progress, status_text } = data;
        
        if (!execution_id) return;
        
        this.activeExecutions.set(execution_id, { status, progress, status_text });
        
        const card = this.findCard(execution_id);
        if (!card) return;
        
        // Update status indicator
        const indicator = card.querySelector('.tool-status-indicator');
        if (indicator) {
            if (status === 'running') {
                indicator.classList.add('spinning');
            } else {
                indicator.classList.remove('spinning');
            }
        }
        
        // Update status text
        if (status_text) {
            const statusEl = card.querySelector('.loading-text');
            if (statusEl) {
                statusEl.textContent = status_text;
            }
        }
        
        // Update progress bar
        if (progress !== undefined && progress !== null) {
            const progressFill = card.querySelector('.progress-fill');
            if (progressFill) {
                progressFill.style.width = `${progress}%`;
            }
        }
    }
    
    handleToolComplete(data) {
        const { execution_id, card_spec, llm_prompt } = data;
        
        if (!execution_id) return;
        
        this.activeExecutions.delete(execution_id);
        
        const card = this.findCard(execution_id);
        
        if (card_spec) {
            this.renderCardContent(card, card_spec);
        }
        
        // Handle LLM commentary
        if (llm_prompt) {
            this.requestLLMCommentary(execution_id, llm_prompt);
        }
    }
    
    handleStreamChunk(data) {
        const { message_id, content, is_tool_commentary } = data;
        
        // Find or create message element
        let messageEl = document.querySelector(`[data-message-id="${message_id}"]`);
        
        if (!messageEl) {
            messageEl = this.createAssistantMessage(message_id);
        }
        
        // Append content
        const contentEl = messageEl.querySelector('.message-content');
        if (contentEl) {
            contentEl.textContent += content;
        }
        
        if (is_tool_commentary) {
            messageEl.classList.add('tool-commentary');
        }
    }
    
    handleError(data) {
        const { code, message } = data;
        console.error('[ToolCard] Error:', code, message);
        
        // Could show error toast here
        this.showErrorToast(message);
    }
    
    // ==================== Rendering ====================
    
    renderCard(spec) {
        const container = document.createElement('div');
        container.className = 'tool-card-container';
        container.dataset.executionId = spec.execution_id || this.generateId();
        
        // Build card HTML
        container.innerHTML = this.buildCardHTML(spec);
        
        // Add to DOM
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.appendChild(container);
            this.scrollToBottom();
        }
        
        return container;
    }
    
    buildCardHTML(spec) {
        const {
            header_icon = '🔧',
            header_title = 'Tool',
            card_type = 'text',
            status = 'pending',
            content = {},
            error_message = null,
            progress = null,
            status_text = null,
            llm_commentary = null
        } = spec;
        
        let bodyContent = '';
        
        if (status === 'pending' || status === 'running') {
            bodyContent = `
                <div class="tool-loading">
                    <div class="spinner"></div>
                    <p class="loading-text">${status_text || 'Processing...'}</p>
                    ${progress !== null ? `
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                    ` : ''}
                </div>
            `;
        } else if (status === 'success') {
            bodyContent = this.renderSuccessContent(card_type, content);
        } else if (status === 'error') {
            bodyContent = `
                <div class="tool-error">
                    <span class="error-icon">⚠️</span>
                    <p class="error-message">${error_message || 'An error occurred'}</p>
                </div>
            `;
        }
        
        return `
            <div class="tool-card" data-status="${status}">
                <div class="tool-card-header">
                    <span class="tool-icon">${header_icon}</span>
                    <span class="tool-title">${header_title}</span>
                    <span class="tool-status-indicator ${status === 'running' ? 'spinning' : ''}"></span>
                </div>
                <div class="tool-card-body">
                    ${bodyContent}
                </div>
                ${llm_commentary ? `
                <div class="tool-card-footer">
                    <p class="llm-commentary">${llm_commentary}</p>
                </div>
                ` : ''}
            </div>
        `;
    }
    
    renderSuccessContent(cardType, content) {
        switch (cardType) {
            case 'image':
                return `
                    <div class="tool-result-image">
                        <img src="${content.path || content.url || ''}" 
                             alt="${content.alt || 'Result'}"
                             onload="this.classList.add('loaded')"
                             onerror="this.classList.add('error')" />
                    </div>
                `;
            
            case 'list':
                const items = content.items || [];
                return `
                    <div class="tool-result-list">
                        <ul>
                            ${items.map(item => `<li>${item.text || JSON.stringify(item)}</li>`).join('')}
                        </ul>
                    </div>
                `;
            
            case 'code':
                return `
                    <div class="tool-result-code">
                        <pre><code>${this.escapeHtml(content.code || '')}</code></pre>
                    </div>
                `;
            
            default:
                return `
                    <div class="tool-result-text">
                        <pre>${this.escapeHtml(content.text || JSON.stringify(content, null, 2))}</pre>
                    </div>
                `;
        }
    }
    
    renderCardContent(card, spec) {
        const body = card.querySelector('.tool-card-body');
        const status = card.dataset.status;
        
        if (body && spec) {
            body.innerHTML = this.renderSuccessContent(spec.card_type || 'text', spec.content || {});
        }
        
        // Update status
        card.dataset.status = 'success';
        
        const indicator = card.querySelector('.tool-status-indicator');
        if (indicator) {
            indicator.classList.remove('spinning');
            indicator.style.background = 'var(--success-color, #a6e3a1)';
        }
    }
    
    // ==================== Utilities ====================
    
    findCard(executionId) {
        return document.querySelector(`[data-execution-id="${executionId}"]`);
    }
    
    generateId() {
        return 'exec_' + Math.random().toString(36).substr(2, 9);
    }
    
    getSessionId() {
        // Get session ID from page data or URL
        return window.YUZU_SESSION_ID || null;
    }
    
    scrollToBottom() {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }
    
    createAssistantMessage(messageId) {
        const container = document.createElement('div');
        container.className = 'message assistant-message';
        container.dataset.messageId = messageId;
        
        container.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content"></div>
        `;
        
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.appendChild(container);
        }
        
        return container;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    requestLLMCommentary(executionId, prompt) {
        // This would typically call the backend to get LLM commentary
        // For now, we'll just log it
        console.log('[ToolCard] Would request commentary:', prompt);
    }
    
    showErrorToast(message) {
        // Simple toast - could be enhanced
        const toast = document.createElement('div');
        toast.className = 'error-toast';
        toast.textContent = message;
        
        Object.assign(toast.style, {
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            background: '#f38ba8',
            color: '#11111b',
            padding: '12px 20px',
            borderRadius: '8px',
            zIndex: '10000',
            animation: 'fadeIn 0.3s ease'
        });
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }
    
    // ==================== Retry ====================
    
    retryTool(url) {
        fetch(url, { method: 'POST' })
            .then(response => response.json())
            .then(data => {
                if (data.execution_id) {
                    this.renderCard(data);
                }
            })
            .catch(error => {
                console.error('[ToolCard] Retry failed:', error);
                this.showErrorToast('Retry failed. Please try again.');
            });
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.toolCardManager = new ToolCardManager({
        wsEnabled: typeof window.YUZU_WS_ENABLED !== 'undefined' && window.YUZU_WS_ENABLED,
        wsUrl: window.YUZU_WS_URL || null
    });
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ToolCardManager;
}
