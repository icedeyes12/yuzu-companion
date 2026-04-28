// FILE: static/js/incremental-renderer.js
// DESCRIPTION: Simple line-based incremental markdown renderer
//              - No full re-render per chunk
//              - Tracks code block state (avoids parsing broken code)
//              - Only renders stable lines
//              - Final render is clean

/**
 * IncrementalMarkdownRenderer
 * 
 * Key insight: Don't parse incomplete markdown.
 * Track line state, only render complete lines.
 * Track code block state to avoid breaking ``` blocks mid-stream.
 */
class IncrementalMarkdownRenderer {
    constructor(container) {
        this.container = container;
        
        // Buffer and line tracking
        this.buffer = "";
        this.lines = [];
        this.renderedLineCount = 0;
        
        // Code block state
        this.inCodeBlock = false;
        this.codeBlockLang = null;
        
        // DOM parts: stable (completed) + live (current line)
        this.stableEl = document.createElement("div");
        this.stableEl.className = "incremental-stable";
        this.liveEl = document.createElement("div");
        this.liveEl.className = "incremental-live";
        
        this.container.appendChild(this.stableEl);
        this.container.appendChild(this.liveEl);
        
        // Reference to existing renderer
        this.renderer = null;
        if (typeof window.renderer !== 'undefined') {
            this.renderer = window.renderer;
        } else if (typeof renderer !== 'undefined') {
            this.renderer = renderer;
        }
        
        console.log('[IncrementalRenderer] Initialized');
    }

    /**
     * Set renderer explicitly
     */
    setRenderer(rendererInstance) {
        this.renderer = rendererInstance;
    }

    /**
     * Append a chunk of streaming content
     */
    append(chunk) {
        this.buffer += chunk;
        
        const newLines = this.buffer.split("\n");
        
        // Process only new stable lines (all except last)
        while (this.renderedLineCount < newLines.length - 1) {
            const line = newLines[this.renderedLineCount];
            this._processStableLine(line);
            this.renderedLineCount++;
        }
        
        // Last line = possibly incomplete → live preview
        this._renderLive(newLines[newLines.length - 1]);
    }

    /**
     * Process a stable (complete) line
     */
    _processStableLine(line) {
        // Track code block state
        const trimmed = line.trim();
        if (trimmed.startsWith("```")) {
            if (!this.inCodeBlock) {
                // Opening code block - extract language
                this.inCodeBlock = true;
                this.codeBlockLang = trimmed.slice(3).trim() || null;
            } else {
                // Closing code block
                this.inCodeBlock = false;
                this.codeBlockLang = null;
            }
        }
        
        // Render the line
        let html;
        if (this.inCodeBlock) {
            // Inside code block - render as plain text line
            // We'll accumulate these and render the whole block at close
            html = this._renderCodeBlockLine(line);
        } else {
            // Normal line - use renderer
            html = this._renderLine(line + "\n");
        }
        
        this.stableEl.insertAdjacentHTML("beforeend", html);
    }

    /**
     * Render a normal line using existing renderer
     */
    _renderLine(text) {
        if (this.renderer && typeof this.renderer.renderSync === 'function') {
            const html = this.renderer.renderSync(text);
            return typeof html === 'string' ? html : String(html || '');
        } else if (typeof marked !== 'undefined') {
            const html = marked.parse(text);
            return typeof html === 'string' ? html : String(html || '');
        }
        return this._escapeHtml(text);
    }

    /**
     * Render a line inside code block
     */
    _renderCodeBlockLine(line) {
        // Inside code block - just show raw text
        // The full code block will be rendered properly on finalize
        return `<div class="code-line-raw">${this._escapeHtml(line)}</div>`;
    }

    /**
     * Render the live (incomplete) line
     */
    _renderLive(line) {
        if (this.inCodeBlock) {
            // Inside code block - don't parse, show raw
            this.liveEl.innerHTML = `<span class="code-live">${this._escapeHtml(line)}</span><span class="cursor">▋</span>`;
        } else {
            // Normal line - try to parse
            // But wrap in paragraph to avoid breaking
            if (line.trim()) {
                const html = this._renderLine(line);
                this.liveEl.innerHTML = html + '<span class="cursor">▋</span>';
            } else {
                this.liveEl.innerHTML = '<span class="cursor">▋</span>';
            }
        }
    }

    /**
     * Finalize - full authoritative render
     */
    finalize() {
        // Full clean render using existing renderer
        if (this.renderer && typeof this.renderer.renderSync === 'function') {
            this.container.innerHTML = this.renderer.renderSync(this.buffer);
        } else if (typeof marked !== 'undefined') {
            this.container.innerHTML = marked.parse(this.buffer);
        } else {
            this.container.innerHTML = this._escapeHtml(this.buffer);
        }
        
        // Post-process: syntax highlighting, mermaid
        this._postProcess();
        
        console.log('[IncrementalRenderer] Finalized');
    }

    /**
     * Post-process: syntax highlighting, mermaid
     */
    _postProcess() {
        // Initialize mermaid if available
        if (this.renderer && typeof this.renderer.initializeMermaidDiagrams === 'function') {
            this.renderer.initializeMermaidDiagrams();
        } else if (typeof mermaid !== 'undefined' && typeof mermaid.run === 'function') {
            try {
                mermaid.run({ querySelector: '.mermaid' });
            } catch (e) {
                console.error('[IncrementalRenderer] Mermaid error:', e);
            }
        }
        
        // Apply syntax highlighting if needed
        if (typeof hljs !== 'undefined') {
            const codeBlocks = this.container.querySelectorAll('pre code:not(.hljs)');
            codeBlocks.forEach(block => {
                if (block.className.includes('language-')) {
                    try {
                        hljs.highlightElement(block);
                    } catch (e) {
                        // Ignore
                    }
                }
            });
        }
    }

    /**
     * Reset for next message
     */
    reset() {
        this.buffer = "";
        this.lines = [];
        this.renderedLineCount = 0;
        this.inCodeBlock = false;
        this.codeBlockLang = null;
        
        this.container.innerHTML = "";
        this.container.appendChild(this.stableEl);
        this.container.appendChild(this.liveEl);
        
        console.log('[IncrementalRenderer] Reset');
    }

    /**
     * Escape HTML for safe display
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Check if actively streaming
     */
    isActive() {
        return this.renderedLineCount > 0 || this.buffer.length > 0;
    }
}

// Export for ESM
export { IncrementalMarkdownRenderer };

// Expose globally for non-module usage
if (typeof window !== 'undefined') {
    window.IncrementalMarkdownRenderer = IncrementalMarkdownRenderer;
}
