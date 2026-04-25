// FILE: static/js/agentic-stream.js
// DESCRIPTION: SSE handler for agentic loop
//              Parses structured events from backend

class AgenticStreamHandler {
    constructor(options = {}) {
        this.onThought = options.onThought || (() => {});
        this.onCommand = options.onCommand || (() => {});
        this.onToolResult = options.onToolResult || (() => {});
        this.onText = options.onText || (() => {});
        this.onDone = options.onDone || (() => {});
        this.onTimeout = options.onTimeout || (() => {});
        this.onError = options.onError || (() => {});
        
        this.abortController = null;
        this.isStreaming = false;
    }
    
    async stream(message, sessionId) {
        if (this.isStreaming) {
            console.warn('[agentic] Already streaming, aborting previous');
            this.abort();
        }
        
        this.isStreaming = true;
        this.abortController = new AbortController();
        
        try {
            const response = await fetch('/api/agentic/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    stream: true,
                }),
                signal: this.abortController.signal,
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const events = this._parseSSE(buffer);
                buffer = events.remaining;
                
                for (const event of events.parsed) {
                    this._handleEvent(event);
                }
            }
            
            // Process any remaining buffer
            if (buffer.trim()) {
                const events = this._parseSSE(buffer);
                for (const event of events.parsed) {
                    this._handleEvent(event);
                }
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log('[agentic] Stream aborted');
            } else {
                console.error('[agentic] Stream error:', error);
                this.onError(error);
            }
        } finally {
            this.isStreaming = false;
            this.abortController = null;
        }
    }
    
    abort() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        this.isStreaming = false;
    }
    
    _parseSSE(buffer) {
        const parsed = [];
        const lines = buffer.split('\n');
        let remaining = '';
        let currentEvent = null;
        
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            
            if (line.startsWith('event: ')) {
                if (currentEvent) {
                    parsed.push(currentEvent);
                }
                currentEvent = { type: line.slice(7).trim(), data: null };
            } else if (line.startsWith('data: ') && currentEvent) {
                try {
                    currentEvent.data = JSON.parse(line.slice(6));
                } catch (e) {
                    console.warn('[agentic] Failed to parse data:', line);
                    currentEvent.data = line.slice(6);
                }
            } else if (line === '' && currentEvent) {
                // Empty line signals end of event
                parsed.push(currentEvent);
                currentEvent = null;
            } else if (i === lines.length - 1 && line.trim()) {
                // Last line incomplete, keep for next chunk
                remaining = line;
            }
        }
        
        if (currentEvent) {
            parsed.push(currentEvent);
        }
        
        return { parsed, remaining };
    }
    
    _handleEvent(event) {
        if (!event.data) return
        
        try {
            const data = JSON.parse(event.data)
            
            // Update brainBox status
            if (window.brainBox) {
                switch (data.type) {
                    case 'thought':
                        window.brainBox.setStatus('thinking', data.thought || '')
                        break
                    case 'tool_start':
                        window.brainBox.setCurrentTool(data.tool)
                        window.brainBox.setIteration(data.iteration || 0)
                        if (window.activityFeed) {
                            this._currentActivityId = window.activityFeed.addItem(data.tool, 'running', data.args)
                        }
                        break
                    case 'tool_result':
                        if (window.activityFeed && this._currentActivityId) {
                            window.activityFeed.updateItem(this._currentActivityId, data.ok ? 'done' : 'error', data)
                        }
                        break
                    case 'iteration':
                        window.brainBox.setIteration(data.iteration)
                        break
                    case 'done':
                        window.brainBox.setStatus('done', `${data.tool_calls || 0} tools, ${data.elapsed || 0}s`)
                        if (window.activityFeed) {
                            window.activityFeed.clear()
                        }
                        break
                    case 'error':
                        window.brainBox.setStatus('error', data.error)
                        break
                }
            }
            
            // Call original handler
            this._originalHandleEvent(event)
            
        } catch (err) {
            console.error('[AgenticStream] Parse error:', err)
        }
    }
    
    _originalHandleEvent(event) {
        if (!event.data) return
        
        try {
            const data = JSON.parse(event.data)
            
            // Handle existing event types...
            switch (data.type) {
                case 'thought':
                case 'tool_start':
                case 'tool_result':
                case 'iteration':
                case 'text':
                    if (data.chunk) {
                        this.buffer += data.chunk
                        this.callbacks.onChunk(data.chunk)
                    }
                    break
                case 'done':
                    this.callbacks.onComplete(this.buffer, data)
                    break
                case 'error':
                    this.callbacks.onError(data.error)
                    break
            }
            
        } catch (err) {
            console.error('[AgenticStream] Parse error:', err)
        }
    }
    }

// Global instance for chat.js integration
window.agenticStream = new AgenticStreamHandler({
    onThought: (data) => {
        // Display thought in Brain Box
        if (window.addBrainBox) {
            window.addBrainBox(data.content, data.planning, data.tools);
        }
    },
    onCommand: (data) => {
        // Show tool execution indicator
        if (window.showToolExecution) {
            window.showToolExecution(data.tool, data.args, data.iteration);
        }
    },
    onToolResult: (data) => {
        // Display tool result
        if (window.showToolResult) {
            window.showToolResult(data.ok, data.output);
        }
    },
    onText: (data) => {
        // Stream text to message
        if (window.streamToMessage) {
            window.streamToMessage(data.chunk);
        }
    },
    onDone: (data) => {
        // Finalize streaming
        if (window.finalizeStreaming) {
            window.finalizeStreaming(data.iterations, data.elapsed, data.tools_used);
        }
    },
    onTimeout: (data) => {
        console.warn('[agentic] Timeout after', data.elapsed, 's');
        if (window.showTimeout) {
            window.showTimeout(data.elapsed);
        }
    },
    onError: (error) => {
        console.error('[agentic] Error:', error);
        if (window.showError) {
            window.showError(error.message);
        }
    },
});

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AgenticStreamHandler };
}