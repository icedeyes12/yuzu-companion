// chat.js - Chat Interface Logic

let currentPage = 1;
let isLoading = false;
let hasMoreMessages = true;

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

    // Load initial messages
    loadMessages();

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

    // Pagination - load older messages when scrolled to top
    chatContainer.addEventListener('scroll', () => {
        if (chatContainer.scrollTop === 0 && hasMoreMessages && !isLoading) {
            loadMoreMessages();
        }
    });
});

// Load messages
async function loadMessages() {
    try {
        isLoading = true;
        const data = await apiCall('/api/get_profile');

        if (data && data.chat_history) {
            const chatContainer = document.getElementById('chatContainer');
            chatContainer.innerHTML = '';
            
            data.chat_history.slice(-30).forEach(msg => {
                appendMessage(msg.role, msg.content, false);
            });

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
    try {
        isLoading = true;
        const chatContainer = document.getElementById('chatContainer');
        const oldScrollHeight = chatContainer.scrollHeight;

        currentPage++;
        // Pagination would need a proper endpoint
        // For now, just preventing multiple loads

        hasMoreMessages = false;
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
