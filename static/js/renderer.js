// [FILE: renderer.js]
// [VERSION: 2.0.0]
// [DATE: 2025-08-12]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Single renderer using marked.js and highlight.js]
// [AUTHOR: Project Lead: Bani Baskara]

console.log("Initializing renderer.js - using marked.js and highlight.js");

// Wait for marked and hljs to be available
function waitForLibraries() {
    return new Promise((resolve) => {
        const checkInterval = setInterval(() => {
            if (typeof marked !== 'undefined' && typeof hljs !== 'undefined') {
                clearInterval(checkInterval);
                resolve();
            }
        }, 50);
    });
}

// Initialize marked configuration
async function initializeRenderer() {
    await waitForLibraries();
    
    // Configure marked to use highlight.js for code blocks
    marked.setOptions({
        highlight: function(code, lang) {
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(code, { language: lang }).value;
                } catch (err) {
                    console.error('Highlight error:', err);
                }
            }
            return hljs.highlightAuto(code).value;
        },
        breaks: true,
        gfm: true,
        headerIds: true,
        mangle: false,
        pedantic: false
    });
    
    console.log("Renderer initialized with marked.js and highlight.js");
}

// Main render function
async function renderMarkdown(text) {
    if (!text) return '';
    
    // Ensure libraries are loaded
    if (typeof marked === 'undefined') {
        console.error('marked.js is not loaded!');
        return escapeHtml(text);
    }
    
    try {
        // Parse markdown to HTML
        let html = marked.parse(text);
        
        // Post-process: wrap code blocks with copy button container
        html = addCopyButtonsToCodeBlocks(html);
        
        // Process image tags to ensure they render properly
        html = processImageTags(html);
        
        return html;
    } catch (err) {
        console.error('Markdown render error:', err);
        return `<pre>${escapeHtml(text)}</pre>`;
    }
}

// Add copy buttons to code blocks
function addCopyButtonsToCodeBlocks(html) {
    // Find all <pre><code> blocks and wrap them with a container that has a copy button
    return html.replace(/<pre><code([^>]*)>([\s\S]*?)<\/code><\/pre>/g, (match, attributes, code) => {
        // Extract language class if present
        const langMatch = attributes.match(/class="language-(\w+)"/);
        const language = langMatch ? langMatch[1] : 'text';
        
        return `<div class="code-block-container">
            <div class="code-block-header">
                <span class="code-block-language">${language}</span>
                <button class="code-copy-btn" onclick="copyCodeBlock(this)" title="Copy code">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                </button>
            </div>
            <pre><code${attributes}>${code}</code></pre>
        </div>`;
    });
}

// Process image tags to ensure proper rendering
function processImageTags(html) {
    // Ensure markdown images are converted to proper img tags
    // marked.js should handle this, but we can add additional processing if needed
    return html;
}

// Copy code block to clipboard
function copyCodeBlock(button) {
    const container = button.closest('.code-block-container');
    const codeBlock = container.querySelector('code');
    const text = codeBlock.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        // Visual feedback
        const originalHTML = button.innerHTML;
        button.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
    });
}

// Escape HTML for fallback rendering
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize when libraries are ready
initializeRenderer();

// Export for global use
window.renderMarkdown = renderMarkdown;
window.copyCodeBlock = copyCodeBlock;
