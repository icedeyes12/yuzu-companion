// renderer.js - Simple markdown renderer (no external dependencies)

// Simple markdown parser
function renderMessageContent(text) {
  if (!text) return '';
  
  let html = String(text);
  
  // Protect code blocks first
  const codeBlocks = [];
  html = html.replace(/```(\w*)\n([\s\S]*?)\n```/g, (match, lang, code) => {
    const placeholder = `__CODE_BLOCK_${codeBlocks.length}__`;
    codeBlocks.push({ lang: lang || 'text', code: code.trim() });
    return placeholder;
  });
  
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  
  // Bold and italic
  html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  
  // Headings
  html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
  html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
  html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
  
  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  
  // Lists
  html = html.replace(/^- (.*?)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
  
  // Blockquotes
  html = html.replace(/^> (.*?)$/gm, '<blockquote>$1</blockquote>');
  
  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr>');
  
  // Tables
  html = html.replace(/\|(.+)\|\n\|[-:\s|]+\|\n((?:\|.+\|\n?)+)/g, (match, header, body) => {
    const headers = header.split('|').filter(h => h.trim()).map(h => `<th>${h.trim()}</th>`).join('');
    const rows = body.trim().split('\n').map(row => {
      const cells = row.split('|').filter(c => c.trim()).map(c => `<td>${c.trim()}</td>`).join('');
      return `<tr>${cells}</tr>`;
    }).join('');
    return `<table><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
  });
  
  // Restore code blocks
  codeBlocks.forEach((block, i) => {
    const codeHtml = createCodeBlock(block.lang, block.code);
    html = html.replace(`__CODE_BLOCK_${i}__`, codeHtml);
  });
  
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  
  return html;
}

function createCodeBlock(lang, code) {
  const escapedCode = code
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  
  return `<div class="code-block-container">
    <div class="code-header">
      <span class="language-name">${lang.toUpperCase()}</span>
      <button class="copy-code-btn" onclick="copyCodeToClipboard(this)">Copy</button>
    </div>
    <pre><code>${escapedCode}</code></pre>
  </div>`;
}

// Copy code to clipboard
function copyCodeToClipboard(button) {
  const codeBlock = button.closest('.code-block-container');
  const code = codeBlock.querySelector('code');
  
  if (!code) return;
  
  const text = code.textContent;
  
  navigator.clipboard.writeText(text).then(() => {
    const originalText = button.textContent;
    button.textContent = 'Copied!';
    button.classList.add('copied');
    
    setTimeout(() => {
      button.textContent = originalText;
      button.classList.remove('copied');
    }, 2000);
  }).catch(err => {
    console.error('Copy failed:', err);
  });
}

// Add copy buttons to existing code blocks
function addCopyButtons(container) {
  // Already handled in renderMessageContent
}

window.renderMessageContent = renderMessageContent;
window.addCopyButtons = addCopyButtons;
window.copyCodeToClipboard = copyCodeToClipboard;
