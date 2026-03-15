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
        const hasLongOutput = !image_url && (outputText.length > 500 || output.length > 10);
        const displayOutput = hasLongOutput 
            ? output.slice(0, 10).join('\n') + '\n...'
            : outputText;

        const card = document.createElement('div');
        card.className = `tool-card ${statusClass}`;
        
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
            cardHTML += `
                <div class="tool-card-output">
                    <pre>${displayOutput || '(no output)'}</pre>
                </div>
                ${hasLongOutput ? '<div class="tool-card-expand">Click to expand</div>' : ''}
            `;
        }
        
        card.innerHTML = cardHTML;

        // Add expand functionality for text output
        if (hasLongOutput && !image_url) {
            card.querySelector('.tool-card-expand').addEventListener('click', () => {
                const outputDiv = card.querySelector('.tool-card-output pre');
                if (outputDiv.textContent.includes('...')) {
                    outputDiv.textContent = outputText;
                    card.querySelector('.tool-card-expand').textContent = 'Click to collapse';
                } else {
                    outputDiv.textContent = displayOutput;
                    card.querySelector('.tool-card-expand').textContent = 'Click to expand';
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
