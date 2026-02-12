// sidebar.js - Sidebar Logic

// Toggle sidebar
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    
    if (sidebar && overlay) {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('active');
    }
}

// Change theme
function changeTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
}

// Load saved theme
function loadSavedTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    const themeSelect = document.getElementById('themeSelect');
    if (themeSelect) {
        themeSelect.value = savedTheme;
    }
}

// Load sessions
async function loadSessions() {
    try {
        const data = await apiCall('/api/get_sessions');
        const sessionsList = document.getElementById('sessionsList');
        
        if (!sessionsList) return;
        
        if (data && data.sessions && data.sessions.length > 0) {
            sessionsList.innerHTML = '';
            
            data.sessions.forEach(session => {
                const sessionItem = document.createElement('div');
                sessionItem.className = 'session-item' + (session.is_active ? ' active' : '');
                sessionItem.onclick = () => switchSession(session.id);
                
                sessionItem.innerHTML = `
                    <div class="session-name">Session ${session.id}</div>
                    <div class="session-preview">${session.preview || 'No messages yet'}</div>
                `;
                
                sessionsList.appendChild(sessionItem);
            });
        } else {
            sessionsList.innerHTML = '<div style="padding: 0.5rem; color: var(--text-secondary);">No sessions</div>';
        }
    } catch (error) {
        console.error('Failed to load sessions:', error);
        const sessionsList = document.getElementById('sessionsList');
        if (sessionsList) {
            sessionsList.innerHTML = '<div style="padding: 0.5rem; color: var(--text-secondary);">Failed to load</div>';
        }
    }
}

// Create new session
async function createNewSession() {
    try {
        const data = await apiCall('/api/create_session', {
            method: 'POST'
        });
        
        if (data && data.session_id) {
            showNotification('New session created', 'success');
            await loadSessions();
            window.location.reload();
        }
    } catch (error) {
        console.error('Failed to create session:', error);
        showNotification('Failed to create session', 'error');
    }
}

// Switch session
async function switchSession(sessionId) {
    try {
        await apiCall('/api/switch_session', {
            method: 'POST',
            body: JSON.stringify({ session_id: sessionId })
        });
        
        showNotification('Session switched', 'success');
        window.location.reload();
    } catch (error) {
        console.error('Failed to switch session:', error);
        showNotification('Failed to switch session', 'error');
    }
}

// Initialize sidebar on load
document.addEventListener('DOMContentLoaded', () => {
    loadSavedTheme();
    
    // Only load sessions if we're on the chat page
    if (document.getElementById('sessionsList')) {
        loadSessions();
    }
});

// Export functions
window.toggleSidebar = toggleSidebar;
window.changeTheme = changeTheme;
window.createNewSession = createNewSession;
window.switchSession = switchSession;
