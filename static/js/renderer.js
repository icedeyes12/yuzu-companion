// [FILE: renderer.js]
// [VERSION: 1.0.0]
// [DATE: 2026-02-12]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Markdown renderer using marked.js with fallback]

/**
 * Initialize marked.js and highlight.js
 * This module exposes a single function: renderMessageContent(text)
 */

(function() {
    'use strict';

    // Check if marked.js is available (from CDN or local fallback)
    const hasMarked = typeof marked !== 'undefined';
    
    // Check if highlight.js is available
    const hasHighlight = typeof hljs !== 'undefined';

    // Configure marked.js if available
    if (hasMarked) {
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false,
            sanitize: false, // Allow HTML (needed for images)
            highlight: function(code, lang) {
                if (hasHighlight && lang) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {
                        console.warn('Highlight.js error:', e);
                    }
                }
                return code;
            }
        });
    }

    /**
     * Main rendering function
     * @param {string} text - Raw markdown text to render
     * @returns {string} - Rendered HTML
     */
    window.renderMessageContent = function(text) {
        if (!text) return '';
        
        try {
            // Use marked.js if available
            if (hasMarked) {
                let html = marked.parse(text);
                
                // Post-process: Add copy buttons to code blocks
                html = addCopyButtonsToCodeBlocks(html);
                
                // Post-process: Fix image rendering
                html = fixImageRendering(html);
                
                return html;
            } else {
                // Fallback to custom markdown parser if marked.js not loaded
                console.warn('marked.js not available, using fallback parser');
                if (typeof MarkdownParser !== 'undefined') {
                    return MarkdownParser.parse(text);
                } else {
                    // Last resort: return text with basic formatting
                    return escapeHtml(text).replace(/\n/g, '<br>');
                }
            }
        } catch (error) {
            console.error('Error rendering markdown:', error);
            return escapeHtml(text).replace(/\n/g, '<br>');
        }
    };

    /**
     * Add copy buttons to code blocks
     */
    function addCopyButtonsToCodeBlocks(html) {
        // Find all <pre><code> blocks and wrap them with a container that has a copy button
        return html.replace(/<pre><code([^>]*)>([\s\S]*?)<\/code><\/pre>/g, function(match, attrs, code) {
            // Extract language if present
            const langMatch = attrs.match(/class="language-(\w+)"/);
            const lang = langMatch ? langMatch[1] : '';
            
            // Generate unique ID for this code block
            const codeId = 'code-' + Math.random().toString(36).substr(2, 9);
            
            // Store code content in a map for safe retrieval
            if (!window.codeBlockContents) {
                window.codeBlockContents = new Map();
            }
            
            // Decode HTML entities in code for copying
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = code;
            const decodedCode = tempDiv.textContent || tempDiv.innerText;
            window.codeBlockContents.set(codeId, decodedCode);
            
            return `<div class="code-block-container">
                <div class="code-block-header">
                    ${lang ? `<span class="code-lang">${lang}</span>` : ''}
                    <button class="copy-code-btn" onclick="copyCodeBlock(this)" data-code-id="${codeId}" title="Copy code">
                        <svg class="copy-icon" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                            <path d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V2Z"/>
                            <path d="M2 6a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-2H6a3 3 0 0 1-3-3V6H2Z"/>
                        </svg>
                        <span class="copy-text">Copy</span>
                    </button>
                </div>
                <pre><code${attrs}>${code}</code></pre>
            </div>`;
        });
    }

    /**
     * Fix image rendering - ensure markdown images render as actual <img> tags
     */
    function fixImageRendering(html) {
        // marked.js should already handle this, but ensure images have proper styling
        return html.replace(/<img([^>]*)>/g, function(match, attrs) {
            // Add styling classes if not present
            if (!attrs.includes('class=')) {
                return `<img${attrs} class="markdown-image">`;
            }
            return match;
        });
    }

    /**
     * Escape HTML entities
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Copy code block content (called from HTML onclick)
     */
    window.copyCodeBlock = function(button) {
        const codeId = button.getAttribute('data-code-id');
        const code = window.codeBlockContents ? window.codeBlockContents.get(codeId) : null;
        
        if (!code) {
            console.error('Code content not found for ID:', codeId);
            const copyText = button.querySelector('.copy-text');
            copyText.textContent = 'Error!';
            button.classList.add('error');
            setTimeout(() => {
                copyText.textContent = 'Copy';
                button.classList.remove('error');
            }, 2000);
            return;
        }
        
        navigator.clipboard.writeText(code).then(() => {
            const originalText = button.querySelector('.copy-text').textContent;
            button.querySelector('.copy-text').textContent = 'Copied!';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.querySelector('.copy-text').textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            const copyText = button.querySelector('.copy-text');
            copyText.textContent = 'Error!';
            button.classList.add('error');
            setTimeout(() => {
                copyText.textContent = 'Copy';
                button.classList.remove('error');
            }, 2000);
        });
    };

    console.log('Renderer initialized:', {
        hasMarked: hasMarked,
        hasHighlight: hasHighlight
    });
})();
