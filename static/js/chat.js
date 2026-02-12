// Chat interface logic
(function() {
  'use strict';

  // Configuration
  const MESSAGES_PER_PAGE = 30;
  const SCROLL_THRESHOLD = 100;

  // State
  let messages = [];
  let isLoading = false;
  let isSending = false;
  let isAtBottom = true;

  // DOM Elements
  const chatContainer = document.getElementById('chatContainer');
  const messageInput = document.getElementById('messageInput');
  const sendButton = document.getElementById('sendButton');
  const typingIndicator = document.getElementById('typingIndicator');
  const scrollToBottomBtn = document.getElementById('scrollToBottom');

  // Configure marked.js for full markdown support
  marked.setOptions({
    breaks: true,
    gfm: true,
  });

  /**
   * Initialize the chat interface
   */
  async function init() {
    if (!chatContainer) return;

    await loadMessages();
    setupEventListeners();
    scrollToBottom();
  }

  /**
   * Load messages from API
   */
  async function loadMessages() {
    try {
      const profile = await getProfile();
      const history = profile.chat_history || [];
      
      // Take last MESSAGES_PER_PAGE messages
      messages = history.slice(-MESSAGES_PER_PAGE);
      
      renderMessages();
    } catch (error) {
      console.error('Error loading messages:', error);
      messages = [];
      renderMessages();
    }
  }

  /**
   * Render all messages
   */
  function renderMessages() {
    chatContainer.innerHTML = '';
    
    messages.forEach(msg => {
      appendMessage(msg.role, msg.content, false);
    });

    addCopyButtonsToCodeBlocks();
  }

  /**
   * Append a single message to the chat
   */
  function appendMessage(role, content, scroll = true) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = marked.parse(content);
    
    messageDiv.appendChild(contentDiv);
    chatContainer.appendChild(messageDiv);

    if (scroll) {
      scrollToBottom();
    }

    addCopyButtonsToCodeBlocks();
  }

  /**
   * Add copy buttons to all code blocks
   */
  function addCopyButtonsToCodeBlocks() {
    chatContainer.querySelectorAll('pre').forEach(pre => {
      if (pre.querySelector('.copy-btn')) return;

      const button = document.createElement('button');
      button.className = 'copy-btn';
      button.textContent = 'Copy';
      button.addEventListener('click', async () => {
        const code = pre.querySelector('code');
        if (code) {
          await copyToClipboard(code.textContent);
          button.textContent = 'Copied!';
          setTimeout(() => button.textContent = 'Copy', 2000);
        }
      });
      pre.style.position = 'relative';
      pre.appendChild(button);
    });
  }

  /**
   * Send a message
   */
  async function sendMessage() {
    const content = messageInput.value.trim();
    if (!content || isSending) return;

    isSending = true;
    sendButton.disabled = true;

    // Add user message immediately
    appendMessage('user', content);
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Show typing indicator
    typingIndicator.classList.remove('hidden');

    try {
      const response = await sendMessage(content);
      typingIndicator.classList.add('hidden');
      
      if (response.reply) {
        appendMessage('ai', response.reply);
      } else {
        appendMessage('ai', 'No response from server');
      }
    } catch (error) {
      console.error('Error sending message:', error);
      typingIndicator.classList.add('hidden');
      appendMessage('ai', `Error: ${error.message}`);
    } finally {
      isSending = false;
      sendButton.disabled = false;
    }
  }

  /**
   * Load older messages (pagination)
   */
  async function loadOlderMessages() {
    if (isLoading || messages.length === 0) return;

    isLoading = true;
    const oldestMessage = messages[0];

    try {
      const profile = await getProfile();
      const history = profile.chat_history || [];
      
      // Find the index of the oldest loaded message
      const oldestIndex = history.findIndex(m => m.timestamp === oldestMessage.timestamp);
      
      if (oldestIndex > 0) {
        // Load messages before the oldest loaded message
        const olderMessages = history.slice(Math.max(0, oldestIndex - MESSAGES_PER_PAGE), oldestIndex);
        
        // Save scroll position
        const previousScrollHeight = chatContainer.scrollHeight;
        const previousScrollTop = chatContainer.scrollTop;

        // Prepend older messages
        olderMessages.reverse().forEach(msg => {
          messages.unshift(msg);
          const messageDiv = document.createElement('div');
          messageDiv.className = `message ${msg.role}`;
          messageDiv.style.display = 'none';
          
          const contentDiv = document.createElement('div');
          contentDiv.className = 'message-content';
          contentDiv.innerHTML = marked.parse(msg.content);
          
          messageDiv.appendChild(contentDiv);
          chatContainer.insertBefore(messageDiv, chatContainer.firstChild);
          messageDiv.style.display = '';
        });

        // Restore scroll position
        const newScrollHeight = chatContainer.scrollHeight;
        chatContainer.scrollTop = previousScrollTop + (newScrollHeight - previousScrollHeight);
      }
    } catch (error) {
      console.error('Error loading older messages:', error);
    } finally {
      isLoading = false;
    }
  }

  /**
   * Scroll to bottom of chat
   */
  function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
    updateScrollButton();
  }

  /**
   * Update scroll-to-bottom button visibility
   */
  function updateScrollButton() {
    const distanceFromBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight;
    isAtBottom = distanceFromBottom <= SCROLL_THRESHOLD;
    
    if (scrollToBottomBtn) {
      scrollToBottomBtn.classList.toggle('hidden', isAtBottom);
    }
  }

  /**
   * Setup event listeners
   */
  function setupEventListeners() {
    // Send button
    if (sendButton) {
      sendButton.addEventListener('click', sendMessage);
    }

    // Input - Enter to send, Ctrl+Enter for newline
    if (messageInput) {
      messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.ctrlKey && !e.shiftKey) {
          e.preventDefault();
          sendMessage();
        }
      });

      // Auto-resize textarea
      messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
      });
    }

    // Scroll events
    if (chatContainer) {
      chatContainer.addEventListener('scroll', () => {
        updateScrollButton();

        // Load older messages when near top
        if (chatContainer.scrollTop < SCROLL_THRESHOLD && !isLoading) {
          loadOlderMessages();
        }
      });
    }

    // Scroll to bottom button
    if (scrollToBottomBtn) {
      scrollToBottomBtn.addEventListener('click', scrollToBottom);
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
