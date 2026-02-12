// renderer.js - Single markdown pipeline using markdown-it

const md = window.markdownit({
  html: true,
  linkify: true,
  breaks: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value;
      } catch (__) {}
    }
    return '';
  }
});

function renderMessageContent(text) {
  if (!text) return '';
  return md.render(String(text));
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

// Add copy buttons to code blocks
function addCopyButtons(container) {
  const codeBlocks = container.querySelectorAll('pre code');
  
  codeBlocks.forEach(code => {
    const pre = code.parentElement;
    
    // Skip if already has copy button
    if (pre.parentElement.classList.contains('code-block-container')) {
      return;
    }
    
    // Get language
    const language = code.className.match(/language-(\w+)/)?.[1] || 'text';
    
    // Create container
    const container = document.createElement('div');
    container.className = 'code-block-container';
    
    // Create header
    const header = document.createElement('div');
    header.className = 'code-header';
    
    const langName = document.createElement('span');
    langName.className = 'language-name';
    langName.textContent = language.toUpperCase();
    
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-code-btn';
    copyBtn.textContent = 'Copy';
    copyBtn.onclick = () => copyCodeToClipboard(copyBtn);
    
    header.appendChild(langName);
    header.appendChild(copyBtn);
    
    // Wrap pre element
    pre.parentNode.insertBefore(container, pre);
    container.appendChild(header);
    container.appendChild(pre);
  });
}

window.renderMessageContent = renderMessageContent;
window.addCopyButtons = addCopyButtons;
window.copyCodeToClipboard = copyCodeToClipboard;
