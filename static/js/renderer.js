// renderer.js - Markdown Rendering using markdown-it
// 
// IMPORTANT: This implementation uses markdown-it as required by project rules.
// CDN is blocked in deployment environment, so markdown-it must be:
// 1. Loaded from https://unpkg.com/markdown-it/dist/markdown-it.min.js (CDN)
// 2. OR copied locally to static/vendor/markdown-it.min.js
// 
// The fallback renderer below is ONLY for when markdown-it fails to load.
// It provides basic markdown support to prevent complete failure.

// Simple fallback if markdown-it is not available
function initMarkdownRenderer() {
    // Check if markdown-it is loaded
    if (typeof markdownit !== 'undefined') {
        window.md = markdownit({
            html: true,
            linkify: true,
            breaks: true,
            typographer: true
        });
        console.log('markdown-it initialized');
    } else {
        console.warn('markdown-it not loaded, using fallback renderer (NOT RECOMMENDED)');
        // Simple fallback renderer
        window.md = {
            render: function(text) {
                if (!text) return '';
                let html = String(text);
                
                // Protect code blocks first
                const codeBlocks = [];
                html = html.replace(/```(\w*)\n([\s\S]*?)\n```/g, (match, lang, code) => {
                    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
                    codeBlocks.push({ lang: lang || 'text', code: code.trim() });
                    return placeholder;
                });
                
                // Inline code
                html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
                
                // Bold and italic
                html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
                html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
                html = html.replace(/~~(.*?)~~/g, '<del>$1</del>');
                
                // Headings
                html = html.replace(/^###### (.*?)$/gm, '<h6>$1</h6>');
                html = html.replace(/^##### (.*?)$/gm, '<h5>$1</h5>');
                html = html.replace(/^#### (.*?)$/gm, '<h4>$1</h4>');
                html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
                html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
                html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
                
                // Links
                html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
                
                // Images
                html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" />');
                
                // Lists
                html = html.replace(/^[-*+] (.*?)$/gm, '<li>$1</li>');
                html = html.replace(/(<li>.*?<\/li>\n?)+/g, '<ul>$&</ul>');
                
                // Numbered lists
                html = html.replace(/^\d+\. (.*?)$/gm, '<li>$1</li>');
                
                // Blockquotes
                html = html.replace(/^> (.*?)$/gm, '<blockquote>$1</blockquote>');
                
                // HR
                html = html.replace(/^---$/gm, '<hr>');
                html = html.replace(/^\*\*\*$/gm, '<hr>');
                
                // Tables (basic)
                html = html.replace(/\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)/g, (match, header, body) => {
                    const headers = header.split('|').filter(h => h.trim()).map(h => `<th>${h.trim()}</th>`).join('');
                    const rows = body.trim().split('\n').map(row => {
                        const cells = row.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('');
                        return `<tr>${cells}</tr>`;
                    }).join('');
                    return `<table><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
                });
                
                // Restore code blocks
                codeBlocks.forEach((block, i) => {
                    const codeHtml = createCodeBlock(block.lang, block.code);
                    html = html.replace(`__CODE_BLOCK_${i}__`, codeHtml);
                });
                
                // Line breaks
                html = html.replace(/\n/g, '<br>');
                
                return html;
            }
        };
    }
}

// Create code block HTML with proper styling
function createCodeBlock(lang, code) {
    const escapedCode = code
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    
    return `<div class="code-block">
        <div class="code-header">
            <span class="code-lang">${lang.toUpperCase()}</span>
            <button class="copy-btn" onclick="copyCode(this)">Copy</button>
        </div>
        <pre><code class="language-${lang}">${escapedCode}</code></pre>
    </div>`;
}

// Render markdown with proper container styling
function renderMarkdown(text) {
    if (!window.md) {
        initMarkdownRenderer();
    }
    
    let html = window.md.render(text);
    
    // Wrap tables in a scrollable container
    html = html.replace(/<table>/g, '<div class="table-container"><table>');
    html = html.replace(/<\/table>/g, '</table></div>');
    
    // Wrap blockquotes properly
    html = html.replace(/<blockquote>/g, '<blockquote class="markdown-blockquote">');
    
    // Add copy buttons to code blocks if markdown-it generated them
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    
    tempDiv.querySelectorAll('pre code').forEach((codeElement) => {
        const pre = codeElement.parentElement;
        if (!pre.parentElement.classList.contains('code-block')) {
            const lang = codeElement.className.match(/language-(\w+)/)?.[1] || 'text';
            const code = codeElement.textContent;
            const codeBlockHtml = createCodeBlock(lang, code);
            pre.outerHTML = codeBlockHtml;
        }
    });
    
    return tempDiv.innerHTML;
}

// Copy code to clipboard
function copyCode(button) {
    const codeBlock = button.closest('.code-block');
    const code = codeBlock.querySelector('code');
    
    if (!code) return;
    
    const text = code.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        const originalText = button.textContent;
        button.textContent = 'Copied!';
        
        setTimeout(() => {
            button.textContent = originalText;
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    initMarkdownRenderer();
});

// Export functions
window.renderMarkdown = renderMarkdown;
window.copyCode = copyCode;
