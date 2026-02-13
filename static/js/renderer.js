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
    
    // Function to check if highlight.js is available (may load after this script)
    function isHighlightAvailable() {
        return typeof hljs !== 'undefined' && typeof hljs.highlight === 'function';
    }

    // Configure marked.js if available
    if (hasMarked) {
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false,
            sanitize: false, // Allow HTML (needed for images)
            highlight: function(code, lang) {
                if (isHighlightAvailable() && lang) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (e) {
                        console.warn('Highlight.js error for language:', lang, e);
                        // Return code with language class so it can be highlighted later
                        return code;
                    }
                }
                return code;
            }
        });
        
        // Log configuration status
        console.log('Renderer initialized:', {
            marked: true,
            highlight: isHighlightAvailable(),
            markedVersion: typeof marked.parse === 'function' ? 'modern' : 'legacy'
        });
    } else {
        console.warn('marked.js not loaded - markdown rendering will use fallback');
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
                
                // Log for debugging
                if (html.includes('<img')) {
                    console.log('Image detected in rendered content');
                }
                
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
        // marked.js with sanitize: false should render <img> tags correctly
        // This function adds styling classes to all images
        return html.replace(/<img([^>]*)>/gi, function(match, attrs) {
            // Ensure images have the markdown-image class for styling
            if (!attrs.includes('class=')) {
                return `<img${attrs} class="markdown-image">`;
            } else if (!attrs.includes('markdown-image')) {
                // Add to existing class
                return match.replace(/class="([^"]*)"/, 'class="$1 markdown-image"');
            }
            return match;
        });
    }

    /**
     * Apply syntax highlighting to code blocks that may have been missed
     * This is called after DOM insertion for any dynamically added content
     */
    window.applyCodeHighlighting = function(container) {
        if (!isHighlightAvailable()) {
            console.log('highlight.js not available for post-processing');
            return;
        }
        
        const codeBlocks = container.querySelectorAll('pre code');
        codeBlocks.forEach(block => {
            // Only highlight if not already highlighted
            if (!block.classList.contains('hljs')) {
                try {
                    hljs.highlightElement(block);
                } catch (e) {
                    console.warn('Error highlighting code block:', e);
                }
            }
        });
    };

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
