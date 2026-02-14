// [FILE: renderer.js]
// [VERSION: 1.0.0]
// [DATE: 2025-02-14]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Single markdown renderer using marked.js and highlight.js]
// [AUTHOR: Project Lead: Bani Baskara]
// [LICENSE: MIT]

class MessageRenderer {
    constructor() {
        this.markedLoaded = false;
        this.hlLoaded = false;
        this.initializeMarked();
    }

    initializeMarked() {
        // Wait for marked.js and highlight.js to load
        const checkLibraries = () => {
            if (typeof marked !== 'undefined') {
                this.markedLoaded = true;
                
                // Configure marked with highlight.js integration
                if (typeof hljs !== 'undefined') {
                    this.hlLoaded = true;
                    
                    marked.setOptions({
                        highlight: function(code, lang) {
                            if (lang && hljs.getLanguage(lang)) {
                                try {
                                    return hljs.highlight(code, { language: lang }).value;
                                } catch (e) {
                                    console.error('Highlight error:', e);
                                }
                            }
                            return hljs.highlightAuto(code).value;
                        },
                        breaks: true,
                        gfm: true,
                        tables: true,
                        pedantic: false,
                        sanitize: false,
                        smartLists: true,
                        smartypants: false
                    });
                    
                    console.log('Renderer initialized with marked.js and highlight.js');
                } else {
                    // Retry if highlight.js not loaded yet
                    setTimeout(checkLibraries, 100);
                }
            } else {
                // Retry if marked.js not loaded yet
                setTimeout(checkLibraries, 100);
            }
        };
        
        checkLibraries();
    }

    /**
     * Render markdown to HTML
     * @param {string} text - Markdown text to render
     * @returns {string} - Rendered HTML
     */
    render(text) {
        if (!text) return '';
        
        if (!this.markedLoaded) {
            console.warn('marked.js not loaded yet, returning plain text');
            return this.escapeHtml(text);
        }

        try {
            // Parse markdown with marked.js
            let html = marked.parse(text);
            
            // Post-process: Add copy buttons to code blocks
            html = this.addCopyButtonsToCodeBlocks(html);
            
            // Post-process: Handle image rendering
            html = this.processImages(html);
            
            return html;
        } catch (error) {
            console.error('Markdown rendering error:', error);
            return this.escapeHtml(text);
        }
    }

    /**
     * Add copy buttons to code blocks
     * @param {string} html - HTML string
     * @returns {string} - HTML with copy buttons
     */
    addCopyButtonsToCodeBlocks(html) {
        // Match code blocks and add copy button
        return html.replace(
            /<pre><code([^>]*)>([\s\S]*?)<\/code><\/pre>/g,
            (match, attributes, code) => {
                // Extract language from class attribute if present
                const langMatch = attributes.match(/class="language-(\w+)"/);
                const lang = langMatch ? langMatch[1] : '';
                
                // Decode HTML entities in code
                const decodedCode = this.decodeHtmlEntities(code);
                
                return `
                    <div class="code-block-container">
                        <div class="code-block-header">
                            ${lang ? `<span class="code-lang">${lang}</span>` : ''}
                            <button class="code-copy-btn" onclick="window.copyCodeToClipboard(this)" title="Copy code">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                </svg>
                            </button>
                        </div>
                        <pre><code${attributes}>${code}</code></pre>
                    </div>
                `;
            }
        );
    }

    /**
     * Process images in HTML
     * @param {string} html - HTML string
     * @returns {string} - Processed HTML
     */
    processImages(html) {
        // Convert markdown image syntax to actual img tags if not already converted
        // marked.js should handle this, but we ensure proper handling
        return html.replace(
            /!\[([^\]]*)\]\(([^)]+)\)/g,
            '<img src="$2" alt="$1" class="message-image" />'
        );
    }

    /**
     * Decode HTML entities
     * @param {string} html - HTML string with entities
     * @returns {string} - Decoded string
     */
    decodeHtmlEntities(html) {
        const txt = document.createElement('textarea');
        txt.innerHTML = html;
        return txt.value;
    }

    /**
     * Escape HTML for safe display
     * @param {string} text - Text to escape
     * @returns {string} - Escaped HTML
     */
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
}

// Global instance
window.messageRenderer = new MessageRenderer();

// Global function for copying code
window.copyCodeToClipboard = function(button) {
    const container = button.closest('.code-block-container');
    const codeElement = container.querySelector('code');
    const code = codeElement.textContent;
    
    navigator.clipboard.writeText(code).then(() => {
        // Visual feedback
        const originalHTML = button.innerHTML;
        button.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        `;
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy code:', err);
        alert('Failed to copy code to clipboard');
    });
};

console.log('Renderer.js loaded');
