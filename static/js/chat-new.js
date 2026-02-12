// Chat Page - Clean Rebuild with Tailwind
// Version: 2.0.0
// Date: 2026-02-12

console.log('Initializing new chat system...');

// ==================== STATE MANAGEMENT ====================
let currentSessionId = null;
let isLoadingMessages = false;
let isSendingMessage = false;
let allMessages = [];
let displayedMessageCount = 0;
const MESSAGES_PER_PAGE = 30;

// ==================== MARKDOWN SETUP ====================
let md;
if (typeof markdownit !== 'undefined') {
    md = markdownit({
        html: true,
        linkify: true,
        typographer: true,
        breaks: true
    });
    console.log('markdown-it initialized');
} else {
    console.warn('markdown-it not loaded, using fallback');
}

// ==================== MARKDOWN RENDERING ====================
function renderMessageContent(text) {
    if (!text) return '';
    
    // Pre-process: Fix broken image markdown (line breaks between ![alt] and (url))
    text = String(text).replace(/!\[([^\]]*)\]\s*\n\s*\(([^)]+)\)/g, '![$1]($2)');
    
    // Pre-process: Fix image paths to ensure they start with /
    text = String(text).replace(/!\[([^\]]*)\]\((static\/[^)]+)\)/g, '![$1](/$2)');
    
    // Use markdown-it if available
    if (md) {
        let html = md.render(text);
        
        // Post-process code blocks to add copy buttons
        html = html.replace(/<pre><code class="language-(\w+)">([\s\S]*?)<\/code><\/pre>/g, (match, lang, code) => {
            return `<div class="code-block">
                <button class="copy-btn" onclick="copyCode(this)">Copy</button>
                <pre><code class="language-${lang}">${code}</code></pre>
            </div>`;
        });
        
        // Handle code blocks without language
        html = html.replace(/<pre><code>([\s\S]*?)<\/code><\/pre>/g, (match, code) => {
            return `<div class="code-block">
                <button class="copy-btn" onclick="copyCode(this)">Copy</button>
                <pre><code>${code}</code></pre>
            </div>`;
        });
        
        // Post-process: Fix any image src that doesn't start with /
        html = html.replace(/<img([^>]+)src="(static\/[^"]+)"/g, '<img$1src="/$2"');
        
        return html;
    }
    
    // Fallback 1: Use existing MarkdownParser if available
    if (typeof MarkdownParser !== 'undefined' && MarkdownParser.parse) {
        console.log('Using MarkdownParser fallback');
        return MarkdownParser.parse(text);
    }
    
    // Fallback 2: Basic text with line breaks
    console.warn('No markdown parser available, using basic formatting');
    
    // Fix broken image markdown first
    text = text.replace(/!\[([^\]]*)\]\s*\n\s*\(([^)]+)\)/g, '![$1]($2)');
    
    // Fix image paths
    text = text.replace(/!\[([^\]]*)\]\((static\/[^)]+)\)/g, '![$1](/$2)');
    
    // Extract and temporarily store images
    const images = [];
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, src) => {
        const placeholder = `__IMAGE_${images.length}__`;
        // Ensure src starts with /
        const fixedSrc = src.startsWith('/') ? src : (src.startsWith('static/') ? `/${src}` : src);
        images.push(`<img src="${fixedSrc}" alt="${alt}" class="markdown-image">`);
        return placeholder;
    });
    
    // Escape HTML and convert newlines
    text = text.replace(/&/g, '&amp;')
               .replace(/</g, '&lt;')
               .replace(/>/g, '&gt;')
               .replace(/\n/g, '<br>');
    
    // Restore images
    images.forEach((img, i) => {
        text = text.replace(`__IMAGE_${i}__`, img);
    });
    
    return text;
}

// ==================== CODE COPY FUNCTIONALITY ====================
function copyCode(button) {
    const codeBlock = button.closest('.code-block');
    const code = codeBlock.querySelector('code');
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

window.copyCode = copyCode;

// ==================== MESSAGE CREATION ====================
function createMessageElement(role, content, timestamp = null) {
    const messageDiv = document.createElement('div');
    
    // User messages: right-aligned with bubble
    // AI messages: full-width, no bubble background
    if (role === 'user') {
        messageDiv.className = 'flex justify-end mb-4';
    } else {
        messageDiv.className = 'flex justify-start mb-4 w-full';
    }
    
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${role} rounded-lg p-4 shadow-sm`;
    
    // Add copy button for AI messages
    if (role === 'ai') {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-message-btn';
        copyBtn.title = 'Copy message';
        copyBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
        </svg>`;
        copyBtn.onclick = function() {
            copyEntireMessage(content, this);
        };
        bubble.appendChild(copyBtn);
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'markdown-content';
    contentDiv.innerHTML = renderMessageContent(content);
    
    bubble.appendChild(contentDiv);
    
    // Add timestamp if provided
    if (timestamp) {
        const timeDiv = document.createElement('div');
        timeDiv.className = 'text-xs opacity-60 mt-2';
        timeDiv.textContent = formatTimestamp(timestamp);
        bubble.appendChild(timeDiv);
    }
    
    messageDiv.appendChild(bubble);
    
    return messageDiv;
}

// ==================== COPY MESSAGE FUNCTION ====================
function copyEntireMessage(text, button) {
    // Strip markdown and HTML for plain text copy
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = text.replace(/```[\s\S]*?```/g, '[code block]');
    const plainText = tempDiv.textContent || tempDiv.innerText || text;
    
    navigator.clipboard.writeText(plainText).then(() => {
        const originalHTML = button.innerHTML;
        button.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
        </svg>`;
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

window.copyEntireMessage = copyEntireMessage;

// ==================== TIMESTAMP FORMATTING ====================
function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    try {
        const date = new Date(timestamp);
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    } catch (e) {
        return '';
    }
}

// ==================== SYNTAX HIGHLIGHTING ====================
function highlightCode() {
    if (typeof hljs !== 'undefined') {
        document.querySelectorAll('pre code').forEach((block) => {
            if (!block.classList.contains('hljs')) {
                hljs.highlightElement(block);
            }
        });
    }
}

// ==================== SCROLL MANAGEMENT ====================
function scrollToBottom() {
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

function isNearBottom() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return true;
    
    const threshold = 150;
    const position = chatContainer.scrollTop + chatContainer.clientHeight;
    const height = chatContainer.scrollHeight;
    
    return height - position < threshold;
}

function updateScrollButton() {
    const scrollBtn = document.getElementById('scrollToBottom');
    if (!scrollBtn) return;
    
    if (isNearBottom()) {
        scrollBtn.classList.add('hidden');
    } else {
        scrollBtn.classList.remove('hidden');
    }
}

window.scrollToBottom = scrollToBottom;

// ==================== CHAT HISTORY LOADING ====================
async function loadChatHistory() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) {
        console.error('Chat container not found');
        return;
    }
    
    if (isLoadingMessages) return;
    isLoadingMessages = true;
    
    try {
        chatContainer.innerHTML = '<div class="flex justify-center items-center h-full"><div class="opacity-60">Loading messages...</div></div>';
        
        const response = await fetch('/api/get_profile');
        const data = await response.json();
        
        allMessages = data.chat_history || [];
        console.log(`Loaded ${allMessages.length} messages`);
        
        // Update session name
        const sessionName = data.active_session?.name || 'Default Session';
        updateSessionName(sessionName);
        
        // Display last 30 messages
        displayedMessageCount = 0;
        chatContainer.innerHTML = '';
        
        if (allMessages.length > 0) {
            const startIndex = Math.max(0, allMessages.length - MESSAGES_PER_PAGE);
            displayMessages(startIndex, allMessages.length);
        } else {
            chatContainer.innerHTML = '<div class="flex justify-center items-center h-full opacity-60">No messages yet. Start chatting!</div>';
        }
        
        setTimeout(() => {
            scrollToBottom();
            highlightCode();
        }, 100);
        
    } catch (error) {
        console.error('Error loading chat history:', error);
        chatContainer.innerHTML = '<div class="flex justify-center items-center h-full text-red-500">Error loading messages</div>';
    } finally {
        isLoadingMessages = false;
    }
}

function displayMessages(startIndex, endIndex) {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    
    const fragment = document.createDocumentFragment();
    
    for (let i = startIndex; i < endIndex; i++) {
        const msg = allMessages[i];
        if (msg.role === 'user' || msg.role === 'assistant') {
            const role = msg.role === 'user' ? 'user' : 'ai';
            const messageElement = createMessageElement(role, msg.content, msg.timestamp);
            fragment.appendChild(messageElement);
            displayedMessageCount++;
        }
    }
    
    // If we're loading older messages, prepend them
    if (startIndex > 0 && chatContainer.firstChild) {
        chatContainer.insertBefore(fragment, chatContainer.firstChild);
    } else {
        chatContainer.appendChild(fragment);
    }
}

function updateSessionName(sessionName) {
    const sessionNameEl = document.getElementById('sessionName');
    if (sessionNameEl) {
        sessionNameEl.textContent = sessionName || 'Default Session';
    }
}

// ==================== PAGINATION (LOAD OLDER MESSAGES) ====================
async function loadOlderMessages() {
    if (isLoadingMessages) return;
    if (displayedMessageCount >= allMessages.length) return;
    
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    
    // Save current scroll position
    const oldScrollHeight = chatContainer.scrollHeight;
    
    isLoadingMessages = true;
    
    try {
        const remainingMessages = allMessages.length - displayedMessageCount;
        const messagesToLoad = Math.min(MESSAGES_PER_PAGE, remainingMessages);
        const startIndex = allMessages.length - displayedMessageCount - messagesToLoad;
        const endIndex = allMessages.length - displayedMessageCount;
        
        displayMessages(startIndex, endIndex);
        
        // Restore scroll position
        setTimeout(() => {
            const newScrollHeight = chatContainer.scrollHeight;
            chatContainer.scrollTop = newScrollHeight - oldScrollHeight;
            highlightCode();
        }, 50);
        
    } catch (error) {
        console.error('Error loading older messages:', error);
    } finally {
        isLoadingMessages = false;
    }
}

// ==================== SEND MESSAGE ====================
async function sendMessage() {
    if (isSendingMessage) return;
    
    const input = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const message = input.value.trim();
    
    if (!message) return;
    
    isSendingMessage = true;
    sendButton.disabled = true;
    
    try {
        // Add user message to UI immediately
        const chatContainer = document.getElementById('chatContainer');
        const userMessage = createMessageElement('user', message, new Date().toISOString());
        chatContainer.appendChild(userMessage);
        
        // Clear input
        input.value = '';
        input.style.height = 'auto';
        
        // Scroll to bottom
        setTimeout(scrollToBottom, 50);
        
        // Show typing indicator
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.classList.remove('hidden');
        }
        
        // Send to backend
        const response = await fetch('/api/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                mode: 'chat'
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to send message');
        }
        
        const data = await response.json();
        
        // Hide typing indicator
        if (typingIndicator) {
            typingIndicator.classList.add('hidden');
        }
        
        // Add AI response
        if (data.response) {
            const aiMessage = createMessageElement('ai', data.response, new Date().toISOString());
            chatContainer.appendChild(aiMessage);
            
            setTimeout(() => {
                scrollToBottom();
                highlightCode();
            }, 50);
        }
        
        // Update affection if provided
        if (data.affection !== undefined) {
            updateAffection(data.affection);
        }
        
    } catch (error) {
        console.error('Error sending message:', error);
        
        // Hide typing indicator
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.classList.add('hidden');
        }
        
        // Show error message
        const chatContainer = document.getElementById('chatContainer');
        const errorMessage = createMessageElement('ai', 'Sorry, there was an error sending your message. Please try again.', new Date().toISOString());
        chatContainer.appendChild(errorMessage);
        
    } finally {
        isSendingMessage = false;
        sendButton.disabled = false;
        input.focus();
    }
}

function updateAffection(value) {
    const affectionFill = document.querySelector('.affection-fill');
    const affectionText = affectionFill?.parentElement?.nextElementSibling;
    
    if (affectionFill) {
        affectionFill.style.width = `${value}%`;
    }
    
    if (affectionText) {
        affectionText.textContent = `${value}%`;
    }
}

// ==================== INPUT HANDLING ====================
function setupInputHandlers() {
    const input = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    
    if (!input || !sendButton) return;
    
    // Auto-resize textarea
    input.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        
        // Update scroll button position
        updateScrollButtonPosition();
    });
    
    // Keyboard shortcuts
    input.addEventListener('keydown', function(e) {
        // Ctrl+Enter or Cmd+Enter to send
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            sendMessage();
        }
        // Just Enter creates newline (default behavior)
    });
    
    // Send button click
    sendButton.addEventListener('click', sendMessage);
    
    // Initial scroll button position
    updateScrollButtonPosition();
}

// Update scroll-to-bottom button position based on input area height
function updateScrollButtonPosition() {
    const inputArea = document.querySelector('.input-area');
    if (inputArea) {
        const inputHeight = inputArea.offsetHeight;
        document.documentElement.style.setProperty('--input-height', `${inputHeight - 80}px`);
    }
}

window.addEventListener('resize', updateScrollButtonPosition);

// ==================== SCROLL DETECTION ====================
function setupScrollDetection() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    
    chatContainer.addEventListener('scroll', () => {
        // Update scroll-to-bottom button visibility
        updateScrollButton();
        
        // Load older messages when scrolled to top
        if (chatContainer.scrollTop < 100) {
            loadOlderMessages();
        }
    });
}

// ==================== SESSION MANAGEMENT ====================
async function createNewSession() {
    try {
        const response = await fetch('/api/sessions/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: 'New Chat'
            })
        });
        
        if (response.ok) {
            // Reload chat history
            await loadChatHistory();
        }
    } catch (error) {
        console.error('Error creating new session:', error);
    }
}

window.createNewSession = createNewSession;

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', async () => {
    console.log('DOM loaded, initializing chat...');
    
    // Setup handlers
    setupInputHandlers();
    setupScrollDetection();
    
    // Load chat history
    await loadChatHistory();
    
    console.log('Chat system ready!');
});

// ==================== EXPORTS ====================
window.loadChatHistory = loadChatHistory;
window.sendMessage = sendMessage;
window.renderMessageContent = renderMessageContent;
