# Chat Page Rebuild - Manual Testing Guide

## Overview
This document provides a comprehensive testing checklist for the rebuilt chat page using Tailwind CSS.

## Prerequisites
1. Start the application: `python web.py` or `python main.py`
2. Navigate to the chat page in your browser
3. Have at least one chat session with some messages

---

## Test Suite

### 1. Layout Tests

#### Header
- [ ] Header is visible at the top
- [ ] Assistant name (partner_name) is displayed
- [ ] Session name is displayed below assistant name
- [ ] Affection bar is visible on the right
- [ ] Affection percentage is displayed next to the bar
- [ ] Header does not overlap with sidebar when sidebar is open

#### Chat Container
- [ ] Chat messages area is scrollable
- [ ] Messages do not overflow the viewport
- [ ] Scroll bar appears when content exceeds viewport
- [ ] Chat container takes up available space between header and input

#### Input Area
- [ ] Textarea is visible at the bottom
- [ ] Textarea has placeholder text
- [ ] Send button is visible next to textarea
- [ ] Send button is fixed height (doesn't stretch)
- [ ] Input area stays at bottom of screen

---

### 2. Message Display Tests

#### Message Structure
- [ ] User messages appear on the right
- [ ] AI messages appear on the left
- [ ] Messages have distinct background colors
- [ ] Message bubbles have border accent on left side
- [ ] Timestamps are displayed (if available)

#### Content Rendering
Test by sending a message with the following content:

```markdown
# Heading 1
## Heading 2
### Heading 3

**Bold text** and *italic text* and ***bold italic***

- Bullet point 1
- Bullet point 2
  - Nested bullet
  - Another nested

1. Numbered item 1
2. Numbered item 2
3. Numbered item 3

> This is a blockquote
> Second line of blockquote
>> Nested blockquote

`inline code` and a [link](https://example.com)

---

| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |

```python
def hello_world():
    print("Hello, World!")
    return True
```

![Test Image](https://via.placeholder.com/300)

<details>
<summary>Click to expand</summary>
This is hidden content inside details
</details>
```

**Check that:**
- [ ] All headings render correctly
- [ ] Bold and italic formatting works
- [ ] Bullet lists render correctly
- [ ] Numbered lists render correctly
- [ ] Nested lists work
- [ ] Blockquotes render with left border
- [ ] Nested blockquotes work
- [ ] Inline code has background
- [ ] Links are clickable and open in new tab
- [ ] Horizontal rule renders
- [ ] Table renders with borders
- [ ] Table scrolls horizontally if too wide
- [ ] Code block renders with syntax highlighting
- [ ] Code block has copy button
- [ ] Images scale to fit bubble (max-width: 100%)
- [ ] Details/summary works (if supported)

---

### 3. Code Block Tests

#### Structure
- [ ] Code blocks have a container div
- [ ] Copy button appears in top-right corner
- [ ] Language name is displayed (if available)
- [ ] Code is syntax highlighted

#### Functionality
- [ ] Click copy button copies code to clipboard
- [ ] Copy button shows "Copied!" feedback
- [ ] Copy button reverts after 2 seconds
- [ ] Code block scrolls horizontally for long lines

#### Test Code Samples
Send messages with these code blocks:

Python:
````markdown
```python
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
```
````

JavaScript:
````markdown
```javascript
function fibonacci(n) {
    if (n <= 1) return n;
    return fibonacci(n - 1) + fibonacci(n - 2);
}
```
````

No language specified:
````markdown
```
This is a code block
with no language
specified
```
````

---

### 4. Input Behavior Tests

#### Keyboard Shortcuts
- [ ] Press Enter: Creates newline in textarea
- [ ] Press Ctrl+Enter: Sends message
- [ ] Press Cmd+Enter (Mac): Sends message

#### Auto-resize
- [ ] Textarea starts with 1 row
- [ ] Textarea expands as you type multiple lines
- [ ] Textarea stops expanding at max height (200px)
- [ ] Scroll bar appears when max height reached

#### Send Button
- [ ] Send button is enabled when textarea has text
- [ ] Send button is disabled while sending message
- [ ] Send button re-enables after message sent
- [ ] Clicking send button sends the message
- [ ] Textarea clears after sending
- [ ] Textarea resets to initial height after sending

---

### 5. Pagination Tests

#### Initial Load
- [ ] Last 30 messages load on page load
- [ ] Older messages are not loaded initially
- [ ] Chat scrolls to bottom after loading

#### Load Older Messages
- [ ] Scroll to top of chat container
- [ ] Older messages load automatically
- [ ] Scroll position is preserved (doesn't jump)
- [ ] Can continue scrolling up to load more
- [ ] Loading stops when all messages loaded

---

### 6. Scroll Behavior Tests

#### Scroll to Bottom Button
- [ ] Button is hidden when at bottom of chat
- [ ] Button appears when scrolled up
- [ ] Click button scrolls to newest message
- [ ] Button has smooth transition

#### Auto-scroll
- [ ] New messages trigger auto-scroll if near bottom
- [ ] New messages don't auto-scroll if scrolled up

---

### 7. Theme Tests

Test each of the 7 themes:

#### Dark Blue (default)
- [ ] Background is dark blue
- [ ] Text is light colored
- [ ] User bubbles are pink/rose
- [ ] AI bubbles are blue-gray
- [ ] Code blocks are visible
- [ ] All text is readable

#### Soft Light
- [ ] Background is light
- [ ] Text is dark
- [ ] Bubbles have good contrast
- [ ] All elements visible

#### Pastel Lavender
- [ ] Purple/lavender color scheme
- [ ] Text is readable
- [ ] Bubbles have good contrast

#### Pastel Mint
- [ ] Green/mint color scheme
- [ ] Text is readable
- [ ] Bubbles have good contrast

#### Pastel Peach
- [ ] Orange/peach color scheme
- [ ] Text is readable
- [ ] Bubbles have good contrast

#### Dark Lavender
- [ ] Dark purple color scheme
- [ ] Light text on dark background
- [ ] Bubbles have good contrast

#### Vanilla Orange
- [ ] Warm vanilla/orange scheme
- [ ] Text is readable
- [ ] Bubbles have good contrast

**For all themes check:**
- [ ] Smooth transition when switching themes
- [ ] No flickering
- [ ] All UI elements respect theme colors
- [ ] Code blocks use theme-appropriate colors

---

### 8. Sidebar Tests

#### Sidebar Functionality
- [ ] Click hamburger menu opens sidebar
- [ ] Click overlay closes sidebar
- [ ] Click X button closes sidebar
- [ ] Sidebar shows navigation links
- [ ] Sidebar shows theme selector
- [ ] Sidebar shows sessions list

#### Session Management
- [ ] Sessions list loads when sidebar opens
- [ ] "New Chat" button creates new session
- [ ] Clicking a session switches to it
- [ ] Active session is highlighted
- [ ] Chat history updates when switching sessions

---

### 9. Responsive Design Tests

#### Desktop (> 768px)
- [ ] Sidebar can be toggled
- [ ] Chat area uses full width when sidebar closed
- [ ] Chat area shrinks when sidebar open
- [ ] All elements are properly sized

#### Tablet (768px)
- [ ] Sidebar overlays content
- [ ] Hamburger menu is visible
- [ ] Chat area uses full width
- [ ] Touch scrolling works

#### Mobile (< 768px)
- [ ] Sidebar is full-screen overlay
- [ ] Hamburger menu is visible
- [ ] Messages are readable
- [ ] Input area is accessible
- [ ] Virtual keyboard doesn't break layout

---

### 10. Overflow Safety Tests

#### Long Content
Send a message with very long content to test:

```markdown
This is a very long line of text without any spaces that should wrap properly inside the message bubble and not overflow into other areas of the page or cause horizontal scrolling issues.

https://this-is-a-very-long-url-that-should-also-wrap-properly-and-not-cause-overflow-issues-in-the-message-bubble.example.com/with/many/path/segments/that/make/it/extremely/long
```

- [ ] Long text wraps inside bubble
- [ ] Long URLs wrap or break properly
- [ ] No horizontal scrolling in chat area

#### Wide Tables
Send a message with a very wide table:

```markdown
| Column 1 | Column 2 | Column 3 | Column 4 | Column 5 | Column 6 | Column 7 | Column 8 |
|----------|----------|----------|----------|----------|----------|----------|----------|
| Data     | Data     | Data     | Data     | Data     | Data     | Data     | Data     |
```

- [ ] Table has horizontal scrollbar
- [ ] Table doesn't break bubble
- [ ] Table doesn't cause page to scroll

#### Large Images
Send a message with a large image:

```markdown
![Large Image](https://via.placeholder.com/2000x1000)
```

- [ ] Image scales down to fit bubble
- [ ] Image maintains aspect ratio
- [ ] Image doesn't overflow bubble

---

### 11. Error Handling Tests

#### Network Errors
- [ ] Disconnect network
- [ ] Try to send message
- [ ] Error message is displayed
- [ ] Typing indicator disappears
- [ ] Can retry after network restored

#### Empty Messages
- [ ] Try to send empty message (spaces only)
- [ ] Nothing happens (message not sent)

---

### 12. Performance Tests

#### Large Chat History
- [ ] Load session with 100+ messages
- [ ] Page loads in reasonable time
- [ ] Pagination works smoothly
- [ ] Scrolling is smooth
- [ ] No lag when typing

#### Rapid Sending
- [ ] Send multiple messages quickly
- [ ] All messages are sent
- [ ] UI remains responsive
- [ ] No duplicate messages

---

## Bug Report Template

If you find any issues, report them using this template:

```
**Issue Title:** [Brief description]

**Severity:** [Critical/High/Medium/Low]

**Environment:**
- Browser: [Chrome/Firefox/Safari/Edge] Version: [X.X]
- OS: [Windows/Mac/Linux]
- Screen size: [Width x Height]

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Behavior:**
[What should happen]

**Actual Behavior:**
[What actually happens]

**Screenshots:**
[If applicable]

**Console Errors:**
[Any JavaScript errors from browser console]
```

---

## Success Criteria

The implementation is considered successful if:
- ✅ All layout tests pass
- ✅ All markdown features render correctly
- ✅ Code blocks work with copy functionality
- ✅ All 7 themes work properly
- ✅ Input behavior matches requirements
- ✅ Pagination works smoothly
- ✅ No content overflow issues
- ✅ Responsive on all screen sizes
- ✅ No backend modifications
- ✅ Sidebar functionality preserved

---

## Notes for Reviewer

1. **Tailwind CSS**: Uses CDN with inline fallback for offline mode
2. **markdown-it**: Comprehensive markdown parsing replacing custom parser
3. **No backend changes**: All backend logic and APIs untouched
4. **Clean structure**: Simplified message DOM, removed special cases
5. **Theme integration**: Full support for all existing 7 themes
