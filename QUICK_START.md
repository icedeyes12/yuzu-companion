# Quick Start Guide - Testing the New Chat Page

## 🚀 Getting Started

### 1. Start the Application
```bash
cd /home/runner/work/yuzu-companion/yuzu-companion
python web.py
```
Or:
```bash
python main.py
# Then select web interface option
```

### 2. Open Browser
Navigate to: `http://localhost:5000/chat` (or whatever port is configured)

### 3. First Visual Check
You should see:
- ✅ Header at top (assistant name, session name, affection bar)
- ✅ Chat messages in center (scrollable)
- ✅ Input box at bottom with "Send" button
- ✅ Hamburger menu icon (top-left)
- ✅ Clean, modern layout

---

## ⚡ Quick Test Sequence

### Test 1: Basic Message (30 seconds)
1. Type: "Hello, how are you?"
2. Press **Ctrl+Enter** (or click Send)
3. **Expected:** Message appears on right, AI responds on left

### Test 2: Enter Key (15 seconds)
1. Type: "Line 1"
2. Press **Enter** (not Ctrl+Enter)
3. Type: "Line 2"
4. **Expected:** Two lines in the input box (newline created)

### Test 3: Markdown (1 minute)
Send this message:
```
**Bold text** and *italic text*

- Bullet 1
- Bullet 2

> This is a quote
```

**Expected:**
- Bold and italic render correctly
- Bullet list renders
- Blockquote has left border

### Test 4: Code Block (1 minute)
Send this:
````
```python
def hello():
    print("world")
```
````

**Expected:**
- Code has syntax highlighting
- Copy button appears top-right
- Click copy → "Copied!" feedback

### Test 5: Table (1 minute)
Send this:
```
| Name | Age |
|------|-----|
| John | 25  |
| Jane | 30  |
```

**Expected:**
- Table renders with borders
- If you make it wide, it scrolls horizontally

### Test 6: Image (30 seconds)
Send this:
```
![Test](https://via.placeholder.com/600)
```

**Expected:**
- Image appears
- Image scales to fit bubble (not full width)

### Test 7: Theme Switch (1 minute)
1. Click hamburger menu (top-left)
2. Click theme dropdown
3. Select "Soft Light"
4. **Expected:** Theme changes smoothly, all colors update

### Test 8: Pagination (1 minute)
1. Scroll to top of chat
2. Keep scrolling up
3. **Expected:** Older messages load automatically

### Test 9: Scroll Button (30 seconds)
1. Scroll up in chat
2. **Expected:** Floating button appears (bottom-right)
3. Click button
4. **Expected:** Scroll to bottom

### Test 10: New Session (30 seconds)
1. Open sidebar
2. Click "New Chat"
3. **Expected:** Chat clears, new session starts

---

## 🎨 Theme Testing (5 minutes)

Test each theme quickly:
1. **Dark Blue** (default) - Dark background, light text
2. **Soft Light** - Light background, dark text
3. **Pastel Lavender** - Purple theme
4. **Pastel Mint** - Green theme
5. **Pastel Peach** - Orange theme
6. **Dark Lavender** - Dark purple
7. **Vanilla Orange** - Warm vanilla

**For each theme:**
- ✅ Text is readable
- ✅ User bubbles have distinct color
- ✅ AI bubbles have distinct color
- ✅ Code blocks are visible

---

## 📱 Mobile Test (3 minutes)

### Desktop → Mobile
1. Resize browser window to 375px wide (mobile size)
2. **Check:**
   - ✅ Layout adapts
   - ✅ Messages are readable
   - ✅ Input is accessible
   - ✅ Sidebar overlays (doesn't push content)

### Or Use Browser DevTools
1. Press **F12**
2. Click device toolbar icon
3. Select "iPhone SE" or similar
4. **Check same as above**

---

## 🐛 Common Issues & Solutions

### Issue: Tailwind styles not loading
**Symptom:** Page looks broken, no spacing
**Solution:** 
- Check if CDN is blocked
- Fallback CSS should kick in automatically
- Check browser console for errors

### Issue: Markdown not rendering
**Symptom:** Raw markdown shows (like **bold**)
**Solution:**
- Check if markdown-it loaded (CDN might be blocked)
- Should fallback to MarkdownParser
- Check browser console for errors

### Issue: Code blocks have no copy button
**Symptom:** Copy button missing
**Solution:**
- Check if JavaScript loaded
- Check browser console for errors
- Try refreshing page

### Issue: Messages not sending
**Symptom:** Click send, nothing happens
**Solution:**
- Check browser console for errors
- Check network tab for failed API calls
- Verify backend is running

### Issue: Theme not changing
**Symptom:** Click theme, colors don't change
**Solution:**
- Check if theme.css loaded
- Check browser console for errors
- Try hard refresh (Ctrl+Shift+R)

---

## 🔍 Browser Console Check

### Open Console
- **Chrome/Edge:** Press **F12** → Console tab
- **Firefox:** Press **F12** → Console tab
- **Safari:** Develop → Show JavaScript Console

### Expected Messages
```
Initializing new chat system...
markdown-it initialized
DOM loaded, initializing chat...
Loaded X messages
Chat system ready!
```

### Red Flags (Should NOT see)
```
❌ Uncaught TypeError
❌ Failed to load resource
❌ undefined is not a function
❌ Cannot read property of null
```

---

## ✅ Success Checklist

After 10-15 minutes of testing, you should confirm:
- [ ] Messages send and appear correctly
- [ ] Markdown renders (bold, italic, lists, quotes)
- [ ] Code blocks have syntax highlighting and copy button
- [ ] Tables render and scroll if wide
- [ ] Images scale to fit
- [ ] Enter creates newline, Ctrl+Enter sends
- [ ] All 7 themes work
- [ ] Pagination loads older messages
- [ ] Scroll-to-bottom button works
- [ ] Mobile layout looks good
- [ ] No console errors

---

## 📸 Screenshot Guide

### Screenshots Needed
Take screenshots of:

1. **Default View** (Dark Blue theme)
   - Full page showing header, messages, input

2. **Message with Markdown**
   - Bold, italic, lists, blockquotes visible

3. **Code Block**
   - With syntax highlighting and copy button

4. **Table**
   - Showing borders and headers

5. **Light Theme**
   - Switch to Soft Light, take screenshot

6. **Mobile View**
   - Resize to 375px, take screenshot

7. **Sidebar Open**
   - Show sidebar with session list

### How to Take Screenshots
- **Windows:** Win+Shift+S
- **Mac:** Cmd+Shift+4
- **Linux:** Usually Shift+PrtScn
- **Browser:** F12 → Device toolbar → Screenshot icon

---

## 🆘 Need Help?

### Check These Files First
1. **TESTING_GUIDE.md** - Detailed testing procedures
2. **IMPLEMENTATION_SUMMARY.md** - Architecture details
3. **PR_SUMMARY.md** - Overview of changes

### Debugging Steps
1. Check browser console for errors
2. Check network tab for failed requests
3. Verify theme.css and sidebar.css loaded
4. Try different browser
5. Clear cache and hard refresh

### Rollback if Needed
```bash
cd templates/
mv chat.html chat.html.new
mv chat.html.backup chat.html
# Restart app
```

---

## 🎯 Priority Tests

If short on time, test these in order:

1. **Critical** (Must work)
   - [ ] Send message
   - [ ] Markdown renders
   - [ ] Themes work
   - [ ] No console errors

2. **High** (Should work)
   - [ ] Code blocks with copy
   - [ ] Pagination
   - [ ] Input behavior (Enter/Ctrl+Enter)
   - [ ] Mobile responsive

3. **Medium** (Nice to have)
   - [ ] Tables
   - [ ] Images
   - [ ] Scroll button
   - [ ] Session switching

---

## 📊 Test Results Template

```markdown
## Test Results

**Date:** YYYY-MM-DD
**Browser:** Chrome/Firefox/Safari X.X
**OS:** Windows/Mac/Linux

### Basic Functionality
- [ ] Messages send/receive: PASS/FAIL
- [ ] Markdown rendering: PASS/FAIL
- [ ] Code blocks: PASS/FAIL
- [ ] Themes: PASS/FAIL

### Notes:
- Issue 1: [describe]
- Issue 2: [describe]

### Screenshots:
- [Link to screenshot 1]
- [Link to screenshot 2]
```

---

## 🎉 Success!

If all tests pass:
1. ✅ Implementation is successful
2. ✅ Ready for production
3. ✅ Document any minor issues
4. ✅ Merge PR

**Congratulations!** The chat page rebuild is complete. 🚀
