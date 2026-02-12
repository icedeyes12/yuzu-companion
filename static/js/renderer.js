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
    
    // Store inline code temporarily
    const inlineCodes = [];
    html = html.replace(/`([^`]+)`/g, (match, code) => {
        inlineCodes.push(code);
        return `\x00INLINECODE${inlineCodes.length - 1}\x00`;
    });
    
    // Store images and links temporarily to protect URLs from markdown processing
    const images = [];
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
        images.push({ alt, url });
        return `\x00IMAGE${images.length - 1}\x00`;
    });
    
    const links = [];
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, url) => {
        links.push({ text, url });
        return `\x00LINK${links.length - 1}\x00`;
    });
    
    // Escape HTML 
    html = html.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;');
    
    // Bold **text** or __text__
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
    
    // Italic *text* or _text_ (but not inside words or numbers)
    html = html.replace(/(?:^|[^a-zA-Z0-9_])\*(.+?)\*(?:[^a-zA-Z0-9_]|$)/g, (match, content) => {
        const before = match[0] !== '*' ? match[0] : '';
        const after = match[match.length - 1] !== '*' ? match[match.length - 1] : '';
        return `${before}<em>${content}</em>${after}`;
    });
    html = html.replace(/(?:^|[^a-zA-Z0-9_])_(.+?)_(?:[^a-zA-Z0-9_]|$)/g, (match, content) => {
        const before = match[0] !== '_' ? match[0] : '';
        const after = match[match.length - 1] !== '_' ? match[match.length - 1] : '';
        return `${before}<em>${content}</em>${after}`;
    });
    
    // Headers (all levels H1-H6)
    html = html.replace(/^###### (.+)$/gm, '<h6>$1</h6>');
    html = html.replace(/^##### (.+)$/gm, '<h5>$1</h5>');
    html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
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
    
    // Restore images
    html = html.replace(/\x00IMAGE(\d+)\x00/g, (match, index) => {
        const img = images[parseInt(index)];
        return `<img src="${img.url}" alt="${img.alt}">`;
    });
    
    // Restore links
    html = html.replace(/\x00LINK(\d+)\x00/g, (match, index) => {
        const link = links[parseInt(index)];
        return `<a href="${link.url}" target="_blank">${link.text}</a>`;
    });
    
    // Restore inline code
    html = html.replace(/\x00INLINECODE(\d+)\x00/g, (match, index) => {
        return `<code>${inlineCodes[parseInt(index)]}</code>`;
    });
    
    // Restore code blocks and render them
    html = html.replace(/\x00CODEBLOCK(\d+)\x00/g, (match, index) => {
        const block = codeBlocks[parseInt(index)];
        const codeMatch = block.match(/```(\w+)?\s*([\s\S]*?)```/);
        if (codeMatch) {
            // Extract code content (not yet HTML-escaped)
            const rawCode = codeMatch[2].trim();
            // Escape HTML entities for safe display
            const escapedCode = rawCode
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            return `<pre><code>${escapedCode}</code></pre>`;
        }
        return block;
    });
    
    return html;
}
