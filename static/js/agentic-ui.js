// FILE: static/js/agentic-ui.js
// DESCRIPTION: Agentic Loop UI components — Brain Box, Activity Feed, Execution History
//              Reusable components for multi-turn tool execution visualization

/**
 * BrainBox — Floating execution status indicator
 * Shows current agentic iteration, tool being executed, and elapsed time
 */
class BrainBox {
  constructor() {
    this.isVisible = false
    this.startTime = null
    this.iteration = 0
    this.currentTool = null
    this.status = 'idle' // idle | thinking | executing | done | error
    this.element = null
    this._interval = null
  }

  init() {
    if (this.element) return
    this.element = document.createElement('div')
    this.element.className = 'brain-box hidden'
    this.element.innerHTML = `
      <div class="brain-box-inner">
        <div class="brain-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <path d="M12 6v6l4 2"/>
          </svg>
        </div>
        <div class="brain-status">
          <div class="brain-status-text">Idle</div>
          <div class="brain-status-detail"></div>
        </div>
        <div class="brain-stats">
          <div class="brain-stat">
            <span class="stat-label">Iter</span>
            <span class="stat-value" id="brainIteration">0</span>
          </div>
          <div class="brain-stat">
            <span class="stat-label">Time</span>
            <span class="stat-value" id="brainTime">0.0s</span>
          </div>
        </div>
        <button class="brain-stop-btn" onclick="brainBox.stop()">Stop</button>
      </div>
    `
    document.body.appendChild(this.element)
  }

  show() {
    this.init()
    this.isVisible = true
    this.startTime = Date.now()
    this.element.classList.remove('hidden')
    this._interval = setInterval(() => this._updateTime(), 100)
  }

  hide() {
    this.isVisible = false
    if (this._interval) clearInterval(this._interval)
    if (this.element) this.element.classList.add('hidden')
  }

  setStatus(status, detail = '') {
    this.status = status
    const statusText = this.element.querySelector('.brain-status-text')
    const statusDetail = this.element.querySelector('.brain-status-detail')
    
    const labels = {
      idle: 'Idle',
      thinking: 'Thinking...',
      executing: 'Executing',
      done: 'Done',
      error: 'Error'
    }
    
    statusText.textContent = labels[status] || status
    statusDetail.textContent = detail
    this.element.className = `brain-box ${status}`
    
    if (status === 'done' || status === 'error') {
      setTimeout(() => this.hide(), 2000)
    }
  }

  setIteration(n) {
    this.iteration = n
    document.getElementById('brainIteration').textContent = n
  }

  setCurrentTool(tool) {
    this.currentTool = tool
    this.setStatus('executing', tool)
  }

  stop() {
    this.setStatus('done', 'Stopped by user')
    if (window.agenticHandler) {
      window.agenticHandler.abort()
    }
  }

  _updateTime() {
    if (!this.startTime) return
    const elapsed = (Date.now() - this.startTime) / 1000
    document.getElementById('brainTime').textContent = elapsed.toFixed(1) + 's'
  }
}

/**
 * ActivityFeed — Timeline of tool executions in current turn
 * Shows each tool call with status, arguments, and result preview
 */
class ActivityFeed {
  constructor() {
    this.items = []
    this.element = null
    this.isExpanded = true
  }

  init() {
    if (this.element) return
    this.element = document.createElement('div')
    this.element.className = 'activity-feed'
    this.element.innerHTML = `
      <div class="activity-header" onclick="activityFeed.toggle()">
        <span class="activity-title">Execution Timeline</span>
        <span class="activity-count" id="activityCount">0</span>
        <span class="activity-toggle">▼</span>
      </div>
      <div class="activity-items" id="activityItems"></div>
    `
    
    // Insert after chat container
    const chatContainer = document.getElementById('chatContainer')
    if (chatContainer) {
      chatContainer.parentNode.insertBefore(this.element, chatContainer.nextSibling)
    }
  }

  addItem(toolName, status, args = {}) {
    this.init()
    
    const item = {
      id: Date.now(),
      toolName,
      status, // pending | running | done | error
      args,
      result: null,
      timestamp: new Date()
    }
    
    this.items.push(item)
    this._renderItem(item)
    this._updateCount()
    
    return item.id
  }

  updateItem(id, status, result = null) {
    const item = this.items.find(i => i.id === id)
    if (!item) return
    
    item.status = status
    item.result = result
    
    const el = document.getElementById(`activity-${id}`)
    if (el) {
      el.className = `activity-item ${status}`
      const statusEl = el.querySelector('.activity-item-status')
      if (statusEl) {
        statusEl.textContent = status === 'done' ? '✓' : status === 'error' ? '✗' : '...'
      }
      
      if (result && result.markdown) {
        const preview = el.querySelector('.activity-result-preview')
        const text = result.markdown.replace(/<[^>]*>/g, '').slice(0, 100)
        preview.textContent = text + (result.markdown.length > 100 ? '...' : '')
      }
    }
  }

  clear() {
    this.items = []
    const itemsEl = document.getElementById('activityItems')
    if (itemsEl) itemsEl.innerHTML = ''
    this._updateCount()
  }

  toggle() {
    this.isExpanded = !this.isExpanded
    const itemsEl = document.getElementById('activityItems')
    const toggleEl = this.element.querySelector('.activity-toggle')
    
    if (this.isExpanded) {
      itemsEl.classList.remove('hidden')
      toggleEl.textContent = '▼'
    } else {
      itemsEl.classList.add('hidden')
      toggleEl.textContent = '▶'
    }
  }

  _renderItem(item) {
    const itemsEl = document.getElementById('activityItems')
    if (!itemsEl) return
    
    const el = document.createElement('div')
    el.id = `activity-${item.id}`
    el.className = `activity-item ${item.status}`
    el.innerHTML = `
      <div class="activity-item-header">
        <span class="activity-item-icon">🔧</span>
        <span class="activity-item-name">${item.toolName}</span>
        <span class="activity-item-status">...</span>
      </div>
      <div class="activity-item-args">${JSON.stringify(item.args, null, 2)}</div>
      <div class="activity-result-preview"></div>
    `
    
    itemsEl.appendChild(el)
  }

  _updateCount() {
    const countEl = document.getElementById('activityCount')
    if (countEl) countEl.textContent = this.items.length
  }
}

/**
 * ExecutionHistory — Toggle panel to show/hide past tool executions
 * Stores across-turn tool execution history for context
 */
class ExecutionHistory {
  constructor() {
    this.history = [] // [{ turn, tools: [...] }]
    this.isVisible = false
    this.element = null
  }

  init() {
    if (this.element) return
    this.element = document.createElement('div')
    this.element.className = 'execution-history hidden'
    this.element.innerHTML = `
      <div class="history-header">
        <span class="history-title">Execution History</span>
        <button class="history-close" onclick="executionHistory.hide()">×</button>
      </div>
      <div class="history-content" id="historyContent"></div>
    `
    document.body.appendChild(this.element)
  }

  show() {
    this.init()
    this.isVisible = true
    this.element.classList.remove('hidden')
    this._render()
  }

  hide() {
    this.isVisible = false
    if (this.element) this.element.classList.add('hidden')
  }

  addTurn(turnId, tools) {
    this.history.push({
      turn: turnId,
      timestamp: new Date(),
      tools
    })
    
    // Keep last 10 turns
    if (this.history.length > 10) {
      this.history.shift()
    }
    
    if (this.isVisible) this._render()
  }

  clear() {
    this.history = []
    if (this.isVisible) this._render()
  }

  _render() {
    const content = document.getElementById('historyContent')
    if (!content) return
    
    if (this.history.length === 0) {
      content.innerHTML = '<div class="history-empty">No execution history yet</div>'
      return
    }
    
    content.innerHTML = this.history.map(turn => `
      <div class="history-turn">
        <div class="history-turn-header">
          <span class="turn-time">${turn.timestamp.toLocaleTimeString()}</span>
          <span class="turn-tools">${turn.tools.length} tools</span>
        </div>
        <div class="history-turn-tools">
          ${turn.tools.map(t => `
            <div class="history-tool ${t.status}">
              <span class="tool-name">${t.name}</span>
              <span class="tool-status">${t.status}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('')
  }
}

// Singleton instances
const brainBox = new BrainBox()
const activityFeed = new ActivityFeed()
const executionHistory = new ExecutionHistory()

// Global exports for onclick handlers
window.brainBox = brainBox
window.activityFeed = activityFeed
window.executionHistory = executionHistory

// CSS injection for minimal styles if not loaded
if (!document.querySelector('link[href*="agentic.css"]')) {
  const style = document.createElement('style')
  style.textContent = `
    .brain-box { position: fixed; top: 80px; right: 20px; z-index: 1000; }
    .activity-feed { position: fixed; bottom: 80px; left: 20px; right: 20px; z-index: 999; }
    .execution-history { position: fixed; right: 20px; top: 140px; width: 300px; z-index: 1001; }
  `
  document.head.appendChild(style)
}

// Toggle functions
function toggleBrainBox() {
  if (brainBox.isVisible) {
    brainBox.hide()
  } else {
    brainBox.show()
  }
}

function toggleActivityFeed() {
  activityFeed.toggle()
}

function toggleExecutionHistory() {
  if (executionHistory.isVisible) {
    executionHistory.hide()
  } else {
    executionHistory.show()
  }
}

// Agentic Mode Toggle - Backend integration
let agenticModeEnabled = false

async function initAgenticMode() {
  // Load state from backend
  try {
    const resp = await fetch('/api/agentic/status')
    const data = await resp.json()
    agenticModeEnabled = data.agentic_mode || false
    updateAgenticModeUI()
  } catch (e) {
    // Default to off
    agenticModeEnabled = false
    updateAgenticModeUI()
  }
}

async function toggleAgenticMode(enabled) {
  try {
    const resp = await fetch('/api/agentic/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    })
    
    const data = await resp.json()
    
    if (data.status === 'success') {
      agenticModeEnabled = enabled
      updateAgenticModeUI()
      console.log('[Agentic] Mode:', enabled ? 'enabled' : 'disabled')
    }
  } catch (e) {
    console.error('[Agentic] Toggle failed:', e)
  }
}

function updateAgenticModeUI() {
  const toggle = document.getElementById('agenticModeToggle')
  const label = document.getElementById('agenticModeLabel')
  const info = document.getElementById('agenticModeInfo')
  
  if (toggle) toggle.checked = agenticModeEnabled
  if (label) label.textContent = agenticModeEnabled ? 'ON' : 'OFF'
  if (info) info.textContent = agenticModeEnabled ? '56 MCP tools + local' : 'Local RPC tools'
  
  // Show/hide brain box based on mode
  if (agenticModeEnabled) {
    brainBox.init()
  }
}

// Export for global access
window.initAgenticMode = initAgenticMode
window.toggleAgenticMode = toggleAgenticMode
window.agenticModeEnabled = () => agenticModeEnabled

// Initialize on load
document.addEventListener('DOMContentLoaded', initAgenticMode)
