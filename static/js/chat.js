// [FILE: chat.js] - Minimal Chat Logic
// [VERSION: 2.0.0 - Frontend Reset]
// [DATE: 2026-02-08]

console.log("Loading chat.js...");

// ==================== CORE MESSAGE CREATION ====================

function createMessageElement(role, content) {
    const message = document.createElement("div");
    message.className = `message ${role}`;

    const contentEl = document.createElement("div");
    contentEl.className = "message-content";
    contentEl.innerHTML = renderMessageContent(content);

    message.appendChild(contentEl);
    return message;
}

// ==================== MESSAGE DISPLAY ====================

function addMessage(role, content) {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) {
        console.error("chatContainer not found");
        return;
    }
    
    const msgElement = createMessageElement(role, content);
    chatContainer.appendChild(msgElement);
    scrollToBottom();
}

function scrollToBottom() {
    const chatContainer = document.getElementById("chatContainer");
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

// ==================== CHAT HISTORY LOADING ====================

async function loadChatHistory() {
    const chatContainer = document.getElementById("chatContainer");
    if (!chatContainer) return;
    
    try {
        const res = await fetch("/api/get_profile");
        const data = await res.json();
        const history = data.chat_history || [];
        
        chatContainer.innerHTML = '';
        
        if (history.length > 0) {
            history.forEach(msg => {
                if (msg.role === "user" || msg.role === "assistant") {
                    const msgElement = createMessageElement(
                        msg.role === "user" ? "user" : "ai",
                        msg.content
                    );
                    chatContainer.appendChild(msgElement);
                }
            });
            scrollToBottom();
        } else {
            addMessage("ai", "Hello! I'm your AI companion. Let's start a new conversation!");
        }
    } catch (err) {
        console.error("Failed to load chat history:", err);
        addMessage("ai", "Hello! I'm your AI companion. Let's start a new conversation!");
    }
}

// ==================== MESSAGE SENDING ====================

async function sendMessage() {
    const input = document.getElementById("messageInput");
    const sendBtn = document.getElementById("sendButton");
    
    if (!input || !sendBtn) return;
    
    const message = input.value.trim();
    if (!message) return;
    
    // Disable input
    input.disabled = true;
    sendBtn.disabled = true;
    
    // Add user message
    addMessage("user", message);
    input.value = '';
    
    try {
        const res = await fetch("/api/send_message_stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message })
        });
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let aiResponse = "";
        
        // Create AI message element
        const aiMsg = createMessageElement("ai", "");
        document.getElementById("chatContainer").appendChild(aiMsg);
        const contentEl = aiMsg.querySelector(".message-content");
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        if (data.chunk) {
                            aiResponse += data.chunk;
                            contentEl.innerHTML = renderMessageContent(aiResponse);
                            scrollToBottom();
                        }
                    } catch (e) {
                        // Ignore parse errors
                    }
                }
            }
        }
    } catch (err) {
        console.error("Failed to send message:", err);
        addMessage("ai", "Sorry, I encountered an error. Please try again.");
    } finally {
        // Re-enable input
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
}

// ==================== EVENT LISTENERS ====================

document.addEventListener("DOMContentLoaded", function() {
    console.log("DOM loaded, initializing chat...");
    
    // Load chat history
    loadChatHistory();
    
    // Setup send button
    const sendBtn = document.getElementById("sendButton");
    if (sendBtn) {
        sendBtn.addEventListener("click", sendMessage);
    }
    
    // Setup enter key
    const input = document.getElementById("messageInput");
    if (input) {
        input.addEventListener("keypress", function(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});

console.log("chat.js loaded");
