// FILE: static/js/renderer.js
// DESCRIPTION: Markdown renderer using marked.js v18 with syntax highlighting
//              Supports: mermaid diagrams, nested containers, async rendering

class MessageRenderer {
    constructor() {
        this.isMarkedReady = false;
        this.isHighlightReady = false;
        this.isMermaidReady = false;
        this.nestedParser = null;
        this.renderQueue = [];
        this.initializeLibraries();
    }

    initializeLibraries() {
        // Check if marked is available
        if (typeof marked !== 'undefined') {
            this.isMarkedReady = true;
            this.configureMarked();
        } else {
            console.warn('marked.js not loaded');
        }

        // Check if highlight.js is available
        if (typeof hljs !== 'undefined') {
            this.isHighlightReady = true;
        } else {
            console.warn('highlight.js not loaded');
        }

        // Check if mermaid is available
        if (typeof mermaid !== 'undefined') {
            this.isMermaidReady = true;
            this.initializeMermaid();
        } else {
            console.warn('mermaid.js not loaded');
        }

        // Initialize nested container parser
        if (typeof NestedContainerParser !== 'undefined') {
            this.nestedParser = new NestedContainerParser();
        }
    }

    initializeMermaid() {
        if (typeof mermaid === 'undefined') return;
        
        // Determine theme based on current data-theme
        const theme = this._getMermaidTheme();
        
        mermaid.initialize({
            startOnLoad: false, // We'll call run() manually after render
            theme: theme,
            securityLevel: 'loose',
            flowchart: {
                useMaxWidth: true,
                htmlLabels: true,
            },
            sequence: {
                useMaxWidth: true,
            },
        });
        
        console.log('[Renderer] Mermaid initialized with theme:', theme);
    }

    _getMermaidTheme() {
        const bodyTheme = document.body.getAttribute('data-theme') || 'dark';
        // Dark themes
        if (['dark', 'dark-lavender'].includes(bodyTheme)) {
            return 'dark';
        }
        // Light themes
        return 'default';
    }

    normalizeLanguageAlias(lang) {
        if (!lang) return null;
        const lower = lang.toLowerCase().trim();
        if (!lower || lower === 'text' || lower === 'plaintext') return null;

        const familyMap = {
            // Shell / CLI family → bash
            'sh': 'bash', 'zsh': 'bash', 'fish': 'bash', 'shell': 'bash',
            'docker': 'bash', 'dockerfile': 'bash', 'compose': 'bash',
            'make': 'bash', 'makefile': 'bash', 'cmake': 'bash',
            'powershell': 'bash', 'ps1': 'bash', 'pwsh': 'bash',
            'bat': 'bash', 'cmd': 'bash',

            // JavaScript family → javascript
            'js': 'javascript', 'mjs': 'javascript', 'cjs': 'javascript', 'jsx': 'javascript',
            'node': 'javascript', 'deno': 'javascript',

            // TypeScript family → typescript
            'ts': 'typescript', 'tsx': 'typescript',

            // SQL family → sql
            'mysql': 'sql', 'postgres': 'sql', 'postgresql': 'sql',
            'sqlite': 'sql', 'tsql': 'sql', 'plsql': 'sql', 'mssql': 'sql',

            // Config / data family → json
            'yml': 'json', 'yaml': 'json', 'toml': 'json', 'ini': 'json',
            'env': 'json', 'dotenv': 'json',
            'terraform': 'json', 'hcl': 'json', 'tf': 'json',

            // Markup family → html
            'html': 'html', 'xhtml': 'html', 'svg': 'xml', 'rss': 'xml', 'atom': 'xml',

            // Python aliases → python
            'py': 'python', 'python3': 'python',

            // Markdown aliases → markdown
            'md': 'markdown', 'mdx': 'markdown',

            // Ruby aliases → ruby
            'rb': 'ruby',

            // Rust aliases → rust
            'rs': 'rust',

            // Kotlin aliases → kotlin
            'kt': 'kotlin', 'kts': 'kotlin',

            // C# aliases → csharp
            'cs': 'csharp',

            // C++ aliases → cpp
            'hpp': 'cpp', 'cc': 'cpp', 'cxx': 'cpp', 'hxx': 'cpp',

            // C aliases → c
            'h': 'c',

            // Objective-C aliases → objectivec
            'objc': 'objectivec', 'mm': 'objectivec',

            // VB aliases → vbnet
            'vb': 'vbnet',

            // GraphQL aliases → graphql
            'gql': 'graphql',

            // LaTeX aliases → latex
            'tex': 'latex',

            // Assembly aliases → x86asm
            'asm': 'x86asm',
            
            // Mermaid → handled separately
            'mermaid': 'mermaid',
        };

        return familyMap[lower] || lower;
    }

    configureMarked() {
        if (typeof marked === 'undefined') return;
        
        const self = this;

        // marked.js v18 uses setOptions + custom extensions
        marked.setOptions({
            gfm: true,
            breaks: true,
            pedantic: false,
            headerIds: true,
            mangle: false,
        });

        // Custom code block renderer using marked.use() for v18
        marked.use({
            renderer: {
                code(code, language) {
                    // Ensure code is a string (marked v18 sometimes passes objects)
                    code = typeof code === 'string' ? code : String(code || '');
                    const originalLabel = language ? language.trim() : '';
                    
                    // Handle mermaid diagrams
                    if (originalLabel === 'mermaid' && self.isMermaidReady) {
                        const codeStr = typeof code === 'string' ? code : String(code || '');
                        const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
                        return `<div class="mermaid-container"><pre class="mermaid" id="${id}">${self.escapeHtml(codeStr)}</pre></div>`;
                    }
                    
                    const normalizedLang = self.normalizeLanguageAlias(language);
                    const fallbackLang = 'plaintext';
                    let highlightLang = fallbackLang;
                    
                    const isHtmlContent = normalizedLang === 'xml' || normalizedLang === 'html';
                    
                    if (normalizedLang && self.isHighlightReady && typeof hljs !== 'undefined' && hljs.getLanguage(normalizedLang)) {
                        highlightLang = normalizedLang;
                    }
                    
                    const isHtml = isHtmlContent || self._isHtmlCode(code);
                    const highlighted = self.isHighlightReady
                        ? hljs.highlight(code, { language: highlightLang, ignoreIllegals: true }).value
                        : self.escapeHtml(code);
                    
                    const displayLabel = originalLabel || 'code';
                    const previewBtn = isHtml ? `<button class="preview-code-btn" data-code="${encodeURIComponent(code)}" onclick="renderer.showHtmlPreviewModal(this)"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8z"/><circle cx="12" cy="12" r="3"/></svg>Preview</button>` : '';
                    
                    return `<div class="code-block-container"><div class="code-block-header"><span class="code-language">${displayLabel}</span>${previewBtn}<button class="copy-code-btn" onclick="renderer.copyCode(this)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>Copy</button></div><pre><code class="hljs language-${highlightLang}">${highlighted}</code></pre></div>`;
                },
                
                image(href, title, text) {
                    const resolved = self.resolveImageToken(href, title, text);
                    const normalizedHref = self.normalizeImagePath(resolved.href);
                    const titleAttr = resolved.title ? ` title="${self.escapeHtml(resolved.title)}"` : '';
                    const altAttr = resolved.text ? ` alt="${self.escapeHtml(resolved.text)}"` : '';
                    const errorHandler = `onerror="this.onerror=null; this.outerHTML='<div class=\\'image-error\\'>⚠️ Image not found</div>';"`;
                    
                    return `<img src="${self.escapeHtml(normalizedHref)}"${altAttr}${titleAttr} class="markdown-image" loading="lazy" ${errorHandler} />`;
                }
            }
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    _isHtmlCode(code) {
        // Ensure code is a string (marked v18 sometimes passes objects)
        const codeStr = typeof code === 'string' ? code : String(code || '');
        const trimmed = codeStr.trim();
        return trimmed.startsWith('<!DOCTYPE') ||
               trimmed.startsWith('<html') ||
               (trimmed.startsWith('<head') && trimmed.includes('<body')) ||
               (trimmed.includes('<html') && trimmed.includes('<body'));
    }

    normalizeImagePath(path) {
        if (!path) return path;
        const resolved = this.resolveImageToken(path);
        let rawPath = typeof resolved.href === 'string' ? resolved.href : String(resolved.href);
        const cleaned = rawPath.trim().replace(/\\/g, '/');
        
        if (/^(https?:)?\/\//i.test(cleaned) || cleaned.startsWith('data:') || cleaned.startsWith('/')) {
            return cleaned;
        }
        if (cleaned.startsWith('static/')) {
            return `/${cleaned}`;
        }
        if (cleaned.startsWith('uploads/') || cleaned.startsWith('generated_images/')) {
            return `/static/${cleaned}`;
        }
        return cleaned;
    }

    /**
     * Main render method - now async for marked.js v18
     */
    async render(markdown) {
        if (markdown === null || markdown === undefined) return '';
        const safeMarkdown = typeof markdown === 'string' ? markdown : String(markdown);

        if (!this.isMarkedReady) {
            console.warn('marked.js not ready, returning plain text');
            return this.renderWithoutMarked(safeMarkdown);
        }

        try {
            // Step 1: Pre-process nested containers (protect nested codeblocks)
            let processedMarkdown = safeMarkdown;
            if (this.nestedParser) {
                processedMarkdown = this.nestedParser.parse(safeMarkdown);
            }
            
            // Step 2: Pre-process thought blocks
            processedMarkdown = this.preprocessThoughtBlocks(processedMarkdown);
            
            // Step 3: Pre-process image patterns
            processedMarkdown = this.preprocessThoughtBlocks(processedMarkdown);
        processedMarkdown = this.preprocessGeneratedImages(processedMarkdown);
            
            // Step 3: Parse markdown (marked v18 returns Promise by default)
            let html = await marked.parse(processedMarkdown);
            
            // Step 4: Post-process (tables, callouts, etc.)
            html = this.postProcessHTML(html);
            
            // Step 5: Initialize mermaid diagrams (async)
            setTimeout(() => {
                this.initializeMermaidDiagrams();
            }, 0);
            
            return html;
        } catch (error) {
            console.error('Render error:', error, safeMarkdown);
            return `<pre class="render-error">${this.escapeHtml(safeMarkdown)}</pre>`;
        }
    }

    /**
     * Initialize mermaid diagrams in rendered HTML
     */
    async initializeMermaidDiagrams() {
        if (!this.isMermaidReady) return;
        
        const mermaidElements = document.querySelectorAll('.mermaid:not([data-processed])');
        if (mermaidElements.length === 0) return;
        
        console.log('[Renderer] Initializing', mermaidElements.length, 'mermaid diagrams');
        
        mermaidElements.forEach(el => {
            el.setAttribute('data-processed', 'true');
        });
        
        try {
            // Remove data-processed attribute and let mermaid re-process
            mermaidElements.forEach(el => {
                el.removeAttribute('data-processed');
            });
            await mermaid.run({ querySelector: '.mermaid' });
            console.log('[Renderer] Mermaid diagrams initialized');
        } catch (error) {
            console.error('[Renderer] Mermaid initialization error:', error);
        }
    }

    // === Legacy sync render for backward compatibility ===
    renderSync(markdown) {
        // For code that expects sync rendering
        if (!this.isMarkedReady) {
            return this.renderWithoutMarked(markdown);
        }
        
        let processedMarkdown = markdown;
        if (this.nestedParser) {
            processedMarkdown = this.nestedParser.parse(markdown);
        }
        processedMarkdown = this.preprocessThoughtBlocks(processedMarkdown);
        processedMarkdown = this.preprocessGeneratedImages(processedMarkdown);
        
        // marked v18: Use lexer + parser for true sync rendering
        try {
            const tokens = marked.lexer(processedMarkdown);
            let html = this._renderTokensSync(tokens);
            setTimeout(() => this.initializeMermaidDiagrams(), 0);
            return html;
        } catch (e) {
            console.error('[Renderer] renderSync error:', e);
            return this.renderWithoutMarked(markdown);
        }
    }
    
    _renderTokensSync(tokens) {
        // Manual sync rendering using marked's internal parser
        let html = '';
        for (const token of tokens) {
            html += this._renderTokenSync(token);
        }
        return html;
    }
    
    _renderTokenSync(token) {
        // Token renderer for sync mode - handles all marked.js v18 token types
        switch (token.type) {
            case 'heading':
                return `<h${token.depth}>${this._renderInlineSync(token.tokens || token.text)}</h${token.depth}>`;
            case 'paragraph':
                return `<p>${this._renderInlineSync(token.tokens || token.text)}</p>`;
            case 'code':
                return this._renderCodeBlock(token);
            case 'blockquote':
                return `<blockquote>${this._renderTokensSync(token.tokens || [])}</blockquote>`;
            case 'list':
                return this._renderListSync(token);
            case 'list_item':
                return `<li>${this._renderInlineSync(token.tokens || token.text || '')}</li>`;
            case 'table':
                return this._renderTableSync(token);
            case 'image':
                // Block-level image (standalone image on its own line)
                const imgSrc = this.normalizeImagePath(token.href || '');
                const imgAlt = token.text || '';
                const imgTitle = token.title ? ` title="${this.escapeHtml(token.title)}"` : '';
                const errorHandler = `onerror="this.onerror=null; this.outerHTML='<div class=\\'image-error\\'>⚠️ Image not found</div>';"`;
                return `<img src="${this.escapeHtml(imgSrc)}" alt="${this.escapeHtml(imgAlt)}"${imgTitle} class="markdown-image" loading="lazy" ${errorHandler} />`;
            case 'space':
                return '';
            case 'hr':
                return '<hr>';
            case 'html':
                return token.raw || '';
            case 'text':
                return token.raw || token.text || '';
            default:
                return token.raw || '';
        }
    }
    
    _renderInlineSync(tokensOrText) {
        // Handle inline tokens (bold, italic, code, links, etc.)
        if (typeof tokensOrText === 'string') {
            return this.escapeHtml(tokensOrText);
        }
        
        if (!Array.isArray(tokensOrText)) {
            return this.escapeHtml(String(tokensOrText || ''));
        }
        
        let html = '';
        for (const token of tokensOrText) {
            switch (token.type) {
                case 'text':
                    html += this.escapeHtml(token.text || '');
                    break;
                case 'strong':
                    html += `<strong>${this._renderInlineSync(token.tokens || token.text || '')}</strong>`;
                    break;
                case 'em':
                    html += `<em>${this._renderInlineSync(token.tokens || token.text || '')}</em>`;
                    break;
                case 'codespan':
                    html += `<code>${this.escapeHtml(token.text || '')}</code>`;
                    break;
                case 'link':
                    html += `<a href="${token.href || '#'}">${this._renderInlineSync(token.tokens || token.text || '')}</a>`;
                    break;
                case 'image':
                    html += `<img src="${token.href || ''}" alt="${token.text || ''}">`;
                    break;
                case 'br':
                    html += '<br>';
                    break;
                case 'del':
                    html += `<del>${this._renderInlineSync(token.tokens || token.text || '')}</del>`;
                    break;
                case 'html':
                    html += token.raw || '';
                    break;
                default:
                    html += token.raw || token.text || '';
            }
        }
        return html;
    }
    
    _renderTableSync(token) {
        if (!token.header || !token.rows) {
            return '';
        }
        
        let html = '<div class="table-container"><table><thead><tr>';
        
        // Header
        for (const cell of token.header) {
            html += `<th>${this._renderInlineSync(cell.tokens || cell.text || '')}</th>`;
        }
        html += '</tr></thead><tbody>';
        
        // Rows
        for (const row of token.rows) {
            html += '<tr>';
            for (const cell of row) {
                html += `<td>${this._renderInlineSync(cell.tokens || cell.text || '')}</td>`;
            }
            html += '</tr>';
        }
        
        html += '</tbody></table></div>';
        return html;
    }
    
    _renderCodeBlock(token) {
        const lang = token.lang || '';
        const code = token.text || '';
        
        // Handle mermaid
        if (lang === 'mermaid' && this.isMermaidReady) {
            const codeStr = typeof code === 'string' ? code : String(code || '');
            const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
            // Mermaid needs raw text, not escaped HTML
            return `<div class="mermaid-container"><pre class="mermaid" id="${id}">${codeStr}</pre></div>`;
        }
        
        // Highlight with hljs
        const normalizedLang = this.normalizeLanguageAlias(lang);
        const fallbackLang = 'plaintext';
        let highlightLang = fallbackLang;
        
        if (normalizedLang && this.isHighlightReady && hljs.getLanguage(normalizedLang)) {
            highlightLang = normalizedLang;
        }
        
        const highlighted = this.isHighlightReady
            ? hljs.highlight(code, { language: highlightLang, ignoreIllegals: true }).value
            : this.escapeHtml(code);
        
        return `<div class="code-block-container"><div class="code-block-header"><span class="code-language">${lang || 'code'}</span><button class="copy-code-btn" onclick="renderer.copyCode(this)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>Copy</button></div><pre><code class="hljs language-${highlightLang}">${highlighted}</code></pre></div>`;
    }
    
    _renderListSync(token) {
        const tag = token.ordered ? 'ol' : 'ul';
        const start = token.start ? ` start="${token.start}"` : '';
        let items = '';
        
        if (token.items && Array.isArray(token.items)) {
            for (const item of token.items) {
                // Check if item has nested tokens (could be a nested list)
                let itemContent = '';
                if (item.tokens && Array.isArray(item.tokens)) {
                    // Render all tokens in the item (text, nested lists, etc.)
                    for (const t of item.tokens) {
                        if (t.type === 'list') {
                            // Nested list - recurse
                            itemContent += this._renderListSync(t);
                        } else if (t.type === 'text') {
                            itemContent += this.escapeHtml(t.text || '');
                        } else {
                            // Other inline elements
                            itemContent += this._renderInlineSync([t]);
                        }
                    }
                } else {
                    // Fallback to text
                    itemContent = this.escapeHtml(item.text || '');
                }
                items += `<li>${itemContent}</li>`;
            }
        }
        
        return `<${tag}${start}>${items}</${tag}>`;
    }

    preprocessThoughtBlocks(text) {
        // Convert <thought>...</thought> to a div that survives marked.js
        const sourceText = typeof text === 'string' ? text : String(text || '');
        
        // Match <thought>...</thought> blocks (multiline)
        const thoughtPattern = /<thought>([\s\S]*?)<\/thought>/gi;
        
        let processed = sourceText.replace(thoughtPattern, (match, content) => {
            // Wrap in a div that will be processed by postProcessHTML
            const trimmedContent = content.trim();
            return `<div class="thought-block-raw" data-thought="${encodeURIComponent(trimmedContent)}"></div>`;
        });
        
        return processed;
    }

    preprocessGeneratedImages(text) {
        const sourceText = typeof text === 'string' ? text : String(text || '');
        
        // Match image patterns including space after !
        const imagePattern = /!\s*\[([^\]]*)\]\s*\n?\s*\(([^)]+)\)/g;
        
        let normalizedText = sourceText.replace(/\r\n/g, '\n');
        normalizedText = normalizedText.replace(imagePattern, (match, alt, src) => {
            const trimmedSrc = src.trim();
            const encodedSrc = trimmedSrc.replace(/ /g, '%20');
            return `![${alt}](${encodedSrc})`;
        });
        
        return normalizedText;
    }

    _renderThinkingBlock(thought) {
        // Create collapsible thinking block
        const id = 'thought-' + Math.random().toString(36).substr(2, 9);
        
        // Parse thought content (Planning:, Tools:, etc.)
        let planning = '';
        let tools = [];
        let content = thought;
        
        // Extract planning section
        const planningMatch = thought.match(/Planning:\s*(.+?)(?:\n|$)/i);
        if (planningMatch) {
            planning = planningMatch[1];
        }
        
        // Extract tools section
        const toolsMatch = thought.match(/Tools:\s*(.+?)(?:\n|$)/i);
        if (toolsMatch) {
            tools = toolsMatch[1].split(',').map(t => t.trim()).filter(t => t);
        }
        
        // Build HTML
        let html = `
            <div class="thinking-block">
                <details>
                    <summary class="thinking-summary">
                        <span class="thinking-icon">💭</span>
                        <span class="thinking-label">Thinking</span>
                        ${planning ? `<span class="thinking-planning">${this.escapeHtml(planning)}</span>` : ''}
                    </summary>
                    <div class="thought-content">
                        <div class="thought-text">${this.escapeHtml(content)}</div>
                        ${tools.length > 0 ? `
                            <div class="thought-tools">
                                ${tools.map(t => `<span class="tool-badge">${this.escapeHtml(t)}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                </details>
            </div>
        `;
        
        return html;
    }
    
    postProcessHTML(html) {
        const temp = document.createElement('div');
        temp.innerHTML = html;
        
        // 1. Wrap tables
        const tables = temp.querySelectorAll('table');
        tables.forEach(table => {
            if (!table.parentElement?.classList.contains('table-container')) {
                const wrapper = document.createElement('div');
                wrapper.className = 'table-container';
                table.parentNode.insertBefore(wrapper, table);
                wrapper.appendChild(table);
            }
        });
        
        // 2. Process callouts
        const blockquotes = temp.querySelectorAll('blockquote');
        blockquotes.forEach(blockquote => {
            const firstChild = blockquote.firstElementChild;
            if (firstChild?.textContent) {
                const text = firstChild.textContent.trim();
                const calloutMatch = text.match(/^\[!(NOTE|WARNING|INFO|TIP|IMPORTANT|CAUTION)\]/i);
                
                if (calloutMatch) {
                    const calloutType = calloutMatch[1].toLowerCase();
                    blockquote.classList.add('callout', `callout-${calloutType}`);
                    firstChild.textContent = text.replace(/^\[!(?:NOTE|WARNING|INFO|TIP|IMPORTANT|CAUTION)\]\s*/i, '');
                }
            }
        });
        
        // 3. Process thinking blocks (from preprocessThoughtBlocks)
        const thinkingBlocks = temp.querySelectorAll('.thought-block-raw');
        thinkingBlocks.forEach(block => {
            const encoded = block.getAttribute('data-thought') || '';
            try {
                const thought = decodeURIComponent(encoded);
                const rendered = this._renderThinkingBlock(thought);
                const wrapper = document.createElement('div');
                wrapper.innerHTML = rendered;
                if (wrapper.firstElementChild) {
                    block.replaceWith(wrapper.firstElementChild);
                }
            } catch (e) {
                console.error('[Renderer] Failed to process thought block:', e);
            }
        });
        
        // 4. Apply highlight.js to unprocessed code blocks
        if (this.isHighlightReady) {
            const codeBlocks = temp.querySelectorAll('pre code:not(.hljs)');
            codeBlocks.forEach(block => {
                if (block.className.includes('language-')) {
                    hljs.highlightElement(block);
                }
            });
        }
        
        return temp.innerHTML;
    }

    renderWithoutMarked(markdown) {
        const processed = this.preprocessGeneratedImages(markdown);
        let html = this.escapeHtml(processed);

        html = html.replace(/!\s*\[([^\]]*)\]\s*\(([^)]+)\)/g, (match, alt, src) => {
            const normalizedHref = this.normalizeImagePath(src);
            return `<img src="${this.escapeHtml(normalizedHref)}" alt="${this.escapeHtml(alt || 'Image')}" class="markdown-image" loading="lazy" />`;
        });

        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    copyCode(button) {
        if (!button) return;
        const codeBlock = button.closest('.code-block-container');
        if (!codeBlock) return;
        const code = codeBlock.querySelector('code');
        if (!code) return;
        const text = code.textContent;
        
        navigator.clipboard.writeText(text).then(() => {
            const originalText = button.innerHTML;
            button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>Copied!`;
            button.classList.add('copied');
            
            setTimeout(() => {
                button.innerHTML = originalText;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy code:', err);
        });
    }

    renderMessage(content, isUser = false) {
        // Backward compatible sync render
        return this.renderSync(content);
    }

    containsImageMarkdown(content) {
        if (!content) return false;
        return /!\s*\[[^\]]*\]\s*\n?\s*\([^)]+\)/.test(String(content));
    }

    resolveImageToken(href, title = '', text = '') {
        if (href && typeof href === 'object') {
            return {
                href: href.href || href.url || '',
                title: href.title || title || '',
                text: href.text || text || ''
            };
        }
        return { href, title, text };
    }

    showHtmlPreviewModal(btn) {
        const rawCode = decodeURIComponent(btn.dataset.code || '');
        const modal = document.getElementById('html-preview-modal');
        const iframe = document.getElementById('preview-iframe');
        if (!modal || !iframe || !rawCode) return;
        
        let code = rawCode
            .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&').replace(/&quot;/g, '"')
            .replace(/&#39;/g, "'").replace(/&#x27;/g, "'");
        
        modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        iframe.srcdoc = code;
    }

    closeHtmlModal() {
        const modal = document.getElementById('html-preview-modal');
        if (modal) modal.classList.remove('active', 'fullscreen');
        document.body.style.overflow = '';
    }

    togglePreviewTheme() {
        const body = document.getElementById('preview-body');
        const btn = document.getElementById('theme-toggle-btn');
        if (!body || !btn) return;
        
        const isLight = body.classList.toggle('preview-body-light');
        btn.classList.toggle('active', isLight);
    }

    togglePreviewFullscreen() {
        const modal = document.getElementById('html-preview-modal');
        const btn = document.getElementById('fullscreen-toggle-btn');
        if (!modal || !btn) return;
        
        const isFull = modal.classList.toggle('fullscreen');
        btn.classList.toggle('active', isFull);
    }
}

// Create global renderer instance
const renderer = new MessageRenderer();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { MessageRenderer, renderer };
}

// === HTML Preview Modal ===
document.addEventListener('click', function(e) {
    var btn = e.target.closest('.preview-code-btn');
    if (!btn) return;
    var rawCode = btn.getAttribute('data-code') || '';
    try { rawCode = decodeURIComponent(rawCode); } catch(err) {}
    if (rawCode) renderer.showHtmlPreviewModal(rawCode);
});

