// [FILE: renderer.js] - Markdown Renderer
// [VERSION: 2.0.0 - Frontend Reset]
// [DATE: 2026-02-08]

console.log("Loading renderer.js...");

// Initialize markdown-it when available
let md = null;

function initMarkdownIt() {
    if (typeof window.markdownit === 'undefined') {
        console.error('markdown-it not loaded yet');
        return false;
    }
    
    md = window.markdownit({
        html: false,
        linkify: true,
        breaks: true
    });
    
    console.log("markdown-it initialized");
    return true;
}

function renderMessageContent(text) {
    if (!md) {
        initMarkdownIt();
    }
    
    if (!md) {
        // Fallback if markdown-it still not available
        return String(text).replace(/&/g, '&amp;')
                          .replace(/</g, '&lt;')
                          .replace(/>/g, '&gt;')
                          .replace(/\n/g, '<br>');
    }
    
    return md.render(String(text));
}

// Export to global scope
window.renderMessageContent = renderMessageContent;

console.log("renderer.js loaded");
