// FILE: static/js/nested-parser.js
// DESCRIPTION: Stack-based parser for nested markdown containers
//              Handles codeblock-in-codeblock, quote-in-quote, table-in-codeblock, etc.
//
// Problem:
//   Standard markdown parsers use regex that matches first closing delimiter,
//   which breaks on nested structures like:
//   - ``` inside ```
//   - > inside >
//   - table inside codeblock
//   - codeblock inside table
//
// Solution:
//   Stack-based delimiter matching with depth tracking.

(function(global) {
    'use strict';

    /**
     * Parse markdown with proper nested container handling.
     * Uses stack-based delimiter matching.
     */
    class NestedContainerParser {
        constructor() {
            this.delimiters = {
                codeblock: { 
                    open: '```', 
                    close: '```', 
                    escape: true,
                    allowLang: true // ```python, ```mermaid, etc.
                },
                blockquote: { 
                    open: '>', 
                    close: '\n\n', 
                    escape: false,
                    allowLang: false
                },
                // Tables are detected differently - by | at start of line
            };
            
            // Track nesting depth for visual styling
            this.maxDepth = 10;
        }

        /**
         * Parse markdown and return preprocessed text.
         * Marked.js will handle the final rendering.
         */
        parse(markdown) {
            // First, protect nested codeblocks by replacing inner ones
            const protectedMd = this._protectNestedCodeblocks(markdown);
            return protectedMd;
        }

        /**
         * Protect nested codeblocks by escaping inner delimiters.
         * 
         * Example:
         *   Input:  ```outer\n```inner```\n```
         *   Output: ```outer\n&#96;&#96;&#96;inner&#96;&#96;&#96;\n```
         */
        _protectNestedCodeblocks(markdown) {
            const lines = markdown.split('\n');
            const result = [];
            const stack = []; // Stack of { index, lang, inBlock }
            let inCodeblock = false;
            let currentLang = '';
            let codeblockDepth = 0;

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];

                // Detect codeblock start/end
                const codeblockMatch = line.match(/^( {0,3})(`{3,})(.*)$/);
                
                if (codeblockMatch) {
                    const [, indent, ticks, lang] = codeblockMatch;
                    
                    if (!inCodeblock) {
                        // Opening codeblock
                        inCodeblock = true;
                        currentLang = lang.trim();
                        codeblockDepth = 0;
                        stack.push({ index: i, lang: currentLang, depth: codeblockDepth });
                        result.push(line);
                    } else {
                        // Could be closing OR nested opening
                        // Check if there's content after (lang specifier) = nested opening
                        const trimmedLang = lang.trim();
                        
                        if (trimmedLang && trimmedLang !== currentLang) {
                            // This is a nested codeblock opening!
                            // Escape it
                            codeblockDepth++;
                            const escapedTicks = '&#96;'.repeat(ticks.length);
                            result.push(`${indent}${escapedTicks}${lang}`);
                        } else if (codeblockDepth > 0) {
                            // This is a nested codeblock closing
                            // Escape it
                            codeblockDepth--;
                            const escapedTicks = '&#96;'.repeat(ticks.length);
                            result.push(`${indent}${escapedTicks}`);
                        } else {
                            // This is the main codeblock closing
                            inCodeblock = false;
                            currentLang = '';
                            stack.pop();
                            result.push(line);
                        }
                    }
                } else if (inCodeblock) {
                    // Inside codeblock - escape any ``` sequences in content
                    if (line.includes('```')) {
                        // Escape all ``` sequences in this line
                        const escaped = line.replace(/`{3,}/g, (match) => {
                            return '&#96;'.repeat(match.length);
                        });
                        result.push(escaped);
                    } else {
                        result.push(line);
                    }
                } else {
                    // Outside codeblock - check for nested blockquotes
                    const processedLine = this._processBlockquoteLine(line, i, lines);
                    result.push(processedLine);
                }
            }

            return result.join('\n');
        }

        /**
         * Process blockquote lines for proper nesting.
         * Adds depth markers for CSS styling.
         */
        _processBlockquoteLine(line, lineIndex, allLines) {
            // Count leading > characters
            const match = line.match(/^( {0,3}(> ?)+)/);
            
            if (match) {
                const quotePrefix = match[1];
                const depth = (quotePrefix.match(/>/g) || []).length;
                const rest = line.slice(quotePrefix.length);
                
                // Add depth class marker for CSS
                // We use data attribute which CSS can target
                if (depth > 1) {
                    // Mark as nested for CSS styling
                    return `<span class="quote-depth-${Math.min(depth, this.maxDepth)}">${quotePrefix}</span>${rest}`;
                }
            }
            
            return line;
        }

        /**
         * Parse and return structured data for debugging.
         */
        parseDebug(markdown) {
            const tokens = this._tokenize(markdown);
            return {
                tokens,
                depthMap: this._buildDepthMap(tokens),
                stats: {
                    totalTokens: tokens.length,
                    maxDepth: Math.max(...tokens.map(t => t.depth || 0), 0),
                    codeblockCount: tokens.filter(t => t.type === 'codeblock_open').length,
                    blockquoteCount: tokens.filter(t => t.type === 'blockquote_open').length,
                }
            };
        }

        /**
         * Tokenize markdown for debugging/analysis.
         */
        _tokenize(markdown) {
            const tokens = [];
            const stack = [];
            let i = 0;

            while (i < markdown.length) {
                // Check for codeblock opening
                if (markdown.slice(i, i + 3) === '```') {
                    // Find end of opening line
                    let endOfLine = markdown.indexOf('\n', i);
                    if (endOfLine === -1) endOfLine = markdown.length;
                    
                    const lang = markdown.slice(i + 3, endOfLine).trim();
                    const depth = stack.filter(s => s.type === 'codeblock').length;
                    
                    stack.push({ type: 'codeblock', start: i, depth });
                    tokens.push({ 
                        type: 'codeblock_open', 
                        depth, 
                        lang,
                        pos: i 
                    });
                    
                    i = endOfLine + 1;
                    continue;
                }

                // Check for codeblock closing (if in codeblock)
                if (stack.length > 0 && stack[stack.length - 1].type === 'codeblock') {
                    if (markdown.slice(i, i + 3) === '```' && 
                        (markdown[i + 3] === '\n' || markdown[i + 3] === '\n' || i + 3 === markdown.length)) {
                        const current = stack.pop();
                        tokens.push({ 
                            type: 'codeblock_close', 
                            depth: current.depth,
                            pos: i 
                        });
                        i += 3;
                        continue;
                    }
                }

                // Check for blockquote
                if (markdown[i] === '>' && (i === 0 || markdown[i - 1] === '\n')) {
                    const depth = stack.filter(s => s.type === 'blockquote').length;
                    stack.push({ type: 'blockquote', start: i, depth });
                    tokens.push({ type: 'blockquote_open', depth, pos: i });
                    i++;
                    // Skip space after >
                    if (markdown[i] === ' ') i++;
                    continue;
                }

                // Regular content
                tokens.push({ type: 'text', char: markdown[i], pos: i });
                i++;
            }

            // Close any unclosed containers
            while (stack.length > 0) {
                const current = stack.pop();
                tokens.push({ 
                    type: `${current.type}_close`, 
                    depth: current.depth,
                    pos: markdown.length 
                });
            }

            return tokens;
        }

        /**
         * Build depth map for visualization.
         */
        _buildDepthMap(tokens) {
            const map = [];
            let currentDepth = 0;

            for (const token of tokens) {
                if (token.type.endsWith('_open')) {
                    map.push({ pos: token.pos, type: 'enter', depth: currentDepth });
                    currentDepth++;
                } else if (token.type.endsWith('_close')) {
                    currentDepth--;
                    map.push({ pos: token.pos, type: 'exit', depth: currentDepth });
                }
            }

            return map;
        }
    }

    // Export to global scope
    global.NestedContainerParser = NestedContainerParser;

})(typeof window !== 'undefined' ? window : global);
