// DOM elements
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');

/**
 * Create a message element
 * @param {string} role - "user" or "ai"
 * @param {string} content - The message content
 * @returns {HTMLElement} - The message element
 */
function createMessageElement(role, content) {
    const message = document.createElement('div');
    message.className = `message ${role}`;

    const contentEl = document.createElement('div');
    contentEl.className = 'message-content';
    contentEl.innerHTML = renderMessageContent(content);

    message.appendChild(contentEl);
    return message;
}

/**
 * Append a message to the chat container
 * @param {string} role - "user" or "ai"
 * @param {string} content - The message content
 */
function appendMessage(role, content) {
    const messageEl = createMessageElement(role, content);
    chatContainer.appendChild(messageEl);
    scrollToBottom();
}

/**
 * Scroll chat container to bottom
 */
function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

/**
 * Load chat history from API
 */
async function loadChatHistory() {
    try {
        const response = await fetch('/api/get_profile');
        const data = await response.json();
        
        if (data.chat_history && Array.isArray(data.chat_history)) {
            // Clear existing messages
            chatContainer.innerHTML = '';
            
            // Render each message
            data.chat_history.forEach(msg => {
                const role = msg.role === 'user' ? 'user' : 'ai';
                appendMessage(role, msg.content);
            });
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

/**
 * Send a message to the API
 * @param {string} message - The message to send
 */
async function sendMessage(message) {
    if (!message.trim()) return;

    // Disable input while sending
    sendButton.disabled = true;
    messageInput.disabled = true;

    // Show user message immediately
    appendMessage('user', message);
    messageInput.value = '';
    messageInput.style.height = 'auto';  // Reset height

    try {
        const response = await fetch('/api/send_message', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        const data = await response.json();

        if (data.response) {
            appendMessage('ai', data.response);
        } else if (data.error) {
            console.error('API error:', data.error);
            appendMessage('ai', 'Sorry, there was an error processing your message.');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        appendMessage('ai', 'Sorry, there was an error connecting to the server.');
    } finally {
        // Re-enable input
        sendButton.disabled = false;
        messageInput.disabled = false;
        messageInput.focus();
    }
}

/**
 * Handle send button click
 */
sendButton.addEventListener('click', () => {
    const message = messageInput.value;
    sendMessage(message);
});

/**
 * Handle Enter key in input
 */
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const message = messageInput.value;
        sendMessage(message);
    }
});

/**
 * Auto-resize textarea as user types
 */
messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
});

// Load chat history on page load
document.addEventListener('DOMContentLoaded', () => {
    loadChatHistory();
    messageInput.focus();
});
