# Local Library Fallbacks

This directory contains local fallback copies of external libraries used by the chat page.

## Required Files

### marked.min.js
- **Purpose**: Markdown parsing library
- **CDN**: https://cdn.jsdelivr.net/npm/marked/marked.min.js
- **Version**: Latest stable
- **Download**: `curl -o marked.min.js https://cdn.jsdelivr.net/npm/marked/marked.min.js`

### highlight.min.js
- **Purpose**: Syntax highlighting library
- **CDN**: https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js
- **Version**: 11.9.0 or later
- **Download**: `curl -o highlight.min.js https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js`

## Usage

These files serve as fallbacks if CDN is unavailable. The chat page will attempt to load from CDN first, then fall back to these local copies if needed.
