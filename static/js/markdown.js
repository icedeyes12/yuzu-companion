// [FILE: markdown.js] - markdown-it implementation
// [VERSION: 2.0.0] - Phase 4: markdown-it replacement
// [DATE: 2026-02-08]
// [PROJECT: HKKM - Yuzu Companion]

console.log("Loading markdown-it renderer...");

// Initialize markdown-it instance
let md = null;

function initMarkdownIt() {
    if (typeof window.markdownit === 'undefined') {
        console.error('markdown-it library not loaded!');
        return false;
    }
    
    // Initialize with options
    md = window.markdownit({
        html: false,        // Disable raw HTML for security
        xhtmlOut: false,    // Use HTML5 tags
        breaks: true,       // Convert \n to <br>
        linkify: true,      // Auto-convert URLs to links
        typographer: true,  // Enable smart quotes and other typographic replacements
        highlight: function (str, lang) {
            // Use highlight.js for syntax highlighting
            if (lang && hljs.getLanguage(lang)) {
                try {
                    return hljs.highlight(str, { language: lang }).value;
                } catch (err) {
                    console.error('Highlight error:', err);
                }
            }
            return ''; // Use default escaping
        }
    });
    
    // Customize code block renderer to add wrapper container
    const defaultFenceRenderer = md.renderer.rules.fence || function(tokens, idx, options, env, self) {
        return self.renderToken(tokens, idx, options);
    };
    
    md.renderer.rules.fence = function (tokens, idx, options, env, self) {
        const token = tokens[idx];
        const info = token.info ? md.utils.unescapeAll(token.info).trim() : '';
        const langName = info ? info.split(/\s+/g)[0] : 'text';
        const highlighted = options.highlight(token.content, langName) || md.utils.escapeHtml(token.content);
        
        // Wrap in code-block-container for overflow control
        return `<div class="code-block-container">
<pre><code class="language-${langName}">${highlighted}</code></pre>
</div>\n`;
    };
    
    // Customize image renderer to add wrapper container
    const defaultImageRenderer = md.renderer.rules.image || function(tokens, idx, options, env, self) {
        return self.renderToken(tokens, idx, options);
    };
    
    md.renderer.rules.image = function (tokens, idx, options, env, self) {
        const token = tokens[idx];
        const srcIdx = token.attrIndex('src');
        const altIdx = token.attrIndex('alt');
        
        const src = token.attrs[srcIdx][1];
        const alt = altIdx >= 0 ? token.attrs[altIdx][1] : '';
        
        // Wrap images in container for overflow control
        return `<div class="image-container">
<img src="${md.utils.escapeHtml(src)}" alt="${md.utils.escapeHtml(alt)}" loading="lazy">
</div>\n`;
    };
    
    // Customize table renderer to add wrapper container
    const defaultTableOpenRenderer = md.renderer.rules.table_open || function(tokens, idx, options, env, self) {
        return self.renderToken(tokens, idx, options);
    };
    
    md.renderer.rules.table_open = function (tokens, idx, options, env, self) {
        return '<div class="table-container"><table>\n';
    };
    
    const defaultTableCloseRenderer = md.renderer.rules.table_close || function(tokens, idx, options, env, self) {
        return self.renderToken(tokens, idx, options);
    };
    
    md.renderer.rules.table_close = function (tokens, idx, options, env, self) {
        return '</table></div>\n';
    };
    
    console.log("markdown-it initialized successfully");
    return true;
}

// Main rendering function
function renderMessageContent(text) {
    if (!text) return '';
    
    // Initialize if not already done
    if (!md) {
        const success = initMarkdownIt();
        if (!success) {
            console.error('Failed to initialize markdown-it');
            // Fallback to simple HTML escaping
            return text.replace(/&/g, '&amp;')
                      .replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;')
                      .replace(/\n/g, '<br>');
        }
    }
    
    try {
        return md.render(text);
    } catch (err) {
        console.error('Markdown rendering error:', err);
        return text.replace(/&/g, '&amp;')
                  .replace(/</g, '&lt;')
                  .replace(/>/g, '&gt;')
                  .replace(/\n/g, '<br>');
    }
}

// Compatibility layer for old MarkdownParser API
class MarkdownParser {
    static parse(text) {
        return renderMessageContent(text);
    }
    
    static highlightCodeBlocks(container) {
        // highlight.js will be called during markdown-it rendering
        // But we still need to handle any pre-existing code blocks
        if (typeof hljs !== 'undefined') {
            container.querySelectorAll('pre code:not(.hljs)').forEach((block) => {
                hljs.highlightElement(block);
            });
        }
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMarkdownIt);
} else {
    initMarkdownIt();
}

console.log("markdown-it renderer loaded");
