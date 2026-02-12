// ==================== CHAT UNIFIED SCRIPT ====================
// Single script controller for chat page
// Combines message rendering, multimodal support, and UI interactions
// No conflicts - replaces both chat.js and chat-new.js

console.log("Initializing unified chat controller...");

// ==================== GLOBAL STATE ====================
let isSendingMessage = false;
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
                     </svg>`,
            download: `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
                     </svg>`,
            regenerate: `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
                       </svg>`,
            close: `<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                   <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                  </svg>`,
            upload: `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/>
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

    patchSendButton() {
        const sendBtn = document.getElementById('sendButton');
        if (!sendBtn) return;

        // Override send button to use multimodal handler
        sendBtn.onclick = (e) => {
            e.preventDefault();
            this.handleSend();
        };
    }

    handleSend() {
        if (isSendingMessage) {
            console.log("Message already being processed, please wait...");
            return;
        }

        const input = document.getElementById('messageInput');
        const text = input.value.trim();

        if (this.isSending) {
            console.log("Already sending, please wait...");
            return;
        }

        isSendingMessage = true;

        if (this.currentMode === 'generate') {
            this.handleImageGeneration(text);
        } else if (this.currentMode === 'image' || this.selectedImages.length > 0) {
            this.handleImageMessage(text);
        } else {
            sendMessage();  // Use the regular sendMessage function
        }
    }

    async handleImageGeneration(prompt) {
        if (!prompt.trim()) {
            alert('Please enter a prompt for image generation');
            isSendingMessage = false;
            return;
        }

        this.isSending = true;
        const sendBtn = document.getElementById('sendButton');
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.textContent = 'Generating...';
        }

        try {
            const chatContainer = document.getElementById('chatContainer');
            const userMessage = createMessageElement('user', prompt, new Date().toISOString());
            chatContainer.appendChild(userMessage);
            
            const response = await fetch("/api/generate_image", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt })
            });
            
            const data = await response.json();
            
            if (data.status === 'success') {
                // Show generated image in AI message
                let imageUrl = data.image_url;
                if (!imageUrl.startsWith('/') && !imageUrl.startsWith('http')) {
                    imageUrl = `/static/${imageUrl}`;
                }
                
                const imageMarkdown = `I' ve created that image for you!\n\n![Generated Image](${imageUrl})`;
                const aiMessage = createMessageElement('ai', imageMarkdown, new Date().toISOString());
                chatContainer.appendChild(aiMessage);
                
                this.clearInput();
                scrollToBottom();
            } else {
                throw new Error(data.error || 'Image generation failed');
            }
            
        } catch (error) {
            console.error('Image generation failed:', error);
            const errorMessage = createMessageElement('ai', `Error: ${error.message}`, new Date().toISOString());
            chatContainer.appendChild(errorMessage);
        } finally {
            this.isSending = false;
            isSendingMessage = false;
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.textContent = 'Send';
            }
        }
    }

    async handleImageMessage(text) {
        if (!text && this.selectedImages.length === 0) {
            alert('Please enter a message or upload images');
            isSendingMessage = false;
            return;
        }

        this.isSending = true;
        const sendBtn = document.getElementById('sendButton');
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.textContent = 'Sending...';
        }

        try {
            const chatContainer = document.getElementById('chatContainer');
            const userMessage = createMessageElement('user', text || "Analyze these images", new Date().toISOString());
            chatContainer.appendChild(userMessage);

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
                const aiMessage = createMessageElement('ai', data.reply, new Date().toISOString());
                chatContainer.appendChild(aiMessage);
                
                this.clearInput();
                this.clearImages();
                
                if (this.currentMode !== 'chat') {
                    this.switchMode('chat');
                }
                
                scrollToBottom();
            } else {
                throw new Error(data?.error || 'Image processing failed');
            }
            
        } catch (error) {
            console.error('Image message failed:', error);
            const errorMessage = createMessageElement('ai', `Error: ${error.message}`, new Date().toISOString());
            chatContainer.appendChild(errorMessage);
        } finally {
            this.isSending = false;
            isSendingMessage = false;
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.textContent = 'Send';
            }
        }
    }

    updateNotificationCount() {
        if (!this.imageCountBadge) return;
        
        const count = this.selectedImages.length;
        
        if (count > 0) {
            this.imageCountBadge.textContent = count;
            this.imageCountBadge.classList.remove('hidden');
            
            this.imageCountBadge.classList.add('pulse');
            setTimeout(() => {
                this.imageCountBadge.classList.remove('pulse');
            }, 1000);
        } else {
            this.imageCountBadge.classList.add('hidden');
        }
    }

    addImages(files) {
        this.selectedImages = [...this.selectedImages, ...files];
        this.updateNotificationCount();
        
        if (this.currentMode === 'image') {
            this.updateInputPlaceholder();
        }
    }

    removeImage(index) {
        this.selectedImages.splice(index, 1);
        this.updateNotificationCount();
        
        this.closeDropdown();
        setTimeout(() => this.openDropdown(), 100);
    }

    clearImages() {
        this.selectedImages = [];
        this.updateNotificationCount();
        
        if (this.isDropdownOpen && this.currentMode === 'image') {
            this.closeDropdown();
            setTimeout(() => this.openDropdown(), 100);
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    clearInput() {
        const input = document.getElementById('messageInput');
        if (input) {
            input.value = '';
            input.style.height = 'auto';
            this.updateInputPlaceholder();
            updateScrollButtonPosition();
        }
    }

    getCurrentTime() {
        const now = new Date();
        return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    }

    downloadImage(imageUrl, filename) {
        const link = document.createElement('a');
        link.href = imageUrl;
        link.download = `${filename || 'generated_image'}.png`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    regenerateImage(prompt) {
        const input = document.getElementById('messageInput');
        if (input) {
            input.value = prompt;
            this.switchMode('generate');
            setTimeout(() => this.handleImageGeneration(prompt), 100);
        }
    }

    toggleDropdown() {
        if (this.isDropdownOpen) {
            this.closeDropdown();
        } else {
            this.openDropdown();
        }
    }

    openDropdown() {
        this.closeDropdown();

        const dropdownHTML = `
            <div class="multimodal-dropdown">
                <div class="multimodal-option ${this.currentMode === 'chat' ? 'active' : ''}" data-mode="chat">
                    <div class="option-icon">${this.getSVGIcon('chat')}</div>
                    <div class="option-content">
                        <div class="option-text">Chat</div>
                        <div class="option-description">Normal chat</div>
                    </div>
                </div>
                <div class="multimodal-option ${this.currentMode === 'generate' ? 'active' : ''}" data-mode="generate">
                    <div class="option-icon">${this.getSVGIcon('generate')}</div>
                    <div class="option-content">
                        <div class="option-text">Generate Image</div>
                        <div class="option-description">Create images with AI</div>
                    </div>
                </div>
                <div class="multimodal-option ${this.currentMode === 'image' ? 'active' : ''}" data-mode="image">
                    <div class="option-icon">${this.getSVGIcon('image')}</div>
                    <div class="option-content">
                        <div class="option-text">Upload Image</div>
                        <div class="option-description">Upload + analyze images</div>
                    </div>
                </div>
                
                ${this.currentMode === 'image' ? `
                <div class="image-upload-area">
                    <div class="upload-placeholder">
                        ${this.selectedImages.length > 0 ? `${this.selectedImages.length} image(s) ready!` : 'Upload images for analysis'}
                    </div>
                    <input type="file" id="imageUpload" accept="image/*" multiple style="display: none;">
                    <button class="upload-btn" onclick="window.multimodal.openFilePicker()">
                        ${this.getSVGIcon('upload')}
                        <span>${this.selectedImages.length > 0 ? 'Add More Images' : 'Choose Images'}</span>
                    </button>
                    ${this.selectedImages.length > 0 ? this.renderImagePreviews() : ''}
                </div>
                ` : ''}
            </div>
        `;

        this.toggleBtn.insertAdjacentHTML('afterend', dropdownHTML);
        this.isDropdownOpen = true;

        const dropdown = this.toggleBtn.nextElementSibling;
        dropdown.querySelectorAll('.multimodal-option').forEach(option => {
            option.addEventListener('click', () => {
                const mode = option.dataset.mode;
                this.switchMode(mode);
                this.closeDropdown();
            });
        });

        if (this.currentMode === 'image') {
            const fileInput = document.getElementById('imageUpload');
            fileInput.onchange = (e) => {
                if (e.target.files.length > 0) {
                    this.addImages(Array.from(e.target.files));
                    this.closeDropdown();
                    setTimeout(() => this.openDropdown(), 100);
                }
            };
        }
    }

    renderImagePreviews() {
        if (this.selectedImages.length === 0) return '';
        
        const previews = this.selectedImages.map((image, index) => {
            const previewUrl = URL.createObjectURL(image);
            return `
                <div class="image-preview-container">
                    <img class="image-preview" src="${previewUrl}" alt="Preview ${index + 1}">
                    <button class="remove-image-btn" onclick="window.multimodal.removeImage(${index})" type="button">
                        ${this.getSVGIcon('close')}
                    </button>
                </div>
            `;
        }).join('');

        return `
            <div class="image-previews-header">
                <span>${this.selectedImages.length} image(s) ready</span>
                <button class="clear-all-btn" onclick="window.multimodal.clearImages()" type="button">Clear All</button>
            </div>
            <div class="image-previews-grid">
                ${previews}
            </div>
        `;
    }

    openFilePicker() {
        document.getElementById('imageUpload').click();
    }

    closeDropdown() {
        const dropdown = document.querySelector('.multimodal-dropdown');
        if (dropdown) dropdown.remove();
        this.isDropdownOpen = false;
    }

    switchMode(mode) {
        this.currentMode = mode;
        
        const indicators = { chat: 'C', generate: 'G', image: 'U' };
        this.toggleBtn.querySelector('.toggle-icon').innerHTML = this.getSVGIcon(mode);
        this.modeIndicator.textContent = indicators[mode];
        
        if (mode === 'image' && this.selectedImages.length > 0) {
            this.imageCountBadge.classList.remove('hidden');
        } else if (mode !== 'image') {
            this.imageCountBadge.classList.add('hidden');
        }
        
        this.updateInputPlaceholder();
    }

    updateInputPlaceholder() {
        const input = document.getElementById('messageInput');
        if (!input) return;
        
        const placeholders = {
            chat: 'Type your message... (Enter for newline, Ctrl+Enter to send)',
            generate: 'Describe the image to generate...',
            image: this.selectedImages.length > 0 
                ? `Ask about ${this.selectedImages.length} image(s)...`
                : 'Upload images first...'
        };
        
        input.placeholder = placeholders[this.currentMode];
    }
}

// ==================== MARKDOWN RENDERING ====================
let md = null;

// Try to initialize markdown-it if available
if (typeof markdownit !== 'undefined') {
    md = markdownit({
        html: true,
        breaks: true,
        linkify: true
    });
    console.log("markdown-it initialized");
}

function renderMessageContent(text) {
    // Pre-process: Fix line breaks in markdown images
    text = text.replace(/!\[([^\]]*)\]\s*\n\s*\(([^)]+)\)/g, '![$1]($2)');
    
    // Pre-process: Fix image paths
    text = text.replace(/\(static\//g, '(/static/');
    
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
        
        // Post-process: Fix any remaining image paths
        html = html.replace(/src="static\//g, 'src="/static/');
        
        return html;
    }
    
    // Fallback to MarkdownParser if available
    if (typeof MarkdownParser !== 'undefined') {
        const parser = new MarkdownParser();
        let html = parser.parse(text);
        html = html.replace(/src="static\//g, 'src="/static/');
        return html;
    }
    
    // Basic fallback: escape HTML and convert line breaks
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\n/g, '<br>');
}

// ==================== CODE COPY FUNCTION ====================
function copyCode(button) {
    const codeBlock = button.closest('.code-block');
    if (!codeBlock) return;
    
    const code = codeBlock.querySelector('code');
    if (!code) return;
    
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
    
    // Apply syntax highlighting if hljs is available
    if (typeof hljs !== 'undefined') {
        const codeBlocks = messageDiv.querySelectorAll('pre code');
        codeBlocks.forEach(block => {
            hljs.highlightElement(block);
        });
    }
    
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

// ==================== SENDING MESSAGES ====================
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const message = input.value.trim();
    
    if (!message || isSendingMessage) return;
    
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
        updateScrollButtonPosition();
        
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
        if (data.reply) {
            const aiMessage = createMessageElement('ai', data.reply, new Date().toISOString());
            chatContainer.appendChild(aiMessage);
            
            // Update affection if provided
            if (data.affection !== undefined) {
                updateAffection(data.affection);
            }
            
            scrollToBottom();
        }
        
    } catch (error) {
        console.error('Send message error:', error);
        
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
            if (window.multimodal) {
                window.multimodal.handleSend();
            } else {
                sendMessage();
            }
        }
        // Just Enter creates newline (default behavior)
    });
    
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
        
        // Check if scrolled to top for pagination
        if (chatContainer.scrollTop === 0) {
            loadOlderMessages();
        }
    });
}

function updateScrollButton() {
    const chatContainer = document.getElementById('chatContainer');
    const scrollButton = document.getElementById('scrollToBottom');
    
    if (!chatContainer || !scrollButton) return;
    
    const isNearBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight < 100;
    
    if (isNearBottom) {
        scrollButton.classList.add('hidden');
    } else {
        scrollButton.classList.remove('hidden');
    }
}

function scrollToBottom() {
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
        updateScrollButton();
    }
}

window.scrollToBottom = scrollToBottom;

// ==================== PAGINATION ====================
async function loadOlderMessages() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    
    // Save current scroll position
    const oldScrollHeight = chatContainer.scrollHeight;
    
    try {
        const response = await fetch(`/api/get_history?limit=${MESSAGES_PER_PAGE}&offset=${displayedMessageCount}`);
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.messages && data.messages.length > 0) {
            const fragment = document.createDocumentFragment();
            
            // Reverse to maintain chronological order
            data.messages.reverse().forEach(msg => {
                const msgElement = createMessageElement(
                    msg.role === 'user' ? 'user' : 'ai',
                    msg.content,
                    msg.timestamp
                );
                fragment.appendChild(msgElement);
            });
            
            // Prepend older messages
            chatContainer.insertBefore(fragment, chatContainer.firstChild);
            
            // Restore scroll position
            chatContainer.scrollTop = chatContainer.scrollHeight - oldScrollHeight;
            
            displayedMessageCount += data.messages.length;
        }
    } catch (error) {
        console.error('Error loading older messages:', error);
    }
}

// ==================== CHAT HISTORY ====================
async function loadChatHistory() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;
    
    try {
        const response = await fetch(`/api/get_history?limit=${MESSAGES_PER_PAGE}`);
        if (!response.ok) return;
        
        const data = await response.json();
        
        if (data.messages && data.messages.length > 0) {
            const fragment = document.createDocumentFragment();
            
            data.messages.forEach(msg => {
                const msgElement = createMessageElement(
                    msg.role === 'user' ? 'user' : 'ai',
                    msg.content,
                    msg.timestamp
                );
                fragment.appendChild(msgElement);
            });
            
            chatContainer.appendChild(fragment);
            displayedMessageCount = data.messages.length;
            
            scrollToBottom();
        }
        
        // Update affection if provided
        if (data.affection !== undefined) {
            updateAffection(data.affection);
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

// ==================== UTILITY FUNCTIONS ====================
function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log("Initializing chat unified controller...");
    
    // Initialize multimodal manager
    window.multimodal = new MultimodalManager();
    window.multimodal.init();
    
    // Setup input handlers
    setupInputHandlers();
    
    // Setup scroll detection
    setupScrollDetection();
    
    // Load chat history
    loadChatHistory();
    
    // Update scroll button position initially
    updateScrollButtonPosition();
    
    console.log("Chat unified controller initialized successfully");
});

// Export functions for global access
window.sendMessage = sendMessage;
window.loadChatHistory = loadChatHistory;
window.MultimodalManager = MultimodalManager;
