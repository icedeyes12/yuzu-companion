// [FILE: renderer.js]
// [VERSION: 2.0.0]
// [DATE: 2026-02-14]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Markdown renderer using marked.js with syntax highlighting]
// [AUTHOR: Project Lead: Bani Baskara]
// [LICENSE: MIT]

// Markdown Renderer using marked.js
class MarkdownRenderer {
    constructor() {
        this.markedLoaded = false;
        this.highlightLoaded = false;
        this.initializeMarked();
    }

    initializeMarked() {
        // Wait for marked.js to load
        if (typeof marked !== 'undefined') {
            this.markedLoaded = true;
            this.configureMarked();
        } else {
            setTimeout(() => this.initializeMarked(), 100);
        }
    }

    configureMarked() {
        // Configure marked.js options
        marked.setOptions({
            highlight: (code, lang) => {
                if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (err) {
                        console.error('Highlight error:', err);
                    }
                }
                return code;
            },
            breaks: true,
            gfm: true,
            tables: true,
            pedantic: false,
            smartLists: true,
            smartypants: false
        });

        // Custom renderer for images
        const renderer = new marked.Renderer();
        
        // Override image rendering with URL validation and XSS protection
        renderer.image = (href, title, text) => {
            // Validate and sanitize URL
            let safeHref = '';
            try {
                const url = new URL(href, window.location.origin);
                // Only allow http, https, and data URLs
                if (['http:', 'https:', 'data:'].includes(url.protocol)) {
                    safeHref = url.href;
                }
            } catch (e) {
                // Invalid URL, use empty string
                console.warn('Invalid image URL:', href);
                safeHref = '';
            }
            
            const safeTitle = title ? ` title="${this.escapeHtml(title)}"` : '';
            const safeAlt = text ? ` alt="${this.escapeHtml(text)}"` : '';
            return `<img src="${safeHref}"${safeAlt}${safeTitle} class="message-image">`;
        };

        // Override code rendering to add copy button
        renderer.code = (code, language) => {
            const lang = language || 'plaintext';
            const highlighted = typeof hljs !== 'undefined' && hljs.getLanguage(lang)
                ? hljs.highlight(code, { language: lang }).value
                : this.escapeHtml(code);
            
            return `<div class="code-block-container">
                <div class="code-block-header">
                    <span class="code-language">${lang}</span>
                    <button class="copy-code-btn" data-action="copy-code">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                    </button>
                </div>
                <pre><code class="language-${lang}">${highlighted}</code></pre>
            </div>`;
        };

        marked.use({ renderer });
    }

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

    render(text) {
        if (!text) return '';
        
        if (!this.markedLoaded) {
            console.warn('marked.js not yet loaded, returning plain text');
            return this.escapeHtml(text);
        }

        try {
            const html = marked.parse(text);
            
            // Sanitize with DOMPurify if available
            if (typeof DOMPurify !== 'undefined') {
                return DOMPurify.sanitize(html, {
                    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'code', 'pre', 'a', 'img', 
                                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 
                                    'blockquote', 'table', 'thead', 'tbody', 'tr', 'th', 'td',
                                    'div', 'span', 'details', 'summary', 'hr', 'button', 'svg', 'rect', 'path', 'polyline'],
                    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'data-action', 
                                    'width', 'height', 'viewBox', 'fill', 'stroke', 'stroke-width', 
                                    'x', 'y', 'rx', 'ry', 'd', 'points'],
                    ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp|data):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i
                });
            }
            
            // Fallback if DOMPurify is not available (shouldn't happen)
            return html;
        } catch (error) {
            console.error('Markdown rendering error:', error);
            return this.escapeHtml(text);
        }
    }
}

// Global renderer instance
let renderer = null;

// Initialize renderer when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        renderer = new MarkdownRenderer();
        setupCodeCopyListeners();
    });
} else {
    renderer = new MarkdownRenderer();
    setupCodeCopyListeners();
}

// Setup event delegation for copy code buttons
function setupCodeCopyListeners() {
    document.addEventListener('click', (e) => {
        const button = e.target.closest('[data-action="copy-code"]');
        if (button) {
            copyCodeToClipboard(button);
        }
    });
}

// Copy code to clipboard
function copyCodeToClipboard(button) {
    const codeBlock = button.closest('.code-block-container');
    const code = codeBlock.querySelector('code');
    const text = code.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        const originalHTML = button.innerHTML;
        button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"></polyline>
        </svg>`;
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy code:', err);
    });
}
