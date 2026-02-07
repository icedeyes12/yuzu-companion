// markme.js - Marked.js wrapper with custom enhancements
class MarkdownParser {
    static parse(text) {
        if (!text) return '';
        
        // Check if marked is available
        if (typeof marked === 'undefined') {
            console.error('marked.js not loaded, falling back to plain text');
            return this.escapeHtml(String(text));
        }
        
        console.log("Processing text length:", text.length);
        
        // Configure marked.js
        marked.setOptions({
            breaks: true,  // Convert \n to <br>
            gfm: true,     // GitHub Flavored Markdown
            headerIds: true,
            mangle: false,
            sanitize: false,
            highlight: function(code, lang) {
                // Let highlight.js handle syntax highlighting after rendering
                if (lang && hljs && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (err) {
                        console.error('Highlight error:', err);
                    }
                }
                return code;
            },
            // Custom renderer for code blocks to add copy button container
            renderer: new marked.Renderer()
        });
        
        // Custom renderer to wrap code blocks
        const renderer = new marked.Renderer();
        const originalCodeRenderer = renderer.code.bind(renderer);
        
        renderer.code = function(code, language) {
            const langClass = language ? `language-${language}` : '';
            const langLabel = language ? language : 'text';
            
            return `<div class="code-block-container">
                <div class="code-header">
                    <span class="code-language">${langLabel}</span>
                </div>
                <pre><code class="${langClass}">${code}</code></pre>
            </div>`;
        };
        
        marked.use({ renderer });
        
        try {
            // Parse markdown with marked.js
            const html = marked.parse(String(text));
            return html;
        } catch (error) {
            console.error('Markdown parsing error:', error);
            return this.escapeHtml(String(text));
        }
    }
    
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    static parseWithEmojis(text) {
        return this.parse(text);
    }

    static highlightCodeBlocks(container = document) {
        if (typeof hljs === 'undefined') {
            console.log('Highlight.js not loaded');
            return 0;
        }

        const blocks = container.querySelectorAll('pre code');
        let count = 0;

        blocks.forEach(block => {
            try {
                // Skip if already highlighted
                if (block.classList.contains('hljs')) {
                    return;
                }
                
                block.className = block.className.replace(/hljs/g, '').trim();
                
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
}

// Inisialisasi array placeholder code block (for backward compatibility)
MarkdownParser.codeBlockPlaceholders = [];

// FUNGSI COPY
function copyCodeToClipboard(button) {
    if (!button) return;
    
    try {
        const codeContainer = button.closest('.code-block-container');
        const codeElement = codeContainer.querySelector('code');
        if (!codeElement) return;

        const codeText = codeElement.textContent || codeElement.innerText;
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
            console.log('Using fallback copy method');
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
        console.error('Error copying:', error);
    }
}

// INISIALISASI
document.addEventListener('DOMContentLoaded', () => {
    console.log('Markdown parser loaded with marked.js');
    
    if (typeof hljs !== 'undefined') {
        hljs.configure({ 
            tabReplace: '    ',
            ignoreUnescapedHTML: true
        });
        
        setTimeout(() => {
            const count = MarkdownParser.highlightCodeBlocks();
            console.log(`Initially highlighted ${count} code blocks`);
        }, 1000);
    }
});

window.MarkdownParser = MarkdownParser;
window.copyCodeToClipboard = copyCodeToClipboard;
