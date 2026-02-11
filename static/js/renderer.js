// Initialize markdown-it
const md = window.markdownit();

/**
 * Render markdown content to HTML
 * @param {string} text - The markdown text to render
 * @returns {string} - The rendered HTML
 */
function renderMessageContent(text) {
    return md.render(String(text));
}
