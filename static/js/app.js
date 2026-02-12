// app.js - Core application utilities and API helpers

/**
 * API helper functions
 */
const API = {
    /**
     * Generic fetch wrapper with error handling
     */
    async fetch(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API fetch error:', error);
            throw error;
        }
    },

    /**
     * GET request helper
     */
    async get(url) {
        return this.fetch(url, { method: 'GET' });
    },

    /**
     * POST request helper
     */
    async post(url, data) {
        return this.fetch(url, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    /**
     * PUT request helper
     */
    async put(url, data) {
        return this.fetch(url, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    },

    /**
     * DELETE request helper
     */
    async delete(url) {
        return this.fetch(url, { method: 'DELETE' });
    }
};

/**
 * Utility functions
 */
const Utils = {
    /**
     * Debounce function execution
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Format date to readable string
     */
    formatDate(date) {
        const d = new Date(date);
        return d.toLocaleString();
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Show notification/toast message
     */
    showNotification(message, type = 'info') {
        // Simple console log for now, can be enhanced with toast library
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
};

/**
 * Initialize app on DOM load
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Yuzu Companion app initialized');
});

// Export for use in other modules
window.API = API;
window.Utils = Utils;
