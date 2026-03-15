/**
 * Tool Cards System - Beautiful tool execution display
 * Shows tool results as styled cards instead of plain markdown
 */

class ToolCards {
    constructor() {
        this.icons = {
            image: '🖼️',
            request: '🌐',
            memory: '🧠',
            mcp: '🔌',
            shell: '⚡',
            filesystem: '📁',
            fetch: '📡',
            default: '🔧'
        };
    }

    /**
     * Parse tool markdown contract and extract info
     */
    parseToolContract(markdown) {
        const result = {
            tool_name: 'unknown',
            command: '',
            output: [],
            isError: false,
            server_name: null,
            image_url: null
        };

        // Extract summary/tool name
        const summaryMatch = markdown.match(/<summary>🔧\s*(.+?)<\/summary>/);
        if (summaryMatch) {
            result.tool_name = summaryMatch[1].trim();
        }

        // Extract command from bash block
        const commandMatch = markdown.match(/```bash\n\S+\$\s*(.+?)\n```/);
        if (commandMatch) {
            result.command = commandMatch[1].trim();
            // Check if MCP command
            if (result.command.startsWith('MCP:')) {
                const parts = result.command.split(':');
                if (parts.length >= 2) {
                    result.server_name = parts[1];
                }
            }
        }

        // Extract output (blockquote lines)
        const outputMatch = markdown.match(/```[\s\S]*?```\n\n((?:> .+\n?)+)/);
        if (outputMatch) {
            result.output = outputMatch[1]
                .split('\n')
                .map(line => line.replace(/^>\s*/, ''))
                .filter(line => line.trim());
        }

        // Check for error
        result.isError = markdown.includes('Error:') || 
                        markdown.includes('❌') ||
                        result.output.some(line => line.includes('Error:'));

        // Extract image URL from output (for image generation tools)
        const imageMatch = markdown.match(/https?:\/\/[^\s]+\.(?:png|jpg|jpeg|gif|webp)/i) ||
                          markdown.match(/static\/generated_images\/[^\s]+/);
        if (imageMatch) {
            result.image_url = imageMatch[0];
        }

        return result;
    }

    /**
     * Get icon for tool type
     */
    getIcon(toolName, serverName) {
        if (serverName) return this.icons.mcp;
        if (toolName.includes('image')) return this.icons.image;
        if (toolName.includes('request')) return this.icons.request;
        if (toolName.includes('memory')) return this.icons.memory;
        if (toolName.includes('shell')) return this.icons.shell;
        if (toolName.includes('filesystem')) return this.icons.filesystem;
        if (toolName.includes('fetch')) return this.icons.fetch;
        return this.icons.default;
    }

    /**
     * Format command for display
     */
    formatCommand(command) {
        if (command.length > 80) {
            return command.substring(0, 80) + '...';
        }
        return command;
    }

    /**
     * Render a tool card
     */
    renderCard(toolData) {
        const { tool_name, command, output, isError, server_name, image_url } = toolData;
        const icon = this.getIcon(tool_name, server_name);
        const statusClass = isError ? 'tool-card-error' : 'tool-card-success';
        const statusIcon = isError ? '❌' : '✅';
        const isImageTool = tool_name.includes('image') || image_url;
        
        // Format output
        const outputText = output.join('\n');
        const outputLength = outputText.length;
        const isLongOutput = !image_url && (outputLength > 500 || output.length > 10);
        const isVeryLongOutput = !image_url && (outputLength > 2000 || output.length > 50);
        
        // Truncated output for display
        const maxLines = isVeryLongOutput ? 20 : 10;
        const displayOutput = isLongOutput 
            ? output.slice(0, maxLines).join('\n') + (output.length > maxLines ? '\n...' : '')
            : outputText;

        const card = document.createElement('div');
        card.className = `tool-card ${statusClass}`;
        card.dataset.fullOutput = outputText; // Store full output for copy
        
        // Build card HTML
        let cardHTML = `
            <div class="tool-card-header">
                <span class="tool-card-icon">${icon}</span>
                <span class="tool-card-name">${tool_name}</span>
                <span class="tool-card-status">${statusIcon}</span>
            </div>
            <div class="tool-card-command">
                <code>${this.formatCommand(command)}</code>
            </div>
        `;
        
        // For image tools, show the image instead of text output
        if (image_url) {
            const fullImageUrl = image_url.startsWith('http') ? image_url : '/' + image_url;
            cardHTML += `
                <div class="tool-card-image">
                    <img src="${fullImageUrl}" alt="Generated image" loading="lazy" 
                         style="max-width: 100%; border-radius: 8px; margin-top: 12px;"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <div style="display: none; padding: 12px; color: #ff6b6b;">
                        Image failed to load: ${image_url}
                    </div>
                </div>
            `;
        } else {
            // Text output for non-image tools
            const outputSizeInfo = isLongOutput ? `<span class="tool-card-output-size">${outputLength.toLocaleString()} chars</span>` : '';
            const fadeClass = isLongOutput ? 'tool-card-output-fade' : '';
            
            cardHTML += `
                <div class="tool-card-output ${fadeClass}">
                    <pre>${displayOutput || '(no output)'}</pre>
                    ${outputSizeInfo}
                </div>
                <div class="tool-card-actions">
                    <button class="tool-card-copy-btn" title="Copy output to clipboard">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                        </svg>
                        <span>Copy</span>
                    </button>
                    ${isLongOutput ? `
                    <button class="tool-card-expand-btn">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                        <span>Show Full Output</span>
                    </button>
                    ` : ''}
                </div>
            `;
        }
        
        card.innerHTML = cardHTML;

        // Add copy functionality
        const copyBtn = card.querySelector('.tool-card-copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                const fullOutput = card.dataset.fullOutput || outputText;
                navigator.clipboard.writeText(fullOutput).then(() => {
                    copyBtn.classList.add('copied');
                    copyBtn.querySelector('span').textContent = 'Copied!';
                    setTimeout(() => {
                        copyBtn.classList.remove('copied');
                        copyBtn.querySelector('span').textContent = 'Copy';
                    }, 2000);
                }).catch(err => {
                    console.error('Failed to copy:', err);
                    copyBtn.querySelector('span').textContent = 'Failed';
                    setTimeout(() => {
                        copyBtn.querySelector('span').textContent = 'Copy';
                    }, 2000);
                });
            });
        }

        // Add expand functionality
        const expandBtn = card.querySelector('.tool-card-expand-btn');
        if (expandBtn) {
            expandBtn.addEventListener('click', () => {
                const outputDiv = card.querySelector('.tool-card-output pre');
                const outputContainer = card.querySelector('.tool-card-output');
                const span = expandBtn.querySelector('span');
                const svg = expandBtn.querySelector('svg');
                
                if (span.textContent === 'Show Full Output') {
                    outputDiv.textContent = outputText;
                    span.textContent = 'Show Less';
                    svg.style.transform = 'rotate(180deg)';
                    outputContainer.classList.remove('tool-card-output-fade');
                } else {
                    outputDiv.textContent = displayOutput;
                    span.textContent = 'Show Full Output';
                    svg.style.transform = 'rotate(0deg)';
                    if (isLongOutput) {
                        outputContainer.classList.add('tool-card-output-fade');
                    }
                }
            });
        }

        return card;
    }

    /**
     * Check if content is a tool contract
     */
    isToolContract(content) {
        if (!content || typeof content !== 'string') return false;
        const trimmed = content.trim();
        return trimmed.startsWith('<details>') && 
               trimmed.includes('<summary>🔧') &&
               trimmed.includes('```bash');
    }
}

// Create global instance
window.toolCards = new ToolCards();
