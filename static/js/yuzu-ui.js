/**
 * YUZU UI - Sidebar & Tool Cards Controller
 * A warm, intimate interface for digital companionship
 */

(function() {
  'use strict';

  // ============================================
  // SIDEBAR CONTROLLER
  // ============================================
  class YuzuSidebar {
    constructor() {
      this.sidebar = document.getElementById('mainSidebar');
      this.hamburger = document.getElementById('hamburgerMenu');
      this.overlay = document.getElementById('sidebarOverlay');
      this.isOpen = false;
      
      this.init();
    }
    
    init() {
      if (!this.sidebar || !this.hamburger) {
        console.warn('[YuzuUI] Sidebar elements not found');
        return;
      }
      
      // Add new classes for styling
      this.sidebar.classList.add('yuzu-sidebar');
      this.hamburger.classList.add('yuzu-hamburger');
      if (this.overlay) {
        this.overlay.classList.add('yuzu-overlay');
      }
      
      // Event listeners
      this.hamburger.addEventListener('click', () => this.toggle());
      if (this.overlay) {
        this.overlay.addEventListener('click', () => this.close());
      }
      
      // Swipe gestures for mobile
      this.initSwipeGestures();
      
      // Close on escape key
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && this.isOpen) {
          this.close();
        }
      });
      
      console.log('[YuzuUI] Sidebar initialized');
    }
    
    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }
    
    open() {
      if (!this.sidebar) return;
      
      this.isOpen = true;
      this.sidebar.classList.add('is-open');
      this.hamburger?.classList.add('is-active');
      this.overlay?.classList.add('is-visible');
      
      // Prevent body scroll
      document.body.style.overflow = 'hidden';
      
      // Load sessions if on chat page
      if (window.location.pathname === '/chat' && typeof loadSidebarSessions === 'function') {
        loadSidebarSessions();
      }
      
      // Announce for screen readers
      this.announceState('Menu opened');
    }
    
    close() {
      if (!this.sidebar) return;
      
      this.isOpen = false;
      this.sidebar.classList.remove('is-open');
      this.hamburger?.classList.remove('is-active');
      this.overlay?.classList.remove('is-visible');
      
      // Restore body scroll
      document.body.style.overflow = '';
      
      // Announce for screen readers
      this.announceState('Menu closed');
    }
    
    initSwipeGestures() {
      let touchStartX = 0;
      let touchStartY = 0;
      let touchEndX = 0;
      
      const minSwipeDistance = 50;
      const maxVerticalDeviation = 100;
      
      // Touch start
      document.addEventListener('touchstart', (e) => {
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
      }, { passive: true });
      
      // Touch end
      document.addEventListener('touchend', (e) => {
        touchEndX = e.changedTouches[0].screenX;
        const touchEndY = e.changedTouches[0].screenY;
        
        const horizontalDistance = touchEndX - touchStartX;
        const verticalDistance = Math.abs(touchEndY - touchStartY);
        
        // Swipe right from edge to open
        if (horizontalDistance > minSwipeDistance && 
            verticalDistance < maxVerticalDeviation &&
            touchStartX < 30 &&
            !this.isOpen) {
          this.open();
        }
        
        // Swipe left to close
        if (horizontalDistance < -minSwipeDistance && 
            verticalDistance < maxVerticalDeviation &&
            this.isOpen) {
          this.close();
        }
      }, { passive: true });
    }
    
    announceState(message) {
      // Create aria-live region if not exists
      let liveRegion = document.getElementById('yuzu-live-region');
      if (!liveRegion) {
        liveRegion = document.createElement('div');
        liveRegion.id = 'yuzu-live-region';
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        liveRegion.style.position = 'absolute';
        liveRegion.style.left = '-10000px';
        document.body.appendChild(liveRegion);
      }
      liveRegion.textContent = message;
    }
  }

  // ============================================
  // TOOL CARDS CONTROLLER
  // ============================================
  class YuzuToolCards {
    constructor() {
      this.cards = new Map();
      this.ws = null;
    }
    
    // Create a new tool card
    createCard(executionId, toolName, icon = '🔧') {
      const card = document.createElement('div');
      card.className = 'yuzu-tool-card';
      card.id = `tool-card-${executionId}`;
      card.innerHTML = `
        <div class="yuzu-tool-card__header">
          <div class="yuzu-tool-card__icon">${icon}</div>
          <h3 class="yuzu-tool-card__title">${this.formatToolName(toolName)}</h3>
          <span class="yuzu-tool-card__status yuzu-tool-card__status--running">Running</span>
        </div>
        <div class="yuzu-tool-card__content">
          <div class="yuzu-tool-card__result">
            <span class="yuzu-pulse">⏳</span> Executing ${this.formatToolName(toolName)}...
          </div>
        </div>
      `;
      
      this.cards.set(executionId, card);
      return card;
    }
    
    // Update card with result
    updateCard(executionId, result, success = true) {
      const card = this.cards.get(executionId);
      if (!card) return;
      
      const statusEl = card.querySelector('.yuzu-tool-card__status');
      const resultEl = card.querySelector('.yuzu-tool-card__result');
      
      if (statusEl) {
        statusEl.className = `yuzu-tool-card__status ${success ? 'yuzu-tool-card__status--success' : 'yuzu-tool-card__status--error'}`;
        statusEl.textContent = success ? 'Complete' : 'Failed';
      }
      
      if (resultEl) {
        resultEl.innerHTML = this.formatResult(result);
      }
      
      // Add animation
      card.classList.add('yuzu-fade-in');
    }
    
    // Format tool name for display
    formatToolName(name) {
      return name
        .replace(/_/g, ' ')
        .replace(/-/g, ' ')
        .split(' ')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
    }
    
    // Format result based on type
    formatResult(result) {
      if (typeof result === 'string') {
        return result;
      }
      if (typeof result === 'object') {
        return `<pre>${JSON.stringify(result, null, 2)}</pre>`;
      }
      return String(result);
    }
    
    // Get icon for tool
    getToolIcon(toolName) {
      const icons = {
        'filesystem': '📁',
        'fetch': '🌐',
        'sqlite': '🗄️',
        'memory': '🧠',
        'git': '🔀',
        'time': '🕐',
        'shell': '⚡',
        'image_generate': '🎨',
        'request': '📡',
        'default': '🔧'
      };
      return icons[toolName] || icons['default'];
    }
  }

  // ============================================
  // CHAT ENHANCEMENTS
  // ============================================
  class YuzuChat {
    constructor() {
      this.container = document.getElementById('chatContainer');
      this.input = document.getElementById('userInput');
      this.sendBtn = document.getElementById('sendBtn');
    }
    
    init() {
      if (!this.container) return;
      
      // Add message animations
      this.observeNewMessages();
    }
    
    observeNewMessages() {
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          mutation.addedNodes.forEach((node) => {
            if (node.classList && node.classList.contains('message')) {
              node.classList.add('yuzu-fade-in');
            }
          });
        });
      });
      
      observer.observe(this.container, { childList: true });
    }
  }

  // ============================================
  // INITIALIZE
  // ============================================
  document.addEventListener('DOMContentLoaded', () => {
    // Initialize sidebar
    window.yuzuSidebar = new YuzuSidebar();
    
    // Initialize tool cards
    window.yuzuToolCards = new YuzuToolCards();
    
    // Initialize chat
    const chat = new YuzuChat();
    chat.init();
    
    console.log('🍊 Yuzu UI initialized');
  });

  // Expose for global access
  window.YuzuSidebar = YuzuSidebar;
  window.YuzuToolCards = YuzuToolCards;
  window.YuzuChat = YuzuChat;
})();
