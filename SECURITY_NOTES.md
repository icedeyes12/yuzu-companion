# Security Notes

## CDN Script Integrity

### Current Status
The chat page loads JavaScript libraries from CDNs with `crossorigin="anonymous"` attribute but without SRI (Subresource Integrity) hashes.

### Recommendation
For production deployment, add integrity hashes to the CDN script tags. You can generate these hashes using:

```bash
# For marked.js
curl -s https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js | openssl dgst -sha384 -binary | openssl base64 -A

# For highlight.js
curl -s https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js | openssl dgst -sha384 -binary | openssl base64 -A
```

### Example with Integrity Hash
```html
<script src="https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js" 
        integrity="sha384-HASH_HERE" 
        crossorigin="anonymous"
        onerror="this.onerror=null; this.src='/static/js/lib/marked.min.js'"></script>
```

### Alternative: Use Local Files Only
For maximum security, download the actual library files to `static/js/lib/` and remove CDN dependencies entirely:

```bash
cd static/js/lib/
curl -o marked.min.js https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js
curl -o highlight.min.js https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js
```

Then update chat.html to load from local files only.

## XSS Protection

### Code Block Rendering
The renderer.js now uses a Map-based approach to store code content instead of inline data attributes, preventing potential XSS attacks through malicious code content.

**Before (vulnerable):**
```javascript
data-code="${escapeHtml(code).replace(/"/g, '&quot;')}"
```

**After (secure):**
```javascript
window.codeBlockContents.set(codeId, code);
data-code-id="${codeId}"
```

## Error Handling

All clipboard operations now include proper error handling with visual feedback:
- Success: Green "Copied!" state
- Failure: Red "Error!" state
- Console logging for debugging

## Additional Security Considerations

1. **Content Security Policy**: Consider adding CSP headers to restrict script sources
2. **HTTPS Only**: Ensure all CDN resources are loaded over HTTPS (currently enforced)
3. **Regular Updates**: Keep CDN library versions updated for security patches
4. **Dependency Scanning**: Regularly scan for vulnerabilities in dependencies

## CodeQL Findings

**Alert**: Script loaded from CDN with no integrity check
- **Severity**: Medium
- **Status**: Mitigated with crossorigin attribute, TODO for integrity hash
- **Location**: templates/chat.html lines 167-168
- **Recommendation**: Add SRI hash or use local files (see above)
