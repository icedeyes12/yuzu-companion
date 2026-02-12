// chat.js - Chat interface logic

/**
 * Chat manager class
 */
class ChatManager {
    constructor() {
        this.chatContainer = document.getElementById('chatContainer');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.scrollToBottomBtn = document.getElementById('scrollToBottom');
        this.sessionName = document.getElementById('sessionName');
        
        this.currentSessionId = null;
        this.isLoading = false;
        this.messagesLoaded = 0;
        this.allMessagesLoaded = false;
        this.isAtBottom = true;
        
        this.init();
    }

    /**
     * Initialize chat manager
     */
    init() {
        console.log('Initializing chat...');
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load or create session
        this.loadSession();
        
        // Setup auto-resize for textarea
        this.setupTextareaAutoResize();
    }

    /**
     * Setup all event listeners
     */
    setupEventListeners() {
        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enter key handling
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
                // Just Enter = newline (default behavior)
                return;
            } else if (e.key === 'Enter' && e.ctrlKey) {
                // Ctrl+Enter = send
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Scroll detection for pagination and scroll-to-bottom button
        this.chatContainer.addEventListener('scroll', () => {
            this.handleScroll();
        });
        
        // Scroll to bottom button
        this.scrollToBottomBtn.addEventListener('click', () => {
            this.scrollToBottom(true);
        });
    }

    /**
     * Setup textarea auto-resize
     */
    setupTextareaAutoResize() {
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 150) + 'px';
        });
    }

    /**
     * Handle scroll events
     */
    handleScroll() {
        const container = this.chatContainer;
        const scrollTop = container.scrollTop;
        const scrollHeight = container.scrollHeight;
        const clientHeight = container.clientHeight;
        
        // Check if at bottom
        this.isAtBottom = (scrollHeight - scrollTop - clientHeight) < 50;
        
        // Show/hide scroll-to-bottom button
        if (this.isAtBottom) {
            this.scrollToBottomBtn.classList.add('hidden');
        } else {
            this.scrollToBottomBtn.classList.remove('hidden');
        }
        
        // Check if at top for pagination
        if (scrollTop < 100 && !this.isLoading && !this.allMessagesLoaded) {
            this.loadOlderMessages();
        }
    }

    /**
     * Scroll to bottom of chat
     */
    scrollToBottom(smooth = false) {
        this.chatContainer.scrollTo({
            top: this.chatContainer.scrollHeight,
            behavior: smooth ? 'smooth' : 'auto'
        });
    }

    /**
     * Load or create chat session
     */
    async loadSession() {
        try {
            // Get active session from backend
            const profileResponse = await API.get('/api/get_profile');
            
            if (profileResponse && profileResponse.active_session) {
                this.currentSessionId = profileResponse.active_session.id;
                this.sessionName.textContent = profileResponse.active_session.name || 'Chat Session';
                
                // Load messages
                await this.loadMessages();
            } else {
                // Create new session
                await this.createNewSession();
            }
        } catch (error) {
            console.error('Error loading session:', error);
            // Try to create new session on error
            await this.createNewSession();
        }
    }

    /**
     * Create new chat session
     */
    async createNewSession() {
        try {
            const response = await API.post('/api/sessions/create', {
                name: 'New Chat'
            });
            
            if (response.session_id || response.status === 'success') {
                this.currentSessionId = response.session_id;
                this.sessionName.textContent = 'New Chat';
                this.chatContainer.innerHTML = '';
                this.messagesLoaded = 0;
                this.allMessagesLoaded = false;
            }
        } catch (error) {
            console.error('Error creating session:', error);
            Utils.showNotification('Error creating new session', 'error');
        }
    }

    /**
     * Load messages (last 30 initially)
     */
    async loadMessages(limit = 30, offset = 0) {
        if (this.isLoading) return;
        
        this.isLoading = true;
        
        try {
            // Get profile which includes chat history
            const response = await API.get('/api/get_profile');
            
            if (response && response.chat_history && response.chat_history.length > 0) {
                // Get last N messages
                const messages = response.chat_history.slice(-limit);
                
                // Add messages to UI
                messages.forEach(msg => {
                    // Skip system messages if they exist
                    if (msg.role !== 'system') {
                        this.addMessageToUI(msg.role, msg.content, false);
                    }
                });
                
                this.messagesLoaded = messages.length;
                this.allMessagesLoaded = true; // For now, load all at once
                
                // Scroll to bottom on initial load
                if (offset === 0) {
                    setTimeout(() => this.scrollToBottom(false), 100);
                }
            } else {
                this.allMessagesLoaded = true;
            }
        } catch (error) {
            console.error('Error loading messages:', error);
            Utils.showNotification('Error loading messages', 'error');
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * Load older messages (pagination)
     */
    async loadOlderMessages() {
        // For now, all messages are loaded at once
        // This can be enhanced later if needed
        this.allMessagesLoaded = true;
    }

    /**
     * Send message
     */
    async sendMessage() {
        const message = this.messageInput.value.trim();
        
        if (!message || this.isLoading) return;
        
        // Clear input
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        
        // Add user message to UI
        this.addMessageToUI('user', message, true);
        
        // Show typing indicator
        this.typingIndicator.classList.remove('hidden');
        this.scrollToBottom(true);
        
        try {
            // Send to API (backend uses active session automatically)
            const response = await API.post('/api/send_message', {
                message: message
            });
            
            // Hide typing indicator
            this.typingIndicator.classList.add('hidden');
            
            if (response.reply) {
                // Add AI response to UI
                this.addMessageToUI('ai', response.reply, true);
            } else {
                throw new Error('No reply from AI');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.typingIndicator.classList.add('hidden');
            Utils.showNotification('Error sending message', 'error');
            
            // Add error message
            this.addMessageToUI('ai', 'Sorry, I encountered an error. Please try again.', true);
        }
    }

    /**
     * Add message to UI
     */
    addMessageToUI(role, content, shouldScroll = true) {
        const messageEl = this.createMessageElement(role, content);
        this.chatContainer.appendChild(messageEl);
        
        // Highlight code blocks
        Renderer.highlightCodeBlocks(messageEl);
        
        // Scroll to bottom if needed
        if (shouldScroll && this.isAtBottom) {
            setTimeout(() => this.scrollToBottom(true), 100);
        }
    }

    /**
     * Create message DOM element
     */
    createMessageElement(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // Render markdown content
        contentDiv.innerHTML = Renderer.render(content);
        
        messageDiv.appendChild(contentDiv);
        
        return messageDiv;
    }
}

/**
 * Initialize chat when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
    // Check if we're on the chat page
    if (document.getElementById('chatContainer')) {
        window.chatManager = new ChatManager();
        console.log('Chat initialized');
    }
});
