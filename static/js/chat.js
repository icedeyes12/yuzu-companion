// [FILE: chat.js] - CLEAN REBUILD
// [VERSION: 2.0.0]
// [DATE: 2025-02-14]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Clean chat interface with markdown rendering via renderer.js]
// [AUTHOR: Project Lead: Bani Baskara]
// [LICENSE: MIT]

console.log("Starting chat.js v2.0...");

// ==================== GLOBAL STATE ====================
let isProcessingMessage = false;
let typingIndicator = null;

// ==================== MULTIMODAL MANAGER ====================
/**
 * Handles chat modes: chat, image upload/analysis, and image generation
 */
class MultimodalManager {
    constructor() {
        this.currentMode = 'chat';
        this.selectedImages = [];
        this.isDropdownOpen = false;
        this.isSending = false;
    }

    init() {
        console.log("Initializing MultimodalManager...");
        this.createToggleButton();
        this.setupEventListeners();
        this.patchSendButton();
        this.updateImageBadge();
    }

    // Create toggle button in input area
    createToggleButton() {
        const inputArea = document.querySelector('.input-area');
        if (!inputArea || inputArea.querySelector('.multimodal-toggle-container')) return;

        const html = `
            <div class="multimodal-toggle-container">
                <button class="multimodal-toggle-btn" type="button" title="Switch Mode">
                    <span class="toggle-icon">${this.getIcon('chat')}</span>
                    <div class="mode-indicator">C</div>
                    <div class="image-count-badge hidden">0</div>
                </button>
            </div>
        `;
        
        inputArea.insertAdjacentHTML('afterbegin', html);
        this.toggleBtn = inputArea.querySelector('.multimodal-toggle-btn');
        this.modeIndicator = inputArea.querySelector('.mode-indicator');
        this.imageBadge = inputArea.querySelector('.image-count-badge');
    }

    // Get SVG icons for different modes
    getIcon(type) {
        const icons = {
            chat: '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2H4c-1.1 0-1.99.9-1.99 2L2 22l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zM6 9h12v2H6V9zm8 5H6v-2h8v2zm4-6H6V6h12v2z"/></svg>',
            image: '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM5 19l3.5-4.5 2.5 3.01L14.5 11l4.5 6H5z"/></svg>',
            generate: '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM5 19l3.5-4.5 2.5 3.01L14.5 11l4.5 6H5z"/><path d="M14.5 11l1.5-2 1.5 2 2-1-2-1.5 2-1.5-2-1-1.5 2-1.5-2-1 1.5L13 8l-1.5 2z" opacity="0.7"/></svg>',
            upload: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>',
            close: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>',
            copy: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>',
            download: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>',
            regenerate: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>'
        };
        return icons[type] || icons.chat;
    }

    setupEventListeners() {
        if (!this.toggleBtn) return;
        
        this.toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this.toggleDropdown();
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.multimodal-toggle-container')) {
                this.closeDropdown();
            }
        });
    }

    // Override send button behavior
    patchSendButton() {
        const sendBtn = document.getElementById('sendButton');
        if (!sendBtn) return;

        sendBtn.onclick = (e) => {
            e.preventDefault();
            this.handleSend();
        };
    }

    // Main send handler - routes to appropriate API based on mode
    handleSend() {
        if (isProcessingMessage || this.isSending) {
            console.log("Already processing, please wait...");
            return;
        }

        const input = document.getElementById('messageInput');
        const text = input.value.trim();

        isProcessingMessage = true;

        if (this.currentMode === 'generate') {
            this.sendImageGeneration(text);
        } else if (this.currentMode === 'image' && this.selectedImages.length > 0) {
            this.sendImageAnalysis(text);
        } else {
            this.sendChatMessage(text);
        }
    }

    // Send regular chat message to /api/send_message
    async sendChatMessage(text) {
        if (!text) {
            isProcessingMessage = false;
            return;
        }

        addMessage("user", text);
        this.clearInput();
        
        this.showTypingIndicator();

        try {
            const response = await fetch("/api/send_message", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text })
            });
            
            const data = await response.json();
            this.hideTypingIndicator();
            
            if (data.reply) {
                addMessage("ai", data.reply);
            } else {
                addMessage("ai", "No response from server");
            }
        } catch (error) {
            console.error("Error sending message:", error);
            this.hideTypingIndicator();
            addMessage("ai", "Connection error. Please try again.");
        } finally {
            isProcessingMessage = false;
        }
    }

    // Send image generation request to /api/generate_image
    async sendImageGeneration(prompt) {
        if (!prompt) {
            alert('Please enter a prompt for image generation');
            isProcessingMessage = false;
            return;
        }

        this.isSending = true;
        addMessage("user", prompt);
        this.clearInput();

        try {
            const response = await fetch("/api/generate_image", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                this.displayGeneratedImage(data.image_url, prompt);
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

    // Send image analysis to /api/analyze_images
    async sendImageAnalysis(text) {
        if (this.selectedImages.length === 0) {
            alert('Please upload images first');
            isProcessingMessage = false;
            return;
        }

        this.isSending = true;
        addMessage("user", text || "Analyze these images");
        
        // Display uploaded images
        this.selectedImages.forEach(image => {
            this.displayUploadedImage(image);
        });

        try {
            const formData = new FormData();
            if (text) formData.append('message', text);
            
            this.selectedImages.forEach(image => {
                formData.append('images', image);
            });

            const response = await fetch("/api/send_message_with_images", {
                method: "POST",
                body: formData
            });
            
            const data = await response.json();
            
            if (data.reply) {
                addMessage("ai", data.reply);
                this.clearInput();
                this.clearImages();
                this.switchMode('chat');
            } else {
                throw new Error(data?.error || 'Image analysis failed');
            }
            
        } catch (error) {
            console.error('Image analysis failed:', error);
            addMessage("ai", `Error: ${error.message}`);
        } finally {
            this.isSending = false;
            isProcessingMessage = false;
        }
    }

    // Display uploaded image in chat
    displayUploadedImage(imageFile) {
        const chatContainer = document.getElementById('chatContainer');
        if (!chatContainer) return;

        const imageUrl = URL.createObjectURL(imageFile);
        const html = `
            <div class="message user uploaded-image">
                <div class="message-content">
                    <img src="${imageUrl}" alt="Uploaded" class="uploaded-image-preview">
                    <div class="timestamp">${getCurrentTime()}</div>
                </div>
            </div>
        `;
        
        chatContainer.insertAdjacentHTML('beforeend', html);
        scrollToBottom();
    }

    // Display generated image with actions
    displayGeneratedImage(imageUrl, prompt) {
        const chatContainer = document.getElementById('chatContainer');
        if (!chatContainer) return;

        // Fix image URL if needed
        if (imageUrl.startsWith('generated_images/')) {
            imageUrl = `/static/${imageUrl}`;
        }

        const html = `
            <div class="message ai generated-image">
                <div class="message-content">
                    <div class="generated-image-container">
                        <img src="${imageUrl}" alt="${this.escapeHtml(prompt)}" class="generated-image-preview">
                        <div class="image-actions">
                            <button class="image-action-btn" onclick="multimodal.downloadImage('${imageUrl}', '${this.escapeHtml(prompt)}')">
                                ${this.getIcon('download')} Download
                            </button>
                            <button class="image-action-btn" onclick="multimodal.regenerateImage('${this.escapeHtml(prompt)}')">
                                ${this.getIcon('regenerate')} Regenerate
                            </button>
                        </div>
                    </div>
                    <p>Image generated successfully!</p>
                    <div class="timestamp">${getCurrentTime()}</div>
                </div>
            </div>
        `;
        
        chatContainer.insertAdjacentHTML('beforeend', html);
        scrollToBottom();
    }

    // Download generated image
    downloadImage(imageUrl, filename) {
        const link = document.createElement('a');
        link.href = imageUrl;
        link.download = `${filename.replace(/[^a-z0-9]/gi, '_')}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // Regenerate image with same prompt
    regenerateImage(prompt) {
        const input = document.getElementById('messageInput');
        if (input) {
            input.value = prompt;
            this.switchMode('generate');
            setTimeout(() => this.sendImageGeneration(prompt), 100);
        }
    }

    // Toggle mode dropdown
    toggleDropdown() {
        if (this.isDropdownOpen) {
            this.closeDropdown();
        } else {
            this.openDropdown();
        }
    }

    // Open mode dropdown
    openDropdown() {
        this.closeDropdown();

        const html = `
            <div class="multimodal-dropdown">
                <div class="multimodal-option ${this.currentMode === 'chat' ? 'active' : ''}" data-mode="chat">
                    <div class="option-icon">${this.getIcon('chat')}</div>
                    <div class="option-content">
                        <div class="option-text">Chat</div>
                        <div class="option-description">Normal conversation</div>
                    </div>
                </div>
                <div class="multimodal-option ${this.currentMode === 'generate' ? 'active' : ''}" data-mode="generate">
                    <div class="option-icon">${this.getIcon('generate')}</div>
                    <div class="option-content">
                        <div class="option-text">Generate Image</div>
                        <div class="option-description">Create images with AI</div>
                    </div>
                </div>
                <div class="multimodal-option ${this.currentMode === 'image' ? 'active' : ''}" data-mode="image">
                    <div class="option-icon">${this.getIcon('image')}</div>
                    <div class="option-content">
                        <div class="option-text">Analyze Image</div>
                        <div class="option-description">Upload & analyze images</div>
                    </div>
                </div>
                
                ${this.currentMode === 'image' ? `
                <div class="image-upload-section">
                    <div class="upload-status">
                        ${this.selectedImages.length > 0 ? `${this.selectedImages.length} image(s) selected` : 'No images selected'}
                    </div>
                    <input type="file" id="imageUploadInput" accept="image/*" multiple style="display: none;">
                    <button class="upload-btn" onclick="multimodal.openFilePicker()">
                        ${this.getIcon('upload')} ${this.selectedImages.length > 0 ? 'Add More' : 'Choose Images'}
                    </button>
                    ${this.selectedImages.length > 0 ? this.renderImagePreviews() : ''}
                </div>
                ` : ''}
            </div>
        `;

        this.toggleBtn.insertAdjacentHTML('afterend', html);
        this.isDropdownOpen = true;

        // Attach mode switch listeners
        const dropdown = this.toggleBtn.nextElementSibling;
        dropdown.querySelectorAll('.multimodal-option').forEach(option => {
            option.addEventListener('click', () => {
                this.switchMode(option.dataset.mode);
                this.closeDropdown();
            });
        });

        // Setup file input for image mode
        if (this.currentMode === 'image') {
            const fileInput = document.getElementById('imageUploadInput');
            if (fileInput) {
                fileInput.onchange = (e) => {
                    if (e.target.files.length > 0) {
                        this.addImages(Array.from(e.target.files));
                        this.closeDropdown();
                        setTimeout(() => this.openDropdown(), 100);
                    }
                };
            }
        }
    }

    // Close dropdown
    closeDropdown() {
        const dropdown = document.querySelector('.multimodal-dropdown');
        if (dropdown) dropdown.remove();
        this.isDropdownOpen = false;
    }

    // Switch mode
    switchMode(mode) {
        this.currentMode = mode;
        
        const indicators = { chat: 'C', generate: 'G', image: 'U' };
        this.toggleBtn.querySelector('.toggle-icon').innerHTML = this.getIcon(mode);
        this.modeIndicator.textContent = indicators[mode];
        
        this.updateImageBadge();
        this.updateInputPlaceholder();
    }

    // Update image count badge
    updateImageBadge() {
        if (!this.imageBadge) return;
        
        const count = this.selectedImages.length;
        
        if (count > 0 && this.currentMode === 'image') {
            this.imageBadge.textContent = count;
            this.imageBadge.classList.remove('hidden');
        } else {
            this.imageBadge.classList.add('hidden');
        }
    }

    // Update input placeholder based on mode
    updateInputPlaceholder() {
        const input = document.getElementById('messageInput');
        if (!input) return;
        
        const placeholders = {
            chat: 'Type your message...',
            generate: 'Describe the image to generate...',
            image: this.selectedImages.length > 0 
                ? `Ask about ${this.selectedImages.length} image(s)...`
                : 'Upload images first...'
        };
        
        input.placeholder = placeholders[this.currentMode];
    }

    // Add images
    addImages(files) {
        this.selectedImages = [...this.selectedImages, ...files];
        this.updateImageBadge();
        this.updateInputPlaceholder();
    }

    // Remove single image
    removeImage(index) {
        this.selectedImages.splice(index, 1);
        this.updateImageBadge();
        this.closeDropdown();
        setTimeout(() => this.openDropdown(), 100);
    }

    // Clear all images
    clearImages() {
        this.selectedImages = [];
        this.updateImageBadge();
        this.updateInputPlaceholder();
    }

    // Render image previews in dropdown
    renderImagePreviews() {
        if (this.selectedImages.length === 0) return '';
        
        const previews = this.selectedImages.map((image, index) => {
            const url = URL.createObjectURL(image);
            return `
                <div class="image-preview-item">
                    <img src="${url}" alt="Preview ${index + 1}">
                    <button class="remove-preview-btn" onclick="multimodal.removeImage(${index})">
                        ${this.getIcon('close')}
                    </button>
                </div>
            `;
        }).join('');

        return `
            <div class="image-previews">
                <div class="previews-header">
                    <span>${this.selectedImages.length} image(s)</span>
                    <button class="clear-all-btn" onclick="multimodal.clearImages()">Clear All</button>
                </div>
                <div class="previews-grid">${previews}</div>
            </div>
        `;
    }

    // Open file picker
    openFilePicker() {
        document.getElementById('imageUploadInput')?.click();
    }

    // Clear input
    clearInput() {
        const input = document.getElementById('messageInput');
        if (input) {
            input.value = '';
            input.style.height = 'auto';
        }
    }

    // Show typing indicator
    showTypingIndicator() {
        if (typingIndicator) {
            typingIndicator.classList.remove('hidden');
        }
    }

    // Hide typing indicator
    hideTypingIndicator() {
        if (typingIndicator) {
            typingIndicator.classList.add('hidden');
        }
    }

    // Escape HTML
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// ==================== MESSAGE FUNCTIONS ====================

/**
 * Create message element
 * @param {string} role - 'user' or 'ai'
 * @param {string} content - Message content
 * @param {string} timestamp - Optional timestamp
 * @returns {HTMLElement} Message element
 */
function createMessageElement(role, content, timestamp = null) {
    const msg = document.createElement("div");
    msg.classList.add("message", role);
    
    const contentDiv = document.createElement("div");
    contentDiv.classList.add("message-content");

    // AI messages: use markdown renderer from renderer.js
    // User messages: plain text
    if (role === 'ai' && window.messageRenderer) {
        contentDiv.innerHTML = window.messageRenderer.render(content);
    } else {
        // User messages: plain text with line breaks
        contentDiv.textContent = content;
    }

    // Add timestamp
    const timeDiv = document.createElement("div");
    timeDiv.className = "timestamp";
    timeDiv.textContent = timestamp ? formatTimestamp(timestamp) : getCurrentTime();
    contentDiv.appendChild(timeDiv);

    // Add copy button for AI messages
    if (role === 'ai') {
        const copyBtn = document.createElement("button");
        copyBtn.className = "copy-message-btn";
        copyBtn.title = "Copy message";
        copyBtn.innerHTML = window.multimodal?.getIcon('copy') || '📋';
        copyBtn.onclick = () => copyMessageContent(contentDiv, copyBtn);
        contentDiv.appendChild(copyBtn);
    }

    msg.appendChild(contentDiv);
    return msg;
}

/**
 * Add message to chat
 * @param {string} role - 'user' or 'ai'
 * @param {string} content - Message content
 * @param {string} timestamp - Optional timestamp
 * @param {boolean} isHistory - Is this a history message?
 */
function addMessage(role, content, timestamp = null, isHistory = false) {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) {
        console.error("Chat container not found!");
        return;
    }
    
    const msg = createMessageElement(role, content, timestamp);
    chatContainer.appendChild(msg);
    
    // Only scroll for new messages, not history
    if (!isHistory) {
        setTimeout(scrollToBottom, 50);
    }
    
    return msg;
}

/**
 * Copy message content to clipboard
 */
function copyMessageContent(contentDiv, button) {
    // Get text content without timestamp and button
    const timestamp = contentDiv.querySelector('.timestamp');
    const copyBtn = contentDiv.querySelector('.copy-message-btn');
    
    // Temporarily hide elements we don't want to copy
    if (timestamp) timestamp.style.display = 'none';
    if (copyBtn) copyBtn.style.display = 'none';
    
    const textToCopy = contentDiv.innerText;
    
    // Restore elements
    if (timestamp) timestamp.style.display = '';
    if (copyBtn) copyBtn.style.display = '';
    
    navigator.clipboard.writeText(textToCopy).then(() => {
        const originalHTML = button.innerHTML;
        button.innerHTML = '✓';
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

// ==================== HISTORY & PAGINATION ====================

/**
 * Load chat history from /api/get_profile
 * Loads last 30 messages initially, then loads older messages in background
 */
async function loadChatHistory() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) {
        console.error("Chat container not found!");
        return;
    }
    
    try {
        chatContainer.innerHTML = '<div class="loading">Loading messages...</div>';
        
        const response = await fetch("/api/get_profile");
        const data = await response.json();
        const history = data.chat_history || [];

        if (history.length > 0) {
            chatContainer.innerHTML = '';
            console.log(`Loading ${history.length} messages from history`);
            
            // Load last 30 messages immediately
            const recentCount = Math.min(30, history.length);
            const recentMessages = history.slice(-recentCount);
            
            // Use document fragment for efficient DOM insertion
            const fragment = document.createDocumentFragment();
            
            recentMessages.forEach(msg => {
                if (msg.role === "user" || msg.role === "assistant") {
                    const role = msg.role === "user" ? "user" : "ai";
                    const msgElement = createMessageElement(role, msg.content, msg.timestamp);
                    fragment.appendChild(msgElement);
                }
            });
            
            chatContainer.appendChild(fragment);
            scrollToBottom();
            
            console.log(`Loaded ${recentCount} recent messages`);
            
            // Load older messages in background if there are more
            if (history.length > recentCount) {
                setTimeout(() => loadOlderMessages(history, recentCount), 500);
            }
        } else {
            chatContainer.innerHTML = '';
            addMessage("ai", "Hello! I'm your AI companion. How can I help you today?");
        }
    } catch (error) {
        console.error("Failed to load chat history:", error);
        chatContainer.innerHTML = '';
        addMessage("ai", "Hello! I'm your AI companion. How can I help you today?");
    }
}

/**
 * Load older messages in background
 * @param {Array} fullHistory - Complete chat history
 * @param {number} alreadyLoadedCount - Number of messages already loaded
 */
async function loadOlderMessages(fullHistory, alreadyLoadedCount) {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) return;
    
    const olderMessages = fullHistory.slice(0, -alreadyLoadedCount);
    const totalOlder = olderMessages.length;
    
    if (totalOlder === 0) return;
    
    console.log(`Loading ${totalOlder} older messages...`);
    
    // Show loading indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading-older';
    loadingDiv.textContent = `Loading ${totalOlder} older messages...`;
    chatContainer.insertBefore(loadingDiv, chatContainer.firstChild);
    
    // Wait a bit for smooth UX
    await new Promise(resolve => setTimeout(resolve, 100));
    
    // Create fragment for batch insertion
    const fragment = document.createDocumentFragment();
    
    olderMessages.forEach(msg => {
        if (msg.role === "user" || msg.role === "assistant") {
            const role = msg.role === "user" ? "user" : "ai";
            const msgElement = createMessageElement(role, msg.content, msg.timestamp);
            fragment.appendChild(msgElement);
        }
    });
    
    // Remove loading indicator and insert messages
    loadingDiv.remove();
    chatContainer.insertBefore(fragment, chatContainer.firstChild);
    
    console.log(`Loaded ${totalOlder} older messages`);
}

// ==================== SCROLL SYSTEM ====================

/**
 * Scroll to bottom of chat
 */
function scrollToBottom() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) return;
    
    chatContainer.scroll({
        top: chatContainer.scrollHeight,
        behavior: 'smooth'
    });
    
    // Hide scroll button
    const scrollBtn = document.getElementById("scrollToBottomBtn");
    if (scrollBtn) {
        scrollBtn.classList.add("hidden");
    }
}

/**
 * Create scroll-to-bottom button
 */
function createScrollButton() {
    const existing = document.getElementById("scrollToBottomBtn");
    if (existing) return;
    
    const btn = document.createElement("button");
    btn.id = "scrollToBottomBtn";
    btn.title = "Scroll to bottom";
    btn.innerHTML = "↓";
    btn.classList.add("hidden");
    btn.onclick = scrollToBottom;
    
    document.body.appendChild(btn);
}

/**
 * Initialize scroll button auto-hide behavior
 */
function initializeScrollButton() {
    const chatContainer = document.getElementById("chatContainer");
    const scrollBtn = document.getElementById("scrollToBottomBtn");
    
    if (!chatContainer || !scrollBtn) return;
    
    let scrollTimeout;
    
    chatContainer.addEventListener('scroll', () => {
        if (scrollTimeout) clearTimeout(scrollTimeout);
        
        scrollTimeout = setTimeout(() => {
            const threshold = 150;
            const scrollPosition = chatContainer.scrollTop + chatContainer.clientHeight;
            const scrollHeight = chatContainer.scrollHeight;
            const distanceFromBottom = scrollHeight - scrollPosition;
            
            if (distanceFromBottom > threshold) {
                scrollBtn.classList.remove("hidden");
            } else {
                scrollBtn.classList.add("hidden");
            }
        }, 50);
    });
}

// ==================== SESSION ====================

/**
 * Load current session name
 */
async function loadSessionName() {
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

// ==================== INPUT BEHAVIOR ====================

/**
 * Initialize input textarea behavior
 */
function initializeInputBehavior() {
    const input = document.getElementById('messageInput');
    if (!input) return;

    // Auto-resize on input
    input.oninput = () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 400) + 'px';
    };
}

// ==================== UTILITY FUNCTIONS ====================

/**
 * Format timestamp for display
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    
    try {
        const date = new Date(timestamp);
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    } catch (e) {
        console.error('Error formatting timestamp:', e);
        return timestamp;
    }
}

/**
 * Get current time in HH:MM format
 */
function getCurrentTime() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

// ==================== INITIALIZATION ====================

/**
 * Initialize chat system
 */
function initializeChat() {
    console.log("Initializing chat system...");
    
    // Get typing indicator
    typingIndicator = document.getElementById('typingIndicator');
    
    // Initialize scroll system
    createScrollButton();
    initializeScrollButton();
    
    // Initialize input
    initializeInputBehavior();
    
    // Load session name
    loadSessionName();
    
    // Load chat history
    loadChatHistory();
    
    // Initialize multimodal manager
    window.multimodal = new MultimodalManager();
    window.multimodal.init();
    
    console.log("Chat system ready!");
}

// Start when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeChat);
} else {
    initializeChat();
}

// ==================== GLOBAL EXPORTS ====================
window.addMessage = addMessage;
window.scrollToBottom = scrollToBottom;
window.loadChatHistory = loadChatHistory;
