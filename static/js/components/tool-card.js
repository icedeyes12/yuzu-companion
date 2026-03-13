/**
 * ToolCard Component
 * Unified UI component for all tool interactions
 * Phase 3: UI Component System
 */


[truncated]
der() {
    this.element.className = `tool-card ${this.state.status}`;
    this.element.innerHTML = this.getHTML();
    this.attachEventListeners();
    return this.element;
  }
}

// Export for use in chat.js
window.ToolCard = ToolCard;
window.ToolCardUtils = { formatDuration, escapeHtml };
