// FILE: static/js/incremental-renderer.js
// DESCRIPTION: Simple streaming markdown renderer.
//              Accumulate + re-render approach (what ChatGPT/Claude actually do).
//              renderSync is fast enough that re-running per chunk is imperceptible.

class IncrementalMarkdownRenderer {
    constructor(container) {
        this.container = container;
        this.renderer = null;
        this.buffer = '';
    }

    setRenderer(rendererInstance) {
        this.renderer = rendererInstance;
    }

    append(chunk) {
        this.buffer += chunk;
        this._render();
    }

    finalize() {
        // Final authoritative render
        this._render();
        
        // Post-process: syntax highlighting + mermaid
        this._postProcess(true);
        
        // Reset for next message
        this.buffer = '';
        
        console.log('[IncrementalRenderer] Finalized');
    }

    _render() {
        if (!this.buffer.trim()) return;
        
        if (this.renderer && typeof this.renderer.renderSync === 'function') {
            const html = this.renderer.renderSync(this.buffer);
            this.container.innerHTML = typeof html === 'string' ? html : String(html || '');
        } else if (typeof marked !== 'undefined') {
            const html = marked.parse(this.buffer);
            this.container.innerHTML = typeof html === 'string' ? html : String(html || '');
        } else {
            this.container.textContent = this.buffer;
        }
    }

    _postProcess(isFinal = false) {
        // Apply syntax highlighting to any unprocessed code blocks
        if (typeof hljs !== 'undefined') {
            this.container.querySelectorAll('pre code:not(.hljs)').forEach(block => {
                try {
                    // Check if already has highlighted content
                    const hasSpans = block.querySelectorAll('span.hljs-keyword, span.hljs-string, span.hljs-comment, span.hljs-number').length > 0;
                    
                    if (!hasSpans) {
                        const result = hljs.highlightAuto(block.textContent);
                        block.innerHTML = result.value;
                        block.classList.add('hljs');
                        if (result.language) {
                            block.classList.add(`language-${result.language}`);
                        }
                    } else if (!block.classList.contains('hljs')) {
                        block.classList.add('hljs');
                    }
                } catch (e) {
                    // Ignore highlighting errors
                }
            });
        }

        // Initialize mermaid diagrams on finalize
        if (isFinal && this.renderer && typeof this.renderer.initializeMermaidDiagrams === 'function') {
            // Use requestAnimationFrame to ensure DOM is ready
            requestAnimationFrame(() => {
                this.renderer.initializeMermaidDiagrams();
            });
        } else if (isFinal && typeof mermaid !== 'undefined') {
            // Fallback: run mermaid directly
            this.container.querySelectorAll('.mermaid').forEach(el => {
                el.removeAttribute('data-processed');
            });
            try {
                requestAnimationFrame(() => {
                    mermaid.run({ querySelector: '.mermaid' });
                });
            } catch (e) {
                console.warn('[IncrementalRenderer] Mermaid error:', e);
            }
        }
    }
}

// Expose globally (NO ES module export - that crashes when loaded as plain script)
if (typeof window !== 'undefined') {
    window.IncrementalMarkdownRenderer = IncrementalMarkdownRenderer;
}
