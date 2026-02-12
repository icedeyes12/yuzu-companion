// app.js - Core application utilities

// Theme management
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}

// Auto-resize textarea
function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
}

// Show notification
function showNotification(message, type = 'info') {
  console.log(`[${type}] ${message}`);
  // Could add toast notifications here
}

// API helper
async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(endpoint, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
}

// Initialize theme on load
document.addEventListener('DOMContentLoaded', initTheme);

window.setTheme = setTheme;
window.autoResizeTextarea = autoResizeTextarea;
window.showNotification = showNotification;
window.apiCall = apiCall;
