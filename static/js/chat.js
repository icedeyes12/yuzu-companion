// [FILE: chat.js] - REBUILT VERSION
// [VERSION: 2.0.0]
// [DATE: 2025-08-12]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Streamlined chat interface using renderer.js with marked.js]
// [AUTHOR: Project Lead: Bani Baskara]

console.log("Starting REBUILT chat with marked.js renderer...");

// ==================== GLOBAL STATE ====================
let isProcessingMessage = false;
const IMMEDIATE_LOAD_COUNT = 30; // Load last 30 messages initially

// ==================== MULTIMODAL MANAGER ====================
class MultimodalManager {
    constructor() {
        this.currentMode = 'chat';
        this.selectedImages = [];
        this.isDropdownOpen = false;
        this.isSending = false;
    }

    init() {
        console.log("Initializing Multimodal...");
        this.createToggle();
        this.setupEventListeners();
        this.patchSendButton();
        this.updateNotificationCount();
    }

    createToggle() {
        const inputArea = document.querySelector('.input-area');
        if (!inputArea) return;
        if (inputArea.querySelector('.multimodal-toggle-container')) return;

        const toggleHTML = `
            <div class="multimodal-toggle-container">
                <button class="multimodal-toggle-btn" type="button" title="Multimodal Mode">
                    <span class="toggle-icon">${this.getSVGIcon('chat')}</span>
                    <div class="mode-indicator">C</div>
                    <div class="image-count-badge hidden">0</div>
                </button>
            </div>
        `;
        
        inputArea.insertAdjacentHTML('afterbegin', toggleHTML);
        this.toggleBtn = inputArea.querySelector('.multimodal-toggle-btn');
        this.modeIndicator = inputArea.querySelector('.mode-indicator');
        this.imageCountBadge = inputArea.querySelector('.image-count-badge');
    }

    getSVGIcon(mode) {
        const icons = {
            chat: `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 9h12v2H6V9zm8 5H6v-2h8v2zm4-6H6V6h12v2z"/>
                   </svg>`,
            image: `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM5 19l3.5-4.5 2.5 3.01L14.5 11l4.5 6H5z"/>
                   </svg>`,
            generate: `<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM5 19l3.5-4.5 2.5 3.01L14.5 11l4.5 6H5z"/>
                      <path d="M14.5 11l1.5-2 1.5 2 2-1-2-1.5 2-1.5-2-1-1.5 2-1.5-2-1 1.5L13 8l-1.5 2z" opacity="0.7"/>
                     </svg>`
        };
        return icons[mode] || icons.chat;
    }

    setupEventListeners() {
        if (!this.toggleBtn) return;
        
        this.toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.toggleDropdown();
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.multimodal-toggle-container')) {
                this.closeDropdown();
            }
        });
    }

    toggleDropdown() {
        this.isDropdownOpen = !this.isDropdownOpen;
        if (this.isDropdownOpen) {
            this.showModeSelector();
        } else {
            this.closeDropdown();
        }
    }

    showModeSelector() {
        let dropdown = document.querySelector('.multimodal-dropdown');
        if (dropdown) {
            dropdown.remove();
        }

        dropdown = document.createElement('div');
        dropdown.className = 'multimodal-dropdown';
        dropdown.innerHTML = `
            <button class="mode-option" data-mode="chat">
                ${this.getSVGIcon('chat')}
                <span>Chat</span>
            </button>
            <button class="mode-option" data-mode="image">
                ${this.getSVGIcon('image')}
                <span>Image Analysis</span>
            </button>
            <button class="mode-option" data-mode="generate">
                ${this.getSVGIcon('generate')}
                <span>Generate Image</span>
            </button>
        `;

        this.toggleBtn.parentElement.appendChild(dropdown);

        dropdown.querySelectorAll('.mode-option').forEach(option => {
            option.addEventListener('click', (e) => {
                const mode = option.getAttribute('data-mode');
                this.switchMode(mode);
                this.closeDropdown();
            });
        });
    }

    closeDropdown() {
        this.isDropdownOpen = false;
        const dropdown = document.querySelector('.multimodal-dropdown');
        if (dropdown) {
            dropdown.remove();
        }
    }

    switchMode(mode) {
        this.currentMode = mode;
        this.updateToggleIcon(mode);
        console.log(`Switched to ${mode} mode`);
    }

    updateToggleIcon(mode) {
        if (!this.toggleBtn) return;
        
        const icon = this.toggleBtn.querySelector('.toggle-icon');
        const indicator = this.toggleBtn.querySelector('.mode-indicator');
        
        if (icon) icon.innerHTML = this.getSVGIcon(mode);
        if (indicator) {
            const indicators = { chat: 'C', image: 'I', generate: 'G' };
            indicator.textContent = indicators[mode] || 'C';
        }
    }

    patchSendButton() {
        const sendBtn = document.getElementById('sendButton');
        if (!sendBtn) return;

        sendBtn.onclick = async (e) => {
            e.preventDefault();
            if (this.isSending || isProcessingMessage) return;

            const input = document.getElementById('messageInput');
            const text = input?.value.trim();

            if (this.currentMode === 'image' && this.selectedImages.length > 0) {
                await this.handleImageMessage(text);
            } else if (this.currentMode === 'generate' && text) {
                await this.handleImageGeneration(text);
            } else if (text) {
                await this.handleChatMessage(text);
            }
        };
    }

    async handleChatMessage(text) {
        isProcessingMessage = true;
        this.isSending = true;

        try {
            addMessage("user", text);
            clearInput();

            const response = await fetch("/api/send_message", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            });

            const data = await response.json();
            
            if (data.reply) {
                addMessage("ai", data.reply);
            } else {
                throw new Error(data.error || 'No response');
            }
        } catch (error) {
            console.error('Chat message failed:', error);
            addMessage("ai", `Error: ${error.message}`);
        } finally {
            this.isSending = false;
            isProcessingMessage = false;
        }
    }

    async handleImageGeneration(prompt) {
        isProcessingMessage = true;
        this.isSending = true;

        try {
            addMessage("user", `Generate: ${prompt}`);
            
            const response = await fetch("/api/generate_image", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt: prompt })
            });

            const data = await response.json();
            
            if (data.image_path) {
                this.displayGeneratedImage(data.image_path, prompt);
                clearInput();
            } else {
                throw new Error(data.error || 'Image generation failed');
            }
        } catch (error) {
            console.error('Image generation failed:', error);
            addMessage("ai", `Error: ${error.message}`);
        } finally {
            this.isSending = false;
            isProcessingMessage = false;
        }
    }

    async handleImageMessage(text) {
        if (!text && this.selectedImages.length === 0) {
            alert('Please enter a message or upload images');
            isProcessingMessage = false;
            return;
        }

        isProcessingMessage = true;
        this.isSending = true;

        try {
            addMessage("user", text || "Analyze these images");
            
            const formData = new FormData();
            if (text) formData.append('message', text);
            
            this.selectedImages.forEach((image) => {
                formData.append('images', image);
            });

            const response = await fetch("/api/send_message_with_images", {
                method: "POST",
                body: formData
            });
            
            const data = await response.json();
            
            if (data.reply) {
                addMessage("ai", data.reply);
                clearInput();
                this.clearImages();
                
                if (this.currentMode !== 'chat') {
                    this.switchMode('chat');
                }
            } else {
                throw new Error(data?.error || 'Image processing failed');
            }
        } catch (error) {
            console.error('Image message failed:', error);
            addMessage("ai", `Error: ${error.message}`);
        } finally {
            this.isSending = false;
            isProcessingMessage = false;
        }
    }

    displayGeneratedImage(imageUrl, prompt) {
        const chatContainer = document.getElementById('chatContainer');
        if (!chatContainer) return;

        if (imageUrl.startsWith('generated_images/')) {
            imageUrl = `/static/${imageUrl}`;
        }

        const imageHTML = `
            <div class="message user generated-image-message">
                <div class="message-content">
                    <div class="image-prompt-text">${escapeHtml(prompt)}</div>
                    <div class="generated-image-container">
                        <img src="${imageUrl}" alt="${prompt}" class="generated-image">
                    </div>
                    <div class="timestamp">${getCurrentTime()}</div>
                </div>
            </div>
        `;
        
        chatContainer.insertAdjacentHTML('beforeend', imageHTML);
        
        const aiResponseHTML = `
            <div class="message ai">
                <div class="message-content">
                    Image generated successfully! I've created your "${prompt}"
                    <div class="timestamp">${getCurrentTime()}</div>
                </div>
            </div>
        `;
        chatContainer.insertAdjacentHTML('beforeend', aiResponseHTML);
        
        scrollToBottom();
    }

    updateNotificationCount() {
        if (!this.imageCountBadge) return;
        
        const count = this.selectedImages.length;
        
        if (count > 0) {
            this.imageCountBadge.textContent = count;
            this.imageCountBadge.classList.remove('hidden');
        } else {
            this.imageCountBadge.classList.add('hidden');
        }
    }

    clearImages() {
        this.selectedImages = [];
        this.updateNotificationCount();
    }
}

// ==================== MESSAGE FUNCTIONS ====================
async function createMessageElement(role, content, timestamp = null) {
    const msg = document.createElement("div");
    msg.classList.add("message", role);
    msg.setAttribute('data-role', role);
    
    const contentContainer = document.createElement("div");
    contentContainer.className = "message-content";
    
    // Render markdown using renderer.js
    if (typeof renderMarkdown !== 'undefined') {
        const html = await renderMarkdown(String(content));
        contentContainer.innerHTML = html;
        
        // Add timestamp
        const timeDiv = document.createElement("div");
        timeDiv.className = "timestamp";
        timeDiv.textContent = timestamp ? formatTimestamp(timestamp) : getCurrentTime();
        contentContainer.appendChild(timeDiv);
        
        // Add copy button for AI messages
        if (role === 'ai') {
            addCopyMessageButton(msg, content);
        }
    } else {
        // Fallback if renderer not loaded yet
        contentContainer.textContent = String(content);
        
        const timeDiv = document.createElement("div");
        timeDiv.className = "timestamp";
        timeDiv.textContent = timestamp ? formatTimestamp(timestamp) : getCurrentTime();
        contentContainer.appendChild(timeDiv);
    }

    msg.appendChild(contentContainer);
    return msg;
}

async function addMessage(role, content, timestamp = null, isHistory = false) {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) {
        console.error("Cannot add message: chat container not found!");
        return null;
    }
    
    const msg = await createMessageElement(role, content, timestamp);
    chatContainer.appendChild(msg);
    
    if (!isHistory) {
        setTimeout(() => {
            scrollToBottom();
        }, 100);
    }
    
    console.log(`Added ${role} message`);
    return msg;
}

function addCopyMessageButton(messageElement, content) {
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-message-btn';
    copyBtn.title = 'Copy message';
    copyBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
    `;
    
    copyBtn.onclick = function() {
        navigator.clipboard.writeText(content).then(() => {
            copyBtn.classList.add('copied');
            copyBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            `;
            setTimeout(() => {
                copyBtn.classList.remove('copied');
                copyBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                `;
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
    };
    
    messageElement.appendChild(copyBtn);
}

// ==================== CHAT HISTORY & PAGINATION ====================
async function loadChatHistory() {
    try {
        const response = await fetch("/api/get_profile");
        const data = await response.json();
        const history = data.chat_history || [];
        
        const chatContainer = document.getElementById("chatContainer");
        if (!chatContainer) return;

        if (history && history.length > 0) {
            console.log(`Loading ${history.length} messages from history`);
            
            // Load last 30 messages immediately
            const recentMessages = history.slice(-IMMEDIATE_LOAD_COUNT);
            
            // Load messages sequentially to handle async rendering
            for (const msg of recentMessages) {
                if (msg.role === "user" || msg.role === "assistant") {
                    await addMessage(
                        msg.role === "user" ? "user" : "ai",
                        msg.content,
                        msg.timestamp,
                        true
                    );
                }
            }
            
            setTimeout(() => {
                scrollToBottom();
                
                // Load older messages in background if there are more
                if (history.length > IMMEDIATE_LOAD_COUNT) {
                    setupScrollPagination(history);
                }
            }, 300);
            
            console.log(`Loaded ${recentMessages.length} recent messages`);
        } else {
            console.log("No chat history found");
            addMessage("ai", "Hello! I'm your AI companion. Let's start a new conversation!");
            scrollToBottom();
        }
    } catch (err) {
        console.error("Failed to load chat history:", err);
        addMessage("ai", "Hello! I'm your AI companion. Let's start a new conversation!");
        scrollToBottom();
    }
}

function setupScrollPagination(fullHistory) {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) return;
    
    const olderMessages = fullHistory.slice(0, -IMMEDIATE_LOAD_COUNT);
    let isLoadingOlder = false;
    
    chatContainer.addEventListener('scroll', async function() {
        if (isLoadingOlder) return;
        
        // Check if scrolled to top
        if (chatContainer.scrollTop < 100 && olderMessages.length > 0) {
            isLoadingOlder = true;
            await loadOlderMessages(olderMessages, chatContainer);
            olderMessages.length = 0; // Clear after loading
            isLoadingOlder = false;
        }
    });
}

async function loadOlderMessages(olderMessages, chatContainer) {
    console.log(`Loading ${olderMessages.length} older messages...`);
    
    const loadingIndicator = document.createElement('div');
    loadingIndicator.className = 'loading-older';
    loadingIndicator.innerHTML = `<div class="loading-spinner-small"></div> Loading older messages...`;
    chatContainer.insertBefore(loadingIndicator, chatContainer.firstChild);
    
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Load messages sequentially to handle async rendering
    const firstChild = chatContainer.firstChild;
    for (const msg of olderMessages) {
        if (msg.role === "user" || msg.role === "assistant") {
            const msgElement = await createMessageElement(
                msg.role === "user" ? "user" : "ai",
                msg.content,
                msg.timestamp
            );
            chatContainer.insertBefore(msgElement, firstChild);
        }
    }
    
    if (loadingIndicator.parentNode) {
        loadingIndicator.parentNode.removeChild(loadingIndicator);
    }
    
    console.log(`Loaded ${olderMessages.length} older messages`);
}

// ==================== SCROLL FUNCTIONS ====================
function scrollToBottom() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) return;
    
    chatContainer.scroll({
        top: chatContainer.scrollHeight,
        behavior: 'smooth'
    });
    
    const scrollBtn = document.getElementById("scrollToBottom");
    if (scrollBtn) {
        scrollBtn.classList.add("hidden");
    }
}

function initializeScrollButton() {
    const scrollBtn = document.getElementById("scrollToBottom");
    const chatContainer = document.getElementById("chatContainer");
    
    if (!scrollBtn || !chatContainer) return;
    
    scrollBtn.onclick = () => scrollToBottom();
    
    // Show/hide button based on scroll position
    chatContainer.addEventListener('scroll', () => {
        const scrollHeight = chatContainer.scrollHeight;
        const scrollPosition = chatContainer.scrollTop + chatContainer.clientHeight;
        const threshold = 200;
        
        if (scrollHeight - scrollPosition > threshold) {
            scrollBtn.classList.remove("hidden");
        } else {
            scrollBtn.classList.add("hidden");
        }
    });
}

// ==================== UTILITY FUNCTIONS ====================
function getCurrentTime() {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
}

function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    try {
        const date = new Date(timestamp);
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${hours}:${minutes}`;
    } catch (e) {
        console.error('Error formatting timestamp:', e);
        return '';
    }
}

function clearInput() {
    const input = document.getElementById('messageInput');
    if (input) {
        input.value = '';
        input.style.height = 'auto';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadCurrentSessionName() {
    try {
        const response = await fetch('/api/get_profile');
        const data = await response.json();
        
        const sessionNameElement = document.getElementById('sessionName');
        if (sessionNameElement && data.active_session) {
            sessionNameElement.textContent = data.active_session.name || 'Current Chat';
        }
    } catch (error) {
        console.error('Failed to load session name:', error);
    }
}

function initializeInputBehavior() {
    const input = document.getElementById('messageInput');
    if (!input) return;

    // Auto-resize textarea
    input.oninput = () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    };
}

// ==================== INITIALIZATION ====================
function initializeChat() {
    console.log("Initializing REBUILT chat system...");
    
    // Initialize scroll button
    initializeScrollButton();
    
    // Initialize input behavior
    initializeInputBehavior();
    
    // Load session name
    loadCurrentSessionName();
    
    // Load history
    loadChatHistory();
    
    // Initialize multimodal
    window.multimodal = new MultimodalManager();
    window.multimodal.init();
    
    console.log("REBUILT chat system ready!");
}

// Start when page loads
window.onload = function() {
    initializeChat();
};

// Global exports
window.addMessage = addMessage;
window.scrollToBottom = scrollToBottom;
window.loadChatHistory = loadChatHistory;
