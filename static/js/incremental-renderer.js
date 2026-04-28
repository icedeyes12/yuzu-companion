// FILE: static/js/incremental-renderer.js
// DESCRIPTION: Block-based incremental markdown renderer.
//              Stabilizes complete blocks; only re-renders the incomplete tail.

class IncrementalMarkdownRenderer {
    constructor(container) {
        this.container = container;
        this.renderer = null;
        
        // Stable = rendered once, never touched again
        this.stableMarkdown = [];
        this.stableHtml = '';
        
        // Live = current incomplete block(s)
        this.liveText = '';
        this.inCodeBlock = false;
        this.codeBlockBuffer = '';
    }

    setRenderer(rendererInstance) {
        this.renderer = rendererInstance;
    }

    /** Append a streaming chunk */
    append(chunk) {
        if (this.inCodeBlock) {
            this.codeBlockBuffer += chunk;
            this._tryCompleteCodeBlock();
        } else {
            this.liveText += chunk;
            this._processLiveText();
        }
        this._render();
    }

    /** Final clean render after stream ends */
    finalize() {
        const parts = [...this.stableMarkdown];
        
        if (this.inCodeBlock) {
            parts.push(this.codeBlockBuffer);
        } else if (this.liveText.trim()) {
            parts.push(this.liveText);
        }
        
        const fullMd = parts.join('\n\n');
        this.container.innerHTML = this._renderMarkdown(fullMd);
        this._postProcess(true);
        
        console.log('[IncrementalRenderer] Finalized');
    }

    // ==================== BLOCK DETECTION ====================

    /** Look for closing ``` inside a code block */
    _tryCompleteCodeBlock() {
        const lines = this.codeBlockBuffer.split('\n');
        
        // Start from 1 to skip the opening fence
        for (let i = 1; i < lines.length; i++) {
            if (lines[i].trim() === '```') {
                const completeBlock = lines.slice(0, i + 1).join('\n');
                this._stabilize(completeBlock);
                
                this.inCodeBlock = false;
                this.codeBlockBuffer = '';
                
                // Anything after the code block goes back to live text
                const remaining = lines.slice(i + 1).join('\n');
                if (remaining) {
                    this.liveText = remaining;
                    this._processLiveText();
                }
                return;
            }
        }
    }

    /** Scan live text for code fences or completable text blocks */
    _processLiveText() {
        // 1. Code block start detection
        const lines = this.liveText.split('\n');
        
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].trim().startsWith('```')) {
                const beforeCode = lines.slice(0, i).join('\n');
                this._flushText(beforeCode);
                
                this.inCodeBlock = true;
                this.codeBlockBuffer = lines.slice(i).join('\n');
                this.liveText = '';
                return;
            }
        }
        
        // 2. Stabilize complete text blocks (split on \n\n)
        this._stabilizeCompleteBlocks();
    }

    /** Flush raw text into stable blocks (used before entering a code block) */
    _flushText(text) {
        if (!text) return;
        
        const parts = text.split('\n\n');
        for (const part of parts) {
            if (part.trim()) this._stabilize(part);
        }
    }

    /**
     * Split live text on \n\n and move complete blocks to stable.
     * Handles multi-paragraph lists and blockquotes that are separated
     * by blank lines but should stay together.
     */
    _stabilizeCompleteBlocks() {
        const parts = this.liveText.split('\n\n');
        
        if (parts.length <= 1) return;
        
        let stabilizeUpTo = -1;
        let listStart = -1;
        let quoteStart = -1;
        
        for (let i = 0; i < parts.length - 1; i++) {
            const currentFirst = parts[i].split('\n')[0];
            const nextFirst     = parts[i + 1].split('\n')[0];
            
            const isCurrentList  = this._isListItem(currentFirst);
            const isNextList     = this._isListItem(nextFirst);
            const isNextIndented = /^[ \t]/.test(nextFirst);
            
            const isCurrentQuote = this._isBlockquote(currentFirst);
            const isNextQuote    = this._isBlockquote(nextFirst);
            
            // Keep loose lists together (including indented continuations)
            if (isCurrentList && (isNextList || isNextIndented)) {
                if (listStart === -1) listStart = i;
                continue;
            }
            
            // Keep multi-paragraph blockquotes together
            if (isCurrentQuote && isNextQuote) {
                if (quoteStart === -1) quoteStart = i;
                continue;
            }
            
            // Block ends here — stabilize everything from its start
            let startIdx = i;
            
            if (listStart !== -1) {
                startIdx = listStart;
                listStart = -1;
            } else if (quoteStart !== -1) {
                startIdx = quoteStart;
                quoteStart = -1;
            }
            
            const block = parts.slice(startIdx, i + 1).join('\n\n');
            if (block.trim()) this._stabilize(block);
            
            stabilizeUpTo = i;
        }
        
        // If we ended mid-list/quote, keep it all live
        if (listStart !== -1 || quoteStart !== -1) {
            const startIdx = listStart !== -1 ? listStart : quoteStart;
            this.liveText = parts.slice(startIdx).join('\n\n');
            return;
        }
        
        if (stabilizeUpTo >= 0) {
            this.liveText = parts.slice(stabilizeUpTo + 1).join('\n\n');
        }
    }

    _isListItem(line) {
        return /^[ \t]*[-*+][ \t]/.test(line) || /^[ \t]*\d+\.[ \t]/.test(line);
    }

    _isBlockquote(line) {
        return /^[ \t]*>/.test(line);
    }

    // ==================== RENDERING ====================

    _stabilize(markdown) {
        this.stableMarkdown.push(markdown);
        this.stableHtml += this._renderMarkdown(markdown);
    }

    _renderMarkdown(md) {
        if (this.renderer && typeof this.renderer.renderSync === 'function') {
            const html = this.renderer.renderSync(md);
            return typeof html === 'string' ? html : String(html || '');
        }
        
        if (typeof marked !== 'undefined') {
            const html = marked.parse(md);
            return typeof html === 'string' ? html : String(html || '');
        }
        
        return this._escapeHtml(md);
    }

    _render() {
        let html = this.stableHtml;
        
        if (this.inCodeBlock) {
            // Render partial code block so user sees it streaming in
            html += this._renderMarkdown(this.codeBlockBuffer);
        } else if (this.liveText.trim()) {
            html += this._renderMarkdown(this.liveText);
        }
        
        this.container.innerHTML = html;
        this._postProcess();
    }

    _postProcess(isFinal = false) {
        // Highlight code blocks as they appear
        if (typeof hljs !== 'undefined') {
            this.container.querySelectorAll('pre code:not(.hljs)').forEach(block => {
                try {
                    const result = hljs.highlightAuto(block.textContent);
                    block.innerHTML = result.value;
                    block.classList.add('hljs');
                    if (result.language) {
                        block.classList.add(`language-${result.language}`);
                    }
                } catch (e) {
                    // ignore
                }
            });
        }
        
        // Only run mermaid on finalize (don't waste cycles on incomplete diagrams)
        if (isFinal && typeof mermaid !== 'undefined') {
            this.container.querySelectorAll('.mermaid').forEach(el => {
                el.removeAttribute('data-processed');
            });
            try {
                mermaid.run({ querySelector: '.mermaid' });
            } catch (e) {
                console.warn('[IncrementalRenderer] Mermaid finalize error:', e);
            }
        }
    }

    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Check if actively streaming
     */
    isActive() {
        return this.stableMarkdown.length > 0 || this.liveText.length > 0 || this.codeBlockBuffer.length > 0;
    }
    
    /**
     * Reset for next message
     */
    reset() {
        this.stableMarkdown = [];
        this.stableHtml = '';
        this.liveText = '';
        this.inCodeBlock = false;
        this.codeBlockBuffer = '';
        this.container.innerHTML = '';
        
        console.log('[IncrementalRenderer] Reset');
    }
}

// ESM + global compatibility
export { IncrementalMarkdownRenderer };

if (typeof window !== 'undefined') {
    window.IncrementalMarkdownRenderer = IncrementalMarkdownRenderer;
}
