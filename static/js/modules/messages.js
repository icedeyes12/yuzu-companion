// FILE: static/js/modules/messages.js
// DESCRIPTION: Message creation, rendering, and formatting utilities

import { findMessageById } from "./state.js";

/**
 * Create a message element with proper structure.
 * @param {string} role - 'user', 'ai', 'tool', or '*_tools'
 * @param {string} content - Message content
 * @param {string|null} timestamp - Optional timestamp
 * @param {object|null} meta - Optional metadata: { tool_calls, tool_call_id }
 * @returns {HTMLElement|null} The message element (null if role is unrenderable)
 */
export function createMessageElement(
	role,
	content,
	timestamp = null,
	meta = null,
) {
	if (!isRenderableHistoryRole(role)) return null;

	const msg = document.createElement("div");
	msg.className = `message ${role === "assistant" ? "ai" : role}`;

	const isUserMessage = role === "user";
	const isToolMessage =
		role === "tool" || (typeof role === "string" && role.endsWith("_tools"));
	const displayTime = timestamp
		? formatTimestamp(timestamp)
		: getCurrentTime24h();
	const safeContent = String(content ?? "");
	const toolCalls = Array.isArray(meta?.tool_calls) ? meta.tool_calls : [];
	const toolCallId = meta?.tool_call_id || meta?.toolCallId || "";

	if (isUserMessage) {
		const bubble = document.createElement("div");
		bubble.className = "message-bubble";

		const contentContainer = document.createElement("div");
		contentContainer.className = "message-content";

		if (typeof renderer !== "undefined") {
			contentContainer.innerHTML = renderMessageContent(safeContent, true);
			setTimeout(() => {
				if (typeof hljs !== "undefined") {
					const codeBlocks = contentContainer.querySelectorAll("pre code");
					codeBlocks.forEach((block) => {
						if (!block.classList.contains("hljs")) {
							hljs.highlightElement(block);
						}
					});
				}
			}, 0);
		} else {
			contentContainer.textContent = safeContent;
		}

		bubble.appendChild(contentContainer);
		msg.appendChild(bubble);
	} else if (isToolMessage) {
		const contentContainer = document.createElement("div");
		contentContainer.className = "message-content tool-message-content";

		if (
			typeof renderer !== "undefined" &&
			typeof renderer.renderNativeToolCalls === "function" &&
			toolCalls.length > 0
		) {
			contentContainer.innerHTML = renderer.renderNativeToolCalls(toolCalls);
		} else if (
			typeof renderer !== "undefined" &&
			typeof renderer.renderNativeToolResultBlock === "function" &&
			toolCallId
		) {
			contentContainer.innerHTML = renderer.renderNativeToolResultBlock({
				content: safeContent,
				tool_call_id: toolCallId,
			});
		} else if (typeof renderer !== "undefined") {
			contentContainer.innerHTML = renderMessageContent(safeContent, false);
		} else {
			contentContainer.textContent = safeContent;
		}

		msg.appendChild(contentContainer);
	} else {
		const contentContainer = document.createElement("div");
		contentContainer.className = "message-content";

		if (typeof renderer !== "undefined") {
			// Native tool calling: assistant row may contain only tool_calls
			// (no synthesis text). Render the native tool call block inline
			// so the bubble isn't empty. Also render any grouped tool_results
			// (from history grouping) before the synthesis prose.
			let html = "";
			if (toolCalls.length > 0) {
				html += renderer.renderNativeToolCalls?.(toolCalls) || "";
			}
			if (Array.isArray(meta?.tool_results)) {
				for (const tr of meta.tool_results) {
					html +=
						renderer.renderNativeToolResultBlock?.({
							content: tr.content || "",
							tool_call_id: tr.tool_call_id || "",
						}) || "";
				}
			}
			if (safeContent) {
				html += renderMessageContent(safeContent, false);
			}
			contentContainer.innerHTML =
				html || renderMessageContent(safeContent, false);
			setTimeout(() => {
				if (typeof hljs !== "undefined") {
					const codeBlocks = contentContainer.querySelectorAll("pre code");
					codeBlocks.forEach((block) => {
						if (!block.classList.contains("hljs")) {
							hljs.highlightElement(block);
						}
					});
				}
			}, 0);
		} else {
			contentContainer.textContent = safeContent;
		}

		msg.appendChild(contentContainer);
	}

	const footer = document.createElement("div");
	footer.className = isUserMessage
		? "message-footer message-footer--user"
		: "message-footer";

	const timeDiv = document.createElement("div");
	timeDiv.className = "timestamp";
	timeDiv.textContent = displayTime;
	footer.appendChild(timeDiv);

	const copyBtn = document.createElement("button");
	copyBtn.className = "copy-message-btn";
	copyBtn.setAttribute("data-action", "copy-message");
	copyBtn.setAttribute("data-message-content", safeContent);
	copyBtn.title = "Copy full message";
	copyBtn.innerHTML = `
		<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
			<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
			<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
		</svg>
	`;
	footer.appendChild(copyBtn);

	msg.appendChild(footer);
	return msg;
}

/**
 * Add a message to the chat container.
 * @param {string} role - 'user' or 'ai'
 * @param {string} content - Message content
 * @param {string|null} timestamp - Optional timestamp
 * @param {boolean} isHistory - Whether this is from history (skip scroll)
 * @param {object|null} meta - Optional metadata passed through for tool/native messages
 * @returns {HTMLElement|null} The message element
 */
export function addMessage(
	role,
	content,
	timestamp = null,
	isHistory = false,
	meta = null,
) {
	const chatContainer = document.getElementById("chatContainer");
	if (!chatContainer) {
		console.error("Cannot add message: chat container not found!");
		return null;
	}

	const msg = createMessageElement(role, content, timestamp, meta);
	if (!msg) return null;
	chatContainer.appendChild(msg);

	if (!isHistory) {
		setTimeout(() => {
			import("./scroll.js").then(({ scrollToBottom }) => {
				scrollToBottom();
			});
			if (typeof window.updateDynamicLayout === "function") {
				window.updateDynamicLayout();
			}
		}, 50);
	}

	console.log(`Added ${role} message`);
	return msg;
}

/**
 * Copy full message content to clipboard.
 * @param {string} content - Content to copy
 */
export function copyFullMessage(content) {
	if (typeof ClipboardUtils !== "undefined") {
		ClipboardUtils.copyText(content);
	} else {
		navigator.clipboard
			.writeText(content)
			.then(() => {
				console.log("Message copied to clipboard");
			})
			.catch((err) => {
				console.error("Failed to copy message:", err);
			});
	}
}

/**
 * Check if a role is renderable in history.
 * @param {string} role - Message role
 * @returns {boolean}
 */
export function isRenderableHistoryRole(role) {
	return (
		role === "user" ||
		role === "assistant" ||
		role === "tool" ||
		(typeof role === "string" && role.endsWith("_tools"))
	);
}

/**
 * Render message content through the renderer pipeline.
 * @param {string} rawText - Raw message text
 * @param {boolean} isUser - Whether this is a user message
 * @returns {string} Rendered HTML
 */
export function renderMessageContent(rawText, isUser = false) {
	const safeText = String(rawText ?? "");
	console.log("User raw message:", JSON.stringify(safeText));
	const escapedText = escapeMessageHtml(safeText);
	try {
		let processed = safeText;
		if (
			typeof renderer !== "undefined" &&
			typeof renderer.preprocessGeneratedImages === "function"
		) {
			processed = renderer.preprocessGeneratedImages(processed);
		}
		if (
			typeof renderer !== "undefined" &&
			typeof renderer.renderMessage === "function"
		) {
			return renderer.renderMessage(processed, isUser);
		}
		return escapedText;
	} catch (e) {
		console.error("Render error:", e, safeText);
		return `<pre class="render-error">${escapedText}</pre>`;
	}
}

/**
 * Escape HTML entities in text.
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
export function escapeMessageHtml(text) {
	if (
		typeof renderer !== "undefined" &&
		typeof renderer.escapeHtml === "function"
	) {
		return renderer.escapeHtml(text);
	}
	return String(text).replace(
		/[&<>"']/g,
		(c) =>
			({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
				c
			],
	);
}

/**
 * Format timestamp for display.
 * @param {string} timestamp - ISO timestamp string
 * @returns {string} Formatted time (HH:MM)
 */
export function formatTimestamp(timestamp) {
	if (!timestamp) return "";

	try {
		const dbDate = new Date(timestamp);
		let hours = dbDate.getHours();
		let minutes = dbDate.getMinutes();

		hours = hours < 10 ? `0${hours}` : hours;
		minutes = minutes < 10 ? `0${minutes}` : minutes;

		return `${hours}:${minutes}`;
	} catch (e) {
		console.error("Error formatting timestamp:", e, timestamp);
		return timestamp;
	}
}

/**
 * Get current time in 24h format.
 * @returns {string} Time as HH:MM
 */
export function getCurrentTime24h() {
	const now = new Date();
	let hours = now.getHours();
	let minutes = now.getMinutes();
	hours = hours < 10 ? `0${hours}` : hours;
	minutes = minutes < 10 ? `0${minutes}` : minutes;
	return `${hours}:${minutes}`;
}

// Re-export findMessageById for convenience
export { findMessageById };
