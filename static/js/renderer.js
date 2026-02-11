/**
 * Simple markdown renderer
 * Supports: bold, italic, code blocks, inline code, images, links, lists, headings, tables
 * @param {string} text - The markdown text to render
 * @returns {string} - The rendered HTML
 */
function renderMessageContent(text) {
    if (!text) return '';
    
    let html = String(text);
    
    // Store code blocks temporarily to prevent interference with other replacements
    const codeBlocks = [];
    html = html.replace(/```[\s\S]*?```/g, (match) => {
        codeBlocks.push(match);
        return `\x00CODEBLOCK${codeBlocks.length - 1}\x00`;
    });
    
    // Escape HTML 
    html = html.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;');
    
    // Images ![alt](url)
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">');
    
    // Links [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    
    // Bold **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
    
    // Italic *text* or _text_
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    html = html.replace(/_(.+?)_/g, '<em>$1</em>');
    
    // Inline code `code`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
    
    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    
    // Tables
    html = html.replace(/\|(.+)\|\n\|[-:| ]+\|\n((?:\|.+\|\n?)+)/g, (match, header, rows) => {
        const headers = header.split('|').filter(h => h.trim()).map(h => `<th>${h.trim()}</th>`).join('');
        const rowsHtml = rows.trim().split('\n').map(row => {
            const cells = row.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');
        return `<table><thead><tr>${headers}</tr></thead><tbody>${rowsHtml}</tbody></table>`;
    });
    
    // Lists
    html = html.replace(/^\* (.+)$/gm, '<li>$1</li>');
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*?<\/li>\s*)+/g, (match) => `<ul>${match}</ul>`);
    
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    
    // Restore code blocks and render them
    html = html.replace(/\x00CODEBLOCK(\d+)\x00/g, (match, index) => {
        const block = codeBlocks[parseInt(index)];
        const codeMatch = block.match(/```(\w+)?\s*([\s\S]*?)```/);
        if (codeMatch) {
            const code = codeMatch[2].trim()
                .replace(/&amp;/g, '&')
                .replace(/&lt;/g, '<')
                .replace(/&gt;/g, '>')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            return `<pre><code>${code}</code></pre>`;
        }
        return block;
    });
    
    return html;
}
