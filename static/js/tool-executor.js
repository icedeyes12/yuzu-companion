/**
 * Simple Tool Executor UI
 * Shows tool execution status directly in chat without WebSocket
 */

class SimpleToolExecutor {
    constructor() {
        this.container = document.getElementById('chatContainer');
        this.currentToolCard = null;
    }

    /**
     * Show tool is starting
     */
    showToolStarting(toolName, toolIcon = '🔧') {
        const card = this.createToolCard(toolName, toolIcon, 'pending');
        this.container.appendChild(card);
        this.scrollToBottom();
        return card;
    }

    /**
     * Update tool to running state
     */
    updateToolRunning(card, statusText = 'Executing...') {
        card.classList.remove('tool-pending');
        card.classList.add('tool-running');
        const statusEl = card.querySelector('.tool-status');
        if (statusEl) {
            statusEl.textContent = statusText;
        }
        this.scrollToBottom();
    }

    /**
     * Show tool completed successfully
     */
    updateToolSuccess(card, result, summary = null) {
        card.classList.remove('tool-pending', 'tool-running');
        card.classList.add('tool-success');
        
        const contentEl = card.querySelector('.tool-content');
        if (contentEl) {
            contentEl.innerHTML = this.formatResult(result, summary);
        }
        
        const statusEl = card.querySelector('.tool-status');
        if (statusEl) {
            statusEl.innerContent = '✓ Complete';
        }
        
        this.scrollToBottom();
    }

    /**
     * Show tool error
     */
    updateToolError(card, error) {
        card.classList.remove('tool-pending', 'tool-running');
        card.classList.add('tool-error');
        
        const contentEl = card.querySelector('.tool-content');
        if (contentEl) {
            contentEl.innerHTML = `<div class="tool-error-message">❌ ${error}</div>`;
        }
        
        this.scrollToBottom();
    }

    /**
     * Create tool card HTML
     */
    createToolCard(toolName, icon, status) {
        const card = document.createElement('div');
        card.className = `tool-execution-card tool-${status}`;
        
        card.innerHTML = `
            <div class="tool-header">
                <span class="tool-icon">${icon}</span>
                <span class="tool-name">${toolName}</span>
                <span class="tool-status-badge">${status}</span>
            </div>
            <div class="tool-content">
                <div class="tool-spinner"></div>
                <span class="tool-status">${status === 'pending' ? 'Waiting...' : 'Executing...'}</span>
            </div>
        `;
        
        return card;
    }

    /**
     * Format tool result for display
     */
    formatResult(result, summary) {
        // Handle different result types
        if (typeof result === 'string') {
            // Check if it's a URL (image)
            if (result.match(/\.(jpg|jpeg|png|gif|webp)$/i)) {
                return `<img src="${result}" class="tool-result-image" alt="Generated image">`;
            }
            // Check if it's a file path
            if (result.startsWith('/') || result.startsWith('static/')) {
                return `<div class="tool-file-result">📁 ${result.split('/').pop()}</div>`;
            }
            return `<pre class="tool-text-result">${this.escapeHtml(result)}</pre>`;
        }
        
        if (typeof result === 'object') {
            return `<pre class="tool-json-result">${JSON.stringify(result, null, 2)}</pre>`;
        }
        
        return `<div class="tool-generic-result">${result}</div>`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    scrollToBottom() {
        this.container.scrollTop = this.container.scrollHeight;
    }
}

// Initialize
window.toolExecutor = new SimpleToolExecutor();
