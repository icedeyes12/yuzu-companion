// markdown.js - SAFE CDN VERSION with marked.js
// Uses marked.js from CDN for parsing, keeps utility functions

// Custom renderer for code blocks and tables
const customRenderer = {
    code(code, language) {
        const lang = language || 'text';
        const escapedCode = code
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
        
        return `<div class="code-block-container">
    <div class="code-header">
        <span class="language-name">${lang.toUpperCase()}</span>
        <button class="copy-code-btn" onclick="copyCodeToClipboard(this)">
            <span class="copy-text">Copy</span>
        </button>
    </div>
    <pre><code class="language-${lang}">${escapedCode}</code></pre>
</div>`;
    },
    
    table(header, body) {
        // Wrap table in .table-container for proper styling and overflow handling
        return `<div class="table-container">
    <table>
        <thead>${header}</thead>
        <tbody>${body}</tbody>
    </table>
</div>`;
    }
};

// Simple wrapper to use marked.js for markdown parsing
function renderMessageContent(text) {
    if (!text) return "";
    
    // Ensure marked is available
    if (typeof marked === 'undefined') {
        console.error('marked.js not loaded!');
        return String(text);
    }
    
    try {
        // Use marked.parse (custom renderer already registered via marked.use)
        return marked.parse(String(text));
    } catch (e) {
        console.error('Error parsing markdown:', e);
        return String(text);
    }
}

// Code highlighting utility (kept from original)
function highlightCodeBlocks(container = document) {
    if (typeof hljs === 'undefined') {
        console.log('Highlight.js not loaded');
        return 0;
    }

    const blocks = container.querySelectorAll('pre code');
    let count = 0;

    blocks.forEach(block => {
        try {
            block.className = block.className.replace(/hljs|language-\w+/g, '');
            
            const match = block.className.match(/language-(\w+)/);
            if (match) {
                block.className = `language-${match[1]}`;
            }
            
            hljs.highlightElement(block);
            count++;
        } catch (e) {
            console.error('Error highlighting:', e);
            block.classList.add('hljs');
        }
    });

    console.log(`Highlighted ${count} code blocks`);
    return count;
}

// Copy code to clipboard utility (kept from original)
function copyCodeToClipboard(button) {
    if (!button) return;
    
    try {
        const codeContainer = button.closest('.code-block-container, pre');
        const codeElement = codeContainer.querySelector('code');
        if (!codeElement) return;

        const codeText = codeElement.textContent || codeElement.innerText;
        const copyText = button.querySelector('.copy-text');

        navigator.clipboard.writeText(codeText).then(() => {
            const originalText = copyText ? copyText.textContent : 'Copy';
            if (copyText) copyText.textContent = 'Copied!';
            button.classList.add('copied');
            
            setTimeout(() => {
                if (copyText) copyText.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.log('Using fallback copy method');
            const textArea = document.createElement('textarea');
            textArea.value = codeText;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            const originalText = copyText ? copyText.textContent : 'Copy';
            if (copyText) copyText.textContent = 'Copied!';
            button.classList.add('copied');
            setTimeout(() => {
                if (copyText) copyText.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        });
    } catch (error) {
        console.error('Error copying:', error);
    }
}

// Initialize marked.js options when available
document.addEventListener('DOMContentLoaded', () => {
    console.log('Markdown parser (CDN version) loaded');
    
    if (typeof marked !== 'undefined') {
        // Configure marked options
        marked.setOptions({
            breaks: true,        // Support line breaks
            gfm: true,          // GitHub Flavored Markdown
            headerIds: true,
            mangle: false,
            sanitize: false,    // We trust our content
            smartLists: true,
            smartypants: false,
            xhtml: false
        });
        
        // Use custom renderer for better code block wrapping
        marked.use({ renderer: customRenderer });
        
        console.log('marked.js configured successfully with custom renderer');
    } else {
        console.error('marked.js not found! Make sure CDN script is loaded.');
    }
    
    if (typeof hljs !== 'undefined') {
        hljs.configure({ 
            tabReplace: '    ',
            ignoreUnescapedHTML: true
        });
        
        setTimeout(() => {
            const count = highlightCodeBlocks();
            console.log(`Initially highlighted ${count} code blocks`);
        }, 1000);
    }
});

// Backward compatibility: Export as MarkdownParser for existing code
const MarkdownParser = {
    parse: renderMessageContent,
    highlightCodeBlocks: highlightCodeBlocks
};

// Export functions to global scope
window.renderMessageContent = renderMessageContent;
window.MarkdownParser = MarkdownParser;
window.copyCodeToClipboard = copyCodeToClipboard;
window.highlightCodeBlocks = highlightCodeBlocks;
