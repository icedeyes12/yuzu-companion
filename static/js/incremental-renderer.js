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
        this.codeBlockStartLine = -1;
        
        // Table state (tables are multi-line)
        this.inTable = false;
        this.tableStartLine = -1;
        
        // Track completed blocks for incremental processing
        this.lastProcessedCodeBlockEnd = -1;
        this.lastProcessedMermaidEnd = -1;
        
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
            this._processStableLine(line, this.renderedLineCount);
            this.renderedLineCount++;
        }
        
        // Last line = possibly incomplete → live preview
        this._renderLive(newLines[newLines.length - 1]);
    }

    /**
     * Process a stable (complete) line
     */
    _processStableLine(line, lineIndex) {
        const trimmed = line.trim();
        
        // Track code block state
        if (trimmed.startsWith("```")) {
            if (!this.inCodeBlock) {
                // Opening code block
                this.inCodeBlock = true;
                this.codeBlockLang = trimmed.slice(3).trim() || null;
                this.codeBlockStartLine = lineIndex;
            } else {
                // Closing code block - render the WHOLE block now
                this.inCodeBlock = false;
                
                // Extract the complete code block from buffer
                const codeBlockContent = this._extractCompletedCodeBlock(lineIndex);
                if (codeBlockContent) {
                    // Render complete code block
                    const html = this._renderLine(codeBlockContent);
                    this.stableEl.insertAdjacentHTML("beforeend", html);
                    
                    // Immediately post-process this code block
                    this._postProcessCodeBlock(this.stableEl.lastElementChild);
                    
                    // If it's mermaid, initialize it
                    if (this.codeBlockLang === 'mermaid') {
                        this._initMermaidInElement(this.stableEl.lastElementChild);
                    }
                }
                
                this.codeBlockLang = null;
                this.codeBlockStartLine = -1;
                return; // Don't double-render
            }
        }
        
        // Track table state (lines starting with |)
        const isTableLine = trimmed.startsWith('|') && trimmed.includes('|');
        
        if (this.inCodeBlock) {
            // Inside code block - skip, will render whole block at close
            return;
        }
        
        // Render the line
        let html;
        html = this._renderLine(line + "\n");
        
        this.stableEl.insertAdjacentHTML("beforeend", html);
    }

    /**
     * Extract completed code block content from buffer
     */
    _extractCompletedCodeBlock(endLineIndex) {
        const lines = this.buffer.split("\n");
        
        // Find the start (opening ```)
        let startIdx = -1;
        for (let i = endLineIndex - 1; i >= 0; i--) {
            if (lines[i].trim().startsWith("```")) {
                startIdx = i;
                break;
            }
        }
        
        if (startIdx === -1) return null;
        
        // Build the code block markdown
        let blockContent = lines[startIdx] + "\n";
        for (let i = startIdx + 1; i <= endLineIndex; i++) {
            blockContent += lines[i] + "\n";
        }
        
        return blockContent;
    }

    /**
     * Render a line/block using existing renderer
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
     * Render the live (incomplete) line
     */
    _renderLive(line) {
        if (this.inCodeBlock) {
            // Inside code block - show raw with cursor
            this.liveEl.innerHTML = `<span class="code-live">${this._escapeHtml(line)}</span><span class="cursor">▋</span>`;
        } else {
            // Normal line - show parsed with cursor
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
        console.log('[IncrementalRenderer] Finalizing...');
        
        // Full clean render using existing renderer
        if (this.renderer && typeof this.renderer.renderSync === 'function') {
            const html = this.renderer.renderSync(this.buffer);
            this.container.innerHTML = typeof html === 'string' ? html : String(html || '');
        } else if (typeof marked !== 'undefined') {
            const html = marked.parse(this.buffer);
            this.container.innerHTML = typeof html === 'string' ? html : String(html || '');
        } else {
            this.container.innerHTML = this._escapeHtml(this.buffer);
        }
        
        // Post-process immediately, then again after RAF
        this._postProcessAll();
        
        // Also post-process after DOM settles
        requestAnimationFrame(() => {
            this._postProcessAll();
        });
        
        console.log('[IncrementalRenderer] Finalized');
    }

    /**
     * Post-process a single code block element
     */
    _postProcessCodeBlock(element) {
        if (!element) return;
        
        const codeEl = element.querySelector('pre code');
        if (!codeEl) return;
        
        // Check if already highlighted
        const hasSpans = codeEl.querySelectorAll('span.hljs-keyword, span.hljs-string, span.hljs-comment, span.hljs-number').length > 0;
        if (hasSpans) {
            if (!codeEl.classList.contains('hljs')) {
                codeEl.classList.add('hljs');
            }
            return;
        }
        
        // Apply hljs
        if (typeof hljs !== 'undefined') {
            try {
                const result = hljs.highlightAuto(codeEl.textContent);
                codeEl.innerHTML = result.value;
                codeEl.classList.add('hljs');
                if (result.language) {
                    codeEl.classList.add(`language-${result.language}`);
                }
            } catch (e) {
                console.warn('[IncrementalRenderer] HLJS error:', e);
            }
        }
    }

    /**
     * Initialize mermaid in an element
     */
    _initMermaidInElement(element) {
        if (!element) return;
        
        const mermaidEl = element.querySelector('.mermaid, pre.mermaid');
        if (!mermaidEl) return;
        
        // Remove data-processed to allow re-processing
        mermaidEl.removeAttribute('data-processed');
        
        if (typeof mermaid !== 'undefined' && typeof mermaid.run === 'function') {
            try {
                mermaid.run({ 
                    nodes: [mermaidEl]
                });
            } catch (e) {
                console.error('[IncrementalRenderer] Mermaid error:', e);
            }
        } else if (this.renderer && typeof this.renderer.initializeMermaidDiagrams === 'function') {
            this.renderer.initializeMermaidDiagrams();
        }
    }

    /**
     * Post-process all elements in container
     */
    _postProcessAll() {
        console.log('[IncrementalRenderer] Post-processing all...');
        
        // Process all code blocks
        if (typeof hljs !== 'undefined') {
            const codeBlocks = this.container.querySelectorAll('pre code');
            console.log('[IncrementalRenderer] Code blocks found:', codeBlocks.length);
            
            codeBlocks.forEach(block => {
                try {
                    // Check if already highlighted
                    const hasSpans = block.querySelectorAll('span.hljs-keyword, span.hljs-string, span.hljs-comment, span.hljs-number, span.hljs-function, span.hljs-variable').length > 0;
                    
                    if (hasSpans) {
                        if (!block.classList.contains('hljs')) {
                            block.classList.add('hljs');
                        }
                        return;
                    }
                    
                    // Apply highlightAuto
                    const result = hljs.highlightAuto(block.textContent);
                    block.innerHTML = result.value;
                    block.classList.add('hljs');
                    
                    if (result.language) {
                        block.classList.add(`language-${result.language}`);
                    }
                } catch (e) {
                    console.warn('[IncrementalRenderer] HLJS error:', e);
                }
            });
        }
        
        // Process all mermaid diagrams
        const mermaidBlocks = this.container.querySelectorAll('.mermaid, pre.mermaid');
        console.log('[IncrementalRenderer] Mermaid blocks found:', mermaidBlocks.length);
        
        if (mermaidBlocks.length > 0) {
            // Remove data-processed from all
            mermaidBlocks.forEach(el => {
                el.removeAttribute('data-processed');
            });
            
            if (typeof mermaid !== 'undefined' && typeof mermaid.run === 'function') {
                try {
                    mermaid.run({ querySelector: '.mermaid, pre.mermaid' });
                } catch (e) {
                    console.error('[IncrementalRenderer] Mermaid error:', e);
                }
            } else if (this.renderer && typeof this.renderer.initializeMermaidDiagrams === 'function') {
                this.renderer.initializeMermaidDiagrams();
            }
        }
        
        // Process tables (wrap in container if needed)
        const tables = this.container.querySelectorAll('table');
        tables.forEach(table => {
            if (!table.parentElement?.classList.contains('table-container')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-container';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });
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
        this.codeBlockStartLine = -1;
        this.lastProcessedCodeBlockEnd = -1;
        this.lastProcessedMermaidEnd = -1;
        
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
