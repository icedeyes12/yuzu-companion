// [FILE: utils.js]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Shared utility functions]

/**
 * Copy code to clipboard with fallback
 */
function copyCodeToClipboard(button) {
    if (!button) return;
    
    try {
        const codeContainer = button.closest('.code-block-container');
        const codeElement = codeContainer.querySelector('code');
        if (!codeElement) return;

        const codeText = codeElement.textContent || codeElement.innerText;
        const copyText = button.querySelector('.copy-text');

        navigator.clipboard.writeText(codeText).then(() => {
            const originalText = copyText.textContent;
            copyText.textContent = 'Copied!';
            button.classList.add('copied');
            
            setTimeout(() => {
                copyText.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            // Fallback for browsers without clipboard API
            const textArea = document.createElement('textarea');
            textArea.value = codeText;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            
            const originalText = copyText.textContent;
            copyText.textContent = 'Copied!';
            button.classList.add('copied');
            
            setTimeout(() => {
                copyText.textContent = originalText;
                button.classList.remove('copied');
            }, 2000);
        });
    } catch (error) {
        console.error('Copy failed:', error);
    }
}

/**
 * Show notification toast
 */
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.config-notification, .notification');
    existingNotifications.forEach(notification => notification.remove());
    
    const notification = document.createElement('div');
    notification.className = `config-notification ${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-icon">${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 100px;
        right: 20px;
        background: ${type === 'success' ? 'var(--accent-mint)' : type === 'error' ? 'var(--accent-pink)' : 'var(--accent-lavender)'};
        color: var(--button-text);
        padding: 1rem;
        border-radius: 8px;
        box-shadow: var(--shadow-soft);
        z-index: 10000;
        max-width: 300px;
        animation: slideInRight 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOutRight 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export for ES6 modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { copyCodeToClipboard, showNotification, escapeHtml };
}
