// chat.js - Chat Interface Logic

let currentPage = 1;
let isLoading = false;
let hasMoreMessages = true;
let allMessages = []; // Store all loaded messages
let displayedMessageCount = 0;
let currentSessionName = 'Active Session';

// Initialize chat
document.addEventListener('DOMContentLoaded', () => {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const chatContainer = document.getElementById('chatContainer');
    const scrollToBottomBtn = document.getElementById('scrollToBottom');

    if (!messageInput || !sendButton || !chatContainer) {
        console.error('Chat elements not found');
        return;
    }

    // Load initial messages and session info
    loadMessages();
    loadCurrentSession();

    // Input handling - Enter = newline, Ctrl+Enter = send
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault();
            sendMessage();
        }
        // Enter alone creates newline (default behavior)
    });

    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        autoResizeTextarea(messageInput);
    });

    // Send button
    sendButton.addEventListener('click', sendMessage);

    // Scroll to bottom button
    if (scrollToBottomBtn) {
        scrollToBottomBtn.addEventListener('click', () => {
            scrollToBottom();
        });

        // Show/hide scroll button
        chatContainer.addEventListener('scroll', () => {
            const isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
            
            if (isAtBottom) {
                scrollToBottomBtn.classList.add('hidden');
            } else {
                scrollToBottomBtn.classList.remove('hidden');
            }
        });
    }

    // Pagination - load older messages when scrolled near top
    chatContainer.addEventListener('scroll', () => {
        if (chatContainer.scrollTop < 100 && hasMoreMessages && !isLoading) {
            loadMoreMessages();
        }
    });
});

// Load current session info
async function loadCurrentSession() {
    try {
        const data = await apiCall('/api/sessions/list');
        
        if (data && data.sessions) {
            const activeSession = data.sessions.find(s => s.is_active);
            if (activeSession) {
                currentSessionName = activeSession.name || `Session ${activeSession.id}`;
                const sessionNameEl = document.getElementById('sessionName');
                if (sessionNameEl) {
                    sessionNameEl.textContent = currentSessionName;
                }
            }
        }
    } catch (error) {
        console.error('Failed to load session info:', error);
    }
}

// Load initial messages (last 30)
async function loadMessages() {
    try {
        isLoading = true;
        const data = await apiCall('/api/get_profile');

        if (data && data.chat_history && data.chat_history.length > 0) {
            allMessages = data.chat_history;
            const chatContainer = document.getElementById('chatContainer');
            chatContainer.innerHTML = '';
            
            // Display last 30 messages
            const messagesToShow = allMessages.slice(-30);
            displayedMessageCount = messagesToShow.length;
            
            messagesToShow.forEach(msg => {
                appendMessage(msg.role, msg.content, false);
            });

            // Check if there are more messages
            hasMoreMessages = allMessages.length > displayedMessageCount;
            
            scrollToBottom();
        }
    } catch (error) {
        console.error('Failed to load messages:', error);
        showNotification('Failed to load messages', 'error');
    } finally {
        isLoading = false;
    }
}

// Load more messages (pagination)
async function loadMoreMessages() {
    if (!hasMoreMessages || isLoading) return;
    
    try {
        isLoading = true;
        const chatContainer = document.getElementById('chatContainer');
        const oldScrollHeight = chatContainer.scrollHeight;
        const oldScrollTop = chatContainer.scrollTop;

        // Calculate how many more messages to load
        const startIndex = Math.max(0, allMessages.length - displayedMessageCount - 30);
        const endIndex = allMessages.length - displayedMessageCount;
        const olderMessages = allMessages.slice(startIndex, endIndex);
        
        if (olderMessages.length > 0) {
            // Prepend older messages
            olderMessages.reverse().forEach(msg => {
                const messageEl = createMessageElement(msg.role, msg.content);
                chatContainer.insertBefore(messageEl, chatContainer.firstChild);
            });
            
            displayedMessageCount += olderMessages.length;
            
            // Preserve scroll position
            const newScrollHeight = chatContainer.scrollHeight;
            chatContainer.scrollTop = oldScrollTop + (newScrollHeight - oldScrollHeight);
            
            // Check if there are more messages
            hasMoreMessages = displayedMessageCount < allMessages.length;
        } else {
            hasMoreMessages = false;
        }
    } catch (error) {
        console.error('Failed to load more messages:', error);
    } finally {
        isLoading = false;
    }
}

// Send message
async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();

    if (!message) return;

    // Disable input
    messageInput.disabled = true;
    document.getElementById('sendButton').disabled = true;

    // Append user message
    appendMessage('user', message);
    messageInput.value = '';
    autoResizeTextarea(messageInput);

    // Show typing indicator
    showTypingIndicator();

    try {
        const data = await apiCall('/api/send_message', {
            method: 'POST',
            body: JSON.stringify({ message })
        });

        if (data.reply) {
            appendMessage('ai', data.reply);
        } else {
            throw new Error('No response from AI');
        }
    } catch (error) {
        console.error('Failed to send message:', error);
        showNotification('Failed to send message', 'error');
        appendMessage('ai', 'Sorry, I encountered an error. Please try again.');
    } finally {
        hideTypingIndicator();
        messageInput.disabled = false;
        document.getElementById('sendButton').disabled = false;
        messageInput.focus();
    }
}

// Create message element
function createMessageElement(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = renderMarkdown(content);

    messageDiv.appendChild(contentDiv);

    return messageDiv;
}

// Append message
function appendMessage(role, content, shouldScroll = true) {
    const chatContainer = document.getElementById('chatContainer');
    const messageEl = createMessageElement(role, content);
    
    chatContainer.appendChild(messageEl);

    if (shouldScroll) {
        scrollToBottom();
    }
}

// Scroll to bottom
function scrollToBottom() {
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.classList.remove('hidden');
    }
}

// Hide typing indicator
function hideTypingIndicator() {
    const indicator = document.getElementById('typingIndicator');
    if (indicator) {
        indicator.classList.add('hidden');
    }
}
