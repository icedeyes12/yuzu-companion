// [FILE: mobile-enhancements.js]
// [VERSION: 1.0.0]
// [DATE: 2026-03-13]
// [PROJECT: HKKM - Yuzu Companion]
// [DESCRIPTION: Mobile-specific enhancements and gesture support]
// [AUTHOR: Project Lead: Bani Baskara]

(function() {
  'use strict';

  // ==================== MOBILE DETECTION ====================
  const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  const isTouch = window.matchMedia('(pointer: coarse)').matches;

  // ==================== KEYBOARD HANDLING ====================
  class KeyboardManager {
    constructor() {
      this.viewportHeight = window.innerHeight;
      this.isKeyboardOpen = false;
      this.onKeyboardChange = null;
    }

    init() {
      if (!isMobile) return;

      // iOS keyboard detection
      if (/iPhone|iPad|iPod/i.test(navigator.userAgent)) {
        window.addEventListener('focusin', (e) => {
          if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') {
            this.isKeyboardOpen = true;
            document.body.classList.add('keyboard-open');
            this.scrollToInput(e.target);
          }
        });

        window.addEventListener('focusout', () => {
          this.isKeyboardOpen = false;
          document.body.classList.remove('keyboard-open');
        });
      }

      // Android keyboard detection via viewport resize
      let resizeTimer;
      window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
          const newHeight = window.innerHeight;
          const heightDiff = this.viewportHeight - newHeight;
          
          if (heightDiff > 150) {
            this.isKeyboardOpen = true;
            document.body.classList.add('keyboard-open');
          } else if (heightDiff < -50) {
            this.isKeyboardOpen = false;
            document.body.classList.remove('keyboard-open');
          }
          
          this.viewportHeight = newHeight;
        }, 100);
      });
    }

    scrollToInput(input) {
      setTimeout(() => {
        const rect = input.getBoundingClientRect();
        const scrollContainer = document.getElementById('chatContainer');
        if (scrollContainer) {
          const scrollTop = rect.top + scrollContainer.scrollTop - window.innerHeight + rect.height + 20;
          scrollContainer.scrollTo({ top: scrollTop, behavior: 'smooth' });
        }
      }, 300);
    }
  }

  // ==================== GESTURE SUPPORT ====================
  class GestureManager {
    constructor() {
      this.touchStartX = 0;
      this.touchStartY = 0;
      this.touchEndX = 0;
      this.minSwipeDistance = 50;
      this.maxVerticalDeviation = 100;
    }

    init() {
      if (!isTouch) return;

      const chatContainer = document.getElementById('chatContainer');
      const sidebar = document.getElementById('mainSidebar');
      
      if (!chatContainer) return;

      // Touch start
      chatContainer.addEventListener('touchstart', (e) => {
        this.touchStartX = e.changedTouches[0].screenX;
        this.touchStartY = e.changedTouches[0].screenY;
      }, { passive: true });

      // Touch end
      chatContainer.addEventListener('touchend', (e) => {
        this.touchEndX = e.changedTouches[0].screenX;
        const touchEndY = e.changedTouches[0].screenY;
        
        const horizontalDistance = this.touchEndX - this.touchStartX;
        const verticalDistance = Math.abs(touchEndY - this.touchStartY);
        
        // Swipe right from edge to open sidebar
        if (horizontalDistance > this.minSwipeDistance && 
            verticalDistance < this.maxVerticalDeviation &&
            this.touchStartX < 50) {
          if (sidebar && !sidebar.classList.contains('open')) {
            if (typeof toggleSidebar === 'function') toggleSidebar();
          }
        }
        
        // Swipe left to close sidebar
        if (horizontalDistance < -this.minSwipeDistance && 
            verticalDistance < this.maxVerticalDeviation &&
            sidebar && sidebar.classList.contains('open')) {
          if (typeof toggleSidebar === 'function') toggleSidebar();
        }
      }, { passive: true });

      // Prevent horizontal scroll when sidebar is open
      if (sidebar) {
        sidebar.addEventListener('touchmove', (e) => {
          if (sidebar.classList.contains('open')) {
            e.stopPropagation();
          }
        }, { passive: true });
      }
    }
  }

  // ==================== PASTE IMAGE SUPPORT ====================
  class PasteImageManager {
    constructor() {
      this.onImagePasted = null;
    }

    init() {
      document.addEventListener('paste', (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;

        let hasImage = false;
        
        for (const item of items) {
          if (item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
              hasImage = true;
              this.handlePastedImage(file);
            }
          }
        }

        if (hasImage) {
          e.preventDefault();
        }
      });
    }

    handlePastedImage(file) {
      // Switch to image mode if multimodal manager exists
      if (window.multimodal) {
        window.multimodal.switchMode('image');
        window.multimodal.addImages([file]);
        window.multimodal.updateNotificationCount();
        
        // Show visual feedback
        this.showPasteFeedback();
        
        // Focus input
        const input = document.getElementById('messageInput');
        if (input) input.focus();
      }
    }

    showPasteFeedback() {
      const feedback = document.createElement('div');
      feedback.className = 'paste-feedback';
      feedback.textContent = '📎 Image pasted!';
      feedback.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--accent-pink);
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 20px;
        font-size: 0.9rem;
        z-index: 10000;
        animation: fadeInUp 0.3s ease;
      `;
      
      document.body.appendChild(feedback);
      
      setTimeout(() => {
        feedback.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => feedback.remove(), 300);
      }, 2000);
    }
  }

  // ==================== DOUBLE-TAP PREVENTION ====================
  class DoubleTapPreventer {
    init() {
      let lastTouchEnd = 0;
      
      document.addEventListener('touchend', (e) => {
        const now = Date.now();
        if (now - lastTouchEnd <= 300) {
          e.preventDefault();
        }
        lastTouchEnd = now;
      }, { passive: false });
    }
  }

  // ==================== PULL-TO-REFRESH PREVENTION ====================
  class PullToRefreshPreventer {
    init() {
      let startY = 0;
      
      document.addEventListener('touchstart', (e) => {
        startY = e.touches[0].pageY;
      }, { passive: true });
      
      document.addEventListener('touchmove', (e) => {
        const y = e.touches[0].pageY;
        const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
        
        // Prevent pull-to-refresh when at top of page
        if (scrollTop === 0 && y > startY) {
          e.preventDefault();
        }
      }, { passive: false });
    }
  }

  // ==================== THEME PERSISTENCE ====================
  class ThemePersistence {
    init() {
      // Load saved theme
      const savedTheme = localStorage.getItem('yuzu-theme');
      if (savedTheme) {
        document.body.setAttribute('data-theme', savedTheme);
        this.updateThemeDropdown(savedTheme);
      }

      // Listen for theme changes
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.attributeName === 'data-theme') {
            const theme = document.body.getAttribute('data-theme');
            if (theme) {
              localStorage.setItem('yuzu-theme', theme);
            }
          }
        });
      });

      observer.observe(document.body, { attributes: true });
    }

    updateThemeDropdown(theme) {
      const dropdown = document.getElementById('themeDropdown');
      if (!dropdown) return;
      
      const option = dropdown.querySelector(`[data-value="${theme}"]`);
      if (option) {
        const selectedText = dropdown.querySelector('.selected-text');
        if (selectedText) {
          selectedText.textContent = option.textContent.trim();
        }
      }
    }
  }

  // ==================== ONLINE/OFFLINE DETECTION ====================
  class ConnectionManager {
    init() {
      const updateStatus = () => {
        if (navigator.onLine) {
          document.body.classList.remove('offline');
        } else {
          document.body.classList.add('offline');
          this.showOfflineBanner();
        }
      };

      window.addEventListener('online', updateStatus);
      window.addEventListener('offline', updateStatus);
      
      // Initial check
      updateStatus();
    }

    showOfflineBanner() {
      let banner = document.getElementById('offline-banner');
      
      if (!banner) {
        banner = document.createElement('div');
        banner.id = 'offline-banner';
        banner.style.cssText = `
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          background: #ff6b6b;
          color: white;
          text-align: center;
          padding: 0.5rem;
          font-size: 0.85rem;
          z-index: 100000;
          transform: translateY(-100%);
          transition: transform 0.3s ease;
        `;
        banner.textContent = '⚠️ You are offline. Some features may not work.';
        document.body.appendChild(banner);
      }
      
      setTimeout(() => {
        banner.style.transform = 'translateY(0)';
      }, 100);
    }
  }

  // ==================== INITIALIZE ====================
  function init() {
    // Only run on mobile/touch devices
    if (!isMobile && !isTouch) return;

    // Initialize managers
    new KeyboardManager().init();
    new GestureManager().init();
    new PasteImageManager().init();
    new DoubleTapPreventer().init();
    new ThemePersistence().init();
    new ConnectionManager().init();

    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
      @keyframes fadeInUp {
        from { opacity: 0; transform: translate(-50%, 20px); }
        to { opacity: 1; transform: translate(-50%, 0); }
      }
      @keyframes fadeOut {
        from { opacity: 1; }
        to { opacity: 0; }
      }
    `;
    document.head.appendChild(style);

    console.log('📱 Mobile enhancements loaded');
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for debugging
  window.YuzuMobile = {
    isMobile,
    isTouch,
    init
  };

})();
