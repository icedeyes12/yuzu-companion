// renderer.js - Markdown rendering using marked.js

/**
 * Configure marked.js for proper rendering
 */
if (typeof marked !== 'undefined') {
    // Configure marked options
    marked.setOptions({
        breaks: true,        // GitHub-flavored line breaks
        gfm: true,          // GitHub Flavored Markdown
        tables: true,       // Support tables
        smartLists: true,   // Better list handling
        smartypants: false, // Don't convert quotes/dashes
        headerIds: true,    // Add IDs to headers
        mangle: false,      // Don't mangle email addresses
        pedantic: false,    // Don't be too strict
    });

    // Custom renderer for better control
    const renderer = new marked.Renderer();

    // Custom code block rendering with copy button
    renderer.code = function(code, language) {
        const lang = language || 'text';
        const displayName = lang.toUpperCase();
        const escapedCode = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        return `
<div class="code-block-container">
    <div class="code-header">
        <span class="language-name">${displayName}</span>
        <button class="copy-code-btn" onclick="copyCodeToClipboard(this)" type="button">
            <span class="copy-text">Copy</span>
        </button>
    </div>
    <pre><code class="language-${lang}">${escapedCode}</code></pre>
</div>`;
    };

    // Custom image rendering
    renderer.image = function(href, title, text) {
        return `<img src="${href}" alt="${text || ''}" title="${title || ''}" loading="lazy" style="max-width: 100%; height: auto; border-radius: 8px; margin: 0.5rem 0;">`;
    };

    // Custom link rendering (open in new tab)
    renderer.link = function(href, title, text) {
        const titleAttr = title ? ` title="${title}"` : '';
        return `<a href="${href}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
    };

    marked.use({ renderer });
}

/**
 * Renderer class for message content
 */
const Renderer = {
    /**
     * Render markdown text to HTML
     */
    render(text) {
        if (!text) return '';
        
        try {
            // Parse markdown with marked.js
            const html = marked.parse(text);
            return html;
        } catch (error) {
            console.error('Markdown rendering error:', error);
            // Fallback to escaped plain text
            return `<p>${Utils.escapeHtml(text)}</p>`;
        }
    },

    /**
     * Highlight code blocks using highlight.js
     */
    highlightCodeBlocks(container) {
        if (typeof hljs === 'undefined') {
            console.warn('Highlight.js not loaded');
            return;
        }

        const codeBlocks = container.querySelectorAll('pre code');
        let count = 0;

        codeBlocks.forEach(block => {
            try {
                // Remove any existing highlighting
                block.className = block.className.replace(/\bhljs\b/, '');
                
                // Apply highlighting
                hljs.highlightElement(block);
                count++;
            } catch (error) {
                console.error('Error highlighting code block:', error);
            }
        });

        console.log(`Highlighted ${count} code blocks`);
        return count;
    },

    /**
     * Process message content - render markdown and highlight code
     */
    processMessage(text) {
        const html = this.render(text);
        return html;
    }
};

/**
 * Copy code to clipboard function
 */
function copyCodeToClipboard(button) {
    try {
        const codeContainer = button.closest('.code-block-container');
        const codeElement = codeContainer.querySelector('code');
        const codeText = codeElement.textContent;
        const copyText = button.querySelector('.copy-text');

        navigator.clipboard.writeText(codeText).then(() => {
            const originalText = copyText.textContent;
            copyText.textContent = 'Copied!';
            button.classList.add('copied');

            setTimeout(() => {
                copyText.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Clipboard copy failed:', err);
            // Fallback method
            const textArea = document.createElement('textarea');
            textArea.value = codeText;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);

            const originalText = copyText.textContent;
            copyText.textContent = 'Copied!';
            button.classList.add('copied');
            setTimeout(() => {
                copyText.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        });
    } catch (error) {
        console.error('Error copying code:', error);
    }
}

// Initialize highlight.js on load
document.addEventListener('DOMContentLoaded', () => {
    if (typeof hljs !== 'undefined') {
        console.log('Highlight.js initialized');
    } else {
        console.warn('Highlight.js not available');
    }
});

// Export renderer
window.Renderer = Renderer;
window.copyCodeToClipboard = copyCodeToClipboard;
