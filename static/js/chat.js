// [FILE: chat.js]
// [VERSION: 2.0.0]
// [DATE: 2026-02-14]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Rebuilt chat interface with pagination and clean architecture]
// [AUTHOR: Project Lead: Bani Baskara]
// [LICENSE: MIT]

console.log("Starting Chat Interface v2.0.0...");

// ==================== STATE MANAGEMENT ====================
let isProcessingMessage = false;
let currentSessionId = null;
let allMessages = [];
let displayedMessageCount = 0;
const MESSAGES_PER_PAGE = 30;

// ==================== MULTIMODAL MANAGER ====================
class MultimodalManager {
    constructor() {
        this.currentMode = 'chat';
        this.selectedImages = [];
        this.isDropdownOpen = false;
        this.isSending = false;
    }

    init() {
        console.log("Initializing Multimodal Manager...");
        this.createToggle();
        this.setupEventListeners();
        this.patchSendButton();
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
        const container = this.toggleBtn.closest('.multimodal-toggle-container');
        if (this.isDropdownOpen) {
            this.showDropdown(container);
        } else {
            this.closeDropdown();
        }
    }

    showDropdown(container) {
        const existingDropdown = container.querySelector('.mode-dropdown');
        if (existingDropdown) {
            existingDropdown.remove();
        }

        const dropdown = document.createElement('div');
        dropdown.className = 'mode-dropdown';
        dropdown.innerHTML = `
            <div class="mode-option" data-mode="chat">
                <span class="mode-icon">${this.getSVGIcon('chat')}</span>
                <span class="mode-label">Chat Mode</span>
            </div>
            <div class="mode-option" data-mode="image">
                <span class="mode-icon">${this.getSVGIcon('image')}</span>
                <span class="mode-label">Image Analysis</span>
            </div>
            <div class="mode-option" data-mode="generate">
                <span class="mode-icon">${this.getSVGIcon('generate')}</span>
                <span class="mode-label">Generate Image</span>
            </div>
        `;
        
        container.appendChild(dropdown);

        const options = dropdown.querySelectorAll('.mode-option');
        options.forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                const mode = opt.dataset.mode;
                this.switchMode(mode);
                this.closeDropdown();
            });
        });
    }

    closeDropdown() {
        this.isDropdownOpen = false;
        const dropdown = document.querySelector('.mode-dropdown');
        if (dropdown) {
            dropdown.remove();
        }
    }

    switchMode(mode) {
        this.currentMode = mode;
        const icon = this.toggleBtn.querySelector('.toggle-icon');
        icon.innerHTML = this.getSVGIcon(mode);
        
        const indicators = {
            'chat': 'C',
            'image': 'I',
            'generate': 'G'
        };
        this.modeIndicator.textContent = indicators[mode];
        
        console.log(`Switched to ${mode} mode`);
    }

    patchSendButton() {
        const sendBtn = document.getElementById('sendButton');
        if (!sendBtn) return;

        sendBtn.onclick = (e) => {
            e.preventDefault();
            this.handleSend();
        };
    }

    handleSend() {
        if (isProcessingMessage) {
            console.log("Message already being processed, please wait...");
            return;
        }

        const input = document.getElementById('messageInput');
        const text = input.value.trim();

        if (this.isSending) {
            console.log("Already sending, please wait...");
            return;
        }

        isProcessingMessage = true;

        if (this.currentMode === 'generate') {
            this.handleImageGeneration(text);
        } else if (this.currentMode === 'image' || this.selectedImages.length > 0) {
            this.handleImageMessage(text);
        } else {
            this.handleChatMessage(text);
        }
    }

    async handleChatMessage(text) {
        if (!text) {
            isProcessingMessage = false;
            return;
        }

        addMessage("user", text);
        this.clearInput();
        
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) typingIndicator.classList.remove("hidden");

        try {
            const response = await fetch("/api/send_message", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text }),
            });
            
            const data = await response.json();
            
            if (typingIndicator) typingIndicator.classList.add("hidden");
            
            if (data.reply) {
                addMessage("ai", data.reply);
            } else {
                addMessage("ai", "No response from server");
            }
        } catch (error) {
            console.error("Error sending message:", error);
            if (typingIndicator) typingIndicator.classList.add("hidden");
            addMessage("ai", "Connection error. Please try again.");
        } finally {
            isProcessingMessage = false;
            this.isSending = false;
        }
    }

    async handleImageGeneration(prompt) {
        if (!prompt.trim()) {
            alert('Please enter a prompt for image generation');
            isProcessingMessage = false;
            return;
        }

        this.isSending = true;

        try {
            console.log("Generating image with prompt:", prompt);
            
            addMessage("user", prompt);
            
            const typingIndicator = document.getElementById('typingIndicator');
            if (typingIndicator) typingIndicator.classList.remove("hidden");
            
            const response = await fetch("/api/generate_image", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt })
            });
            
            const data = await response.json();
            
            if (typingIndicator) typingIndicator.classList.add("hidden");
            
            if (data.status === 'success') {
                const imageMarkdown = `![Generated Image](${data.image_url})`;
                addMessage("ai", imageMarkdown);
                this.clearInput();
            } else {
                throw new Error(data.error || 'Image generation failed');
            }
        } catch (error) {
            console.error("Image generation error:", error);
            const typingIndicator = document.getElementById('typingIndicator');
            if (typingIndicator) typingIndicator.classList.add("hidden");
            addMessage("ai", `Image generation failed: ${error.message}`);
        } finally {
            isProcessingMessage = false;
            this.isSending = false;
        }
    }

    async handleImageMessage(text) {
        if (!text && this.selectedImages.length === 0) {
            isProcessingMessage = false;
            return;
        }

        this.isSending = true;

        try {
            const userMessage = text || "[Image uploaded]";
            addMessage("user", userMessage);
            
            const typingIndicator = document.getElementById('typingIndicator');
            if (typingIndicator) typingIndicator.classList.remove("hidden");

            const formData = new FormData();
            formData.append('message', text);
            
            this.selectedImages.forEach((img, idx) => {
                formData.append(`image_${idx}`, img.file);
            });

            const response = await fetch("/api/send_image_message", {
                method: "POST",
                body: formData
            });

            const data = await response.json();
            
            if (typingIndicator) typingIndicator.classList.add("hidden");
            
            if (data.reply) {
                addMessage("ai", data.reply);
            } else {
                addMessage("ai", "No response from server");
            }

            this.selectedImages = [];
            this.clearInput();
        } catch (error) {
            console.error("Image message error:", error);
            const typingIndicator = document.getElementById('typingIndicator');
            if (typingIndicator) typingIndicator.classList.add("hidden");
            addMessage("ai", `Error sending image: ${error.message}`);
        } finally {
            isProcessingMessage = false;
            this.isSending = false;
        }
    }

    clearInput() {
        const input = document.getElementById('messageInput');
        if (input) {
            input.value = '';
            input.style.height = 'auto';
        }
    }
}

// ==================== MESSAGE RENDERING ====================
function createMessageElement(role, content, timestamp = null) {
    const msg = document.createElement("div");
    msg.classList.add("message", role);
    
    const displayTime = timestamp ? formatTimestamp(timestamp) : getCurrentTime24h();

    const contentContainer = document.createElement("div");
    contentContainer.className = "message-content";

    // Use renderer.js if available
    if (typeof renderer !== 'undefined' && renderer) {
        contentContainer.innerHTML = renderer.render(String(content));
    } else {
        contentContainer.textContent = String(content);
    }

    const messageFooter = document.createElement("div");
    messageFooter.className = "message-footer";

    const timeDiv = document.createElement("div");
    timeDiv.className = "timestamp";
    timeDiv.textContent = displayTime;
    messageFooter.appendChild(timeDiv);

    // Add copy button for AI messages
    if (role === "ai") {
        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-message-btn";
        copyBtn.title = "Copy message";
        copyBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>`;
        copyBtn.onclick = () => copyMessageToClipboard(copyBtn, content);
        messageFooter.appendChild(copyBtn);
    }

    contentContainer.appendChild(messageFooter);
    msg.appendChild(contentContainer);
    
    return msg;
}

function addMessage(role, content, timestamp = null, isHistory = false) {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) {
        console.error("Cannot add message: chat container not found!");
        return null;
    }
    
    const msg = createMessageElement(role, content, timestamp);
    chatContainer.appendChild(msg);
    
    if (!isHistory) {
        setTimeout(() => {
            scrollToBottom();
        }, 50);
    }
    
    console.log(`Added ${role} message`);
    return msg;
}

function copyMessageToClipboard(button, content) {
    // Strip HTML tags for plain text copy
    const temp = document.createElement('div');
    temp.innerHTML = content;
    const text = temp.textContent || temp.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        const originalHTML = button.innerHTML;
        button.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"></polyline>
        </svg>`;
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy message:', err);
    });
}

// ==================== TIMESTAMP FORMATTING ====================
function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    try {
        const dbDate = new Date(timestamp);
        let hours = dbDate.getHours();
        let minutes = dbDate.getMinutes();
        
        hours = hours < 10 ? '0' + hours : hours;
        minutes = minutes < 10 ? '0' + minutes : minutes;
        
        return `${hours}:${minutes}`;
    } catch (e) {
        console.error('Error formatting timestamp:', e, timestamp);
        return timestamp;
    }
}

function getCurrentTime24h() {
    const now = new Date();
    let hours = now.getHours();
    let minutes = now.getMinutes();
    hours = hours < 10 ? '0' + hours : hours;
    minutes = minutes < 10 ? '0' + minutes : minutes;
    return `${hours}:${minutes}`;
}

// ==================== CHAT HISTORY WITH PAGINATION ====================
async function loadChatHistory() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) {
        console.error("Cannot load history: chat container not found!");
        return;
    }
    
    try {
        chatContainer.innerHTML = '<div class="loading">Loading recent messages...</div>';
        setTimeout(scrollToBottom, 100);
        
        const res = await fetch("/api/get_profile");
        const data = await res.json();
        allMessages = data.chat_history || [];

        if (allMessages.length > 0) {
            chatContainer.innerHTML = '';
            console.log(`Loaded ${allMessages.length} messages from history`);
            
            // Display last 30 messages initially
            displayedMessageCount = Math.min(MESSAGES_PER_PAGE, allMessages.length);
            const messagesToShow = allMessages.slice(-displayedMessageCount);
            
            const fragment = document.createDocumentFragment();
            
            messagesToShow.forEach(msg => {
                if (msg.role === "user" || msg.role === "assistant") {
                    const msgElement = createMessageElement(
                        msg.role === "user" ? "user" : "ai", 
                        msg.content, 
                        msg.timestamp
                    );
                    fragment.appendChild(msgElement);
                }
            });
            
            chatContainer.appendChild(fragment);
            
            setTimeout(() => {
                scrollToBottom();
                
                // Setup scroll listener for loading older messages
                if (allMessages.length > displayedMessageCount) {
                    setupScrollPagination();
                }
            }, 100);
            
            console.log(`Displayed ${displayedMessageCount} recent messages`);
        } else {
            console.log("No chat history found");
            chatContainer.innerHTML = '';
            addMessage("ai", "Hello! I'm your AI companion. Let's start a new conversation!");
            scrollToBottom();
        }
    } catch (err) {
        console.error("Failed to load chat history:", err);
        chatContainer.innerHTML = '';
        addMessage("ai", "Hello! I'm your AI companion. Let's start a new conversation!");
        scrollToBottom();
    }
}

function setupScrollPagination() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) return;
    
    let isLoadingOlder = false;
    
    chatContainer.addEventListener('scroll', async () => {
        // Check if scrolled to top (within 50px)
        if (chatContainer.scrollTop < 50 && !isLoadingOlder) {
            if (displayedMessageCount < allMessages.length) {
                isLoadingOlder = true;
                await loadOlderMessages();
                isLoadingOlder = false;
            }
        }
        
        // Show/hide scroll to bottom button
        updateScrollButton();
    });
}

async function loadOlderMessages() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) return;
    
    const remainingMessages = allMessages.length - displayedMessageCount;
    if (remainingMessages === 0) return;
    
    const messagesToLoad = Math.min(MESSAGES_PER_PAGE, remainingMessages);
    const startIndex = allMessages.length - displayedMessageCount - messagesToLoad;
    const endIndex = allMessages.length - displayedMessageCount;
    
    console.log(`Loading ${messagesToLoad} older messages...`);
    
    // Save scroll position
    const oldScrollHeight = chatContainer.scrollHeight;
    
    const fragment = document.createDocumentFragment();
    const olderMessages = allMessages.slice(startIndex, endIndex);
    
    olderMessages.forEach(msg => {
        if (msg.role === "user" || msg.role === "assistant") {
            const msgElement = createMessageElement(
                msg.role === "user" ? "user" : "ai", 
                msg.content, 
                msg.timestamp
            );
            fragment.appendChild(msgElement);
        }
    });
    
    // Insert at the beginning
    chatContainer.insertBefore(fragment, chatContainer.firstChild);
    
    displayedMessageCount += messagesToLoad;
    
    // Restore scroll position
    chatContainer.scrollTop = chatContainer.scrollHeight - oldScrollHeight;
    
    console.log(`Now displaying ${displayedMessageCount} messages`);
}

// ==================== SCROLL MANAGEMENT ====================
function scrollToBottom() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) {
        console.error("Chat container not found!");
        return;
    }
    
    chatContainer.scroll({
        top: chatContainer.scrollHeight,
        behavior: 'smooth'
    });
    
    updateScrollButton();
}

function updateScrollButton() {
    const chatContainer = document.getElementById("chatContainer");
    const scrollBtn = document.getElementById("scrollToBottomBtn");
    
    if (!chatContainer || !scrollBtn) return;
    
    // Show button if not near bottom (within 100px)
    const isNearBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
    
    if (isNearBottom) {
        scrollBtn.classList.add('hidden');
    } else {
        scrollBtn.classList.remove('hidden');
    }
}

// ==================== SESSION MANAGEMENT ====================
async function loadSessionInfo() {
    try {
        const res = await fetch("/api/get_profile");
        const data = await res.json();
        
        const sessionNameEl = document.getElementById("sessionName");
        if (sessionNameEl && data.current_session) {
            sessionNameEl.textContent = data.current_session.name || "Current Session";
        }
    } catch (err) {
        console.error("Failed to load session info:", err);
    }
}

// ==================== INPUT HANDLING ====================
function setupInputHandlers() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendButton');
    
    if (!input || !sendBtn) return;
    
    // Auto-resize textarea
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 150) + 'px';
    });
    
    // Enter to send, Shift+Enter for new line
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn.click();
        }
    });
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', async () => {
    console.log("Initializing chat interface...");
    
    // Setup scroll to bottom button
    const scrollBtn = document.getElementById('scrollToBottomBtn');
    if (scrollBtn) {
        scrollBtn.addEventListener('click', scrollToBottom);
    }
    
    // Setup input handlers
    setupInputHandlers();
    
    // Initialize multimodal manager and make it globally accessible
    window.multimodal = new MultimodalManager();
    window.multimodal.init();
    
    // Load session info
    await loadSessionInfo();
    
    // Load chat history
    await loadChatHistory();
    
    console.log("Chat interface initialized successfully");
});

// Global function for session creation (called from sidebar)
window.createNewSession = function() {
    console.log("Creating new session...");
    // This will be handled by sidebar.js
};
