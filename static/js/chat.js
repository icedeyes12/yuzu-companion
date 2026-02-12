// chat.js - Chat interface logic

let currentPage = 1;
let isLoading = false;
let hasMoreMessages = true;

// Initialize chat
document.addEventListener('DOMContentLoaded', () => {
  const messageInput = document.getElementById('messageInput');
  const sendButton = document.getElementById('sendButton');
  const chatContainer = document.getElementById('chatContainer');
  const scrollToBottomBtn = document.getElementById('scrollToBottom');

  // Load initial messages
  loadMessages();

  // Input handling - Enter = newline, Ctrl+Enter = send
  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      e.preventDefault();
      sendMessage();
    } else if (e.key === 'Enter' && !e.shiftKey) {
      // Allow Enter for newline by default
      // Do nothing special
    }
  });

  // Auto-resize textarea
  messageInput.addEventListener('input', () => {
    autoResizeTextarea(messageInput);
  });

  // Send button
  sendButton.addEventListener('click', sendMessage);

  // Scroll to bottom button
  scrollToBottomBtn.addEventListener('click', () => {
    scrollToBottom();
  });

  // Show/hide scroll to bottom button
  chatContainer.addEventListener('scroll', () => {
    const isAtBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
    
    if (isAtBottom) {
      scrollToBottomBtn.classList.add('hidden');
    } else {
      scrollToBottomBtn.classList.remove('hidden');
    }
  });

  // Pagination - load older messages when scrolled to top
  chatContainer.addEventListener('scroll', () => {
    if (chatContainer.scrollTop === 0 && hasMoreMessages && !isLoading) {
      loadMoreMessages();
    }
  });
});

// Load messages (last 30)
async function loadMessages() {
  try {
    isLoading = true;
    const response = await fetch(`/api/get_messages?page=${currentPage}&per_page=30`);
    const data = await response.json();

    if (data.messages && data.messages.length > 0) {
      const chatContainer = document.getElementById('chatContainer');
      chatContainer.innerHTML = ''; // Clear existing
      
      data.messages.forEach(msg => {
        appendMessage(msg.role, msg.content, false);
      });

      scrollToBottom();
      hasMoreMessages = data.has_more || false;
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
    const response = await fetch(`/api/get_messages?page=${currentPage}&per_page=30`);
    const data = await response.json();

    if (data.messages && data.messages.length > 0) {
      // Prepend messages
      data.messages.reverse().forEach(msg => {
        const messageEl = createMessageElement(msg.role, msg.content);
        chatContainer.insertBefore(messageEl, chatContainer.firstChild);
      });

      // Preserve scroll position
      chatContainer.scrollTop = chatContainer.scrollHeight - oldScrollHeight;
      
      hasMoreMessages = data.has_more || false;
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
    const response = await fetch('/api/send_message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });

    const data = await response.json();

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
  contentDiv.innerHTML = renderMessageContent(content);

  messageDiv.appendChild(contentDiv);

  // Add copy buttons to code blocks
  addCopyButtons(messageDiv);

  return messageDiv;
}

// Append message to chat
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
  indicator.classList.remove('hidden');
}

// Hide typing indicator
function hideTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  indicator.classList.add('hidden');
}
