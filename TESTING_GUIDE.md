# Local Testing Checklist

Complete testing guide using `demo.html` before deploying to production.

## 🔧 Setup

### 1. Start Local Backend

```bash
# In your project directory
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
2026-01-26 22:21:38 INFO backend.main AI Assistant Backend starting up
INFO: Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 2. Verify Environment Variables

Check your `.env` file has:
```bash
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
OPENAI_API_KEY=...
```

### 3. Open Demo Page

Open `frontend/widget/demo.html` in your browser and configure:
- **API base**: `http://localhost:8000`
- **Website ID**: Your test website UUID from Supabase

---

## ✅ Test Suite

### **Test 1: Health Check** ⏱️ 30 seconds

**Purpose**: Verify backend is running and connected to database

**Steps**:
1. Open browser: `http://localhost:8000/health/db`
2. Check response: `{"ok": true, "count": X}`

**Expected Result**:
- ✅ Status 200 OK
- ✅ JSON response with `ok: true`
- ✅ Count shows number of websites in database

**If Failed**:
- Check `.env` file has correct `SUPABASE_URL`
- Verify database schema is deployed
- Check Supabase project is active

---

### **Test 2: Widget Loads** ⏱️ 1 minute

**Purpose**: Verify widget renders and initializes

**Steps**:
1. Open `frontend/widget/demo.html`
2. Check bottom-right corner for chat bubble

**Expected Result**:
- ✅ Purple gradient chat bubble visible
- ✅ Bubble is clickable
- ✅ Click opens chat panel
- ✅ Panel shows title "AI Assistant"
- ✅ Input field and send button present

**Visual Check**:
```
Bottom-right corner:
┌─────────────────────────────┐
│  AI Assistant           [ X ]│
│─────────────────────────────│
│                             │
│  (Empty - no messages yet)  │
│                             │
│─────────────────────────────│
│ Type your message...  [Send]│
└─────────────────────────────┘
```

**If Failed**:
- Check browser console for errors
- Verify `websiteId` is correct UUID format
- Check `apiBase` is `http://localhost:8000`

---

### **Test 3: Basic Chat Response** ⏱️ 1 minute

**Purpose**: Verify end-to-end chat functionality

**Steps**:
1. Type: "Hello"
2. Click Send (or press Enter)
3. Wait for response

**Expected Result**:
- ✅ Message appears in chat as user bubble (right-aligned)
- ✅ "Typing..." indicator shows
- ✅ Response streams in word-by-word (left-aligned, gray background)
- ✅ Response completes within 5-10 seconds
- ✅ No errors in browser console

**Expected Response** (approximate):
> "Hello! How can I help you today?"

**Backend Logs to Check**:
```
INFO backend.services.retrieval Gathering context for website...
INFO backend.services.retrieval Fetched X chunks...
INFO backend.services.retrieval Context gathered: top_chunks=X...
```

**If Failed**:
- Check browser Network tab for failed requests
- Check backend logs for errors
- Verify `OPENAI_API_KEY` is set and valid
- Check OpenAI account has credits

---

### **Test 4: RAG Context Retrieval** ⏱️ 2 minutes

**Purpose**: Verify document retrieval and context gathering

**Prerequisites**: You need documents ingested in your knowledge base

**Steps**:
1. Ask a question related to your documents:
   - Example: "What services do you offer?"
   - Example: "What are your business hours?"
2. Wait for response

**Expected Result**:
- ✅ Response contains information from your documents
- ✅ Response is relevant and accurate
- ✅ No "I do not have enough information" message (if documents exist)

**Backend Logs to Check**:
```
INFO backend.services.retrieval Fetched X chunks for website... (X should be > 0)
INFO backend.services.retrieval Context gathered: top_chunks=X, unique_docs=Y, top_score=0.XXXX
```

**Top Score Interpretation**:
- **0.8-1.0**: Excellent match - high confidence answer
- **0.6-0.8**: Good match - relevant answer
- **0.4-0.6**: Moderate match - answer may be generic
- **< 0.4**: Poor match - may not find good context

**If No Documents**:
Should respond: *"I do not have enough information to answer your question. I recommend messaging the website owner for details..."*

**If Failed with Documents**:
- Verify documents were ingested (check `document_chunks` table)
- Check embeddings are present
- Look for errors in retrieval logs

---

### **Test 5: Multi-Turn Conversation** ⏱️ 2 minutes

**Purpose**: Verify conversation history works

**Steps**:
1. Ask: "What is your name?"
2. Wait for response
3. Ask: "What did I just ask you?"
4. Wait for response

**Expected Result**:
- ✅ Second response references the first question
- ✅ Bot remembers context from previous message
- ✅ Example: "You asked about my name."

**If Failed**:
- Check chat history is being sent (Network tab → Payload)
- Verify messages are being stored in database

---

### **Test 6: Empty Message Handling** ⏱️ 30 seconds

**Purpose**: Verify input validation

**Steps**:
1. Try to send empty message (just spaces)
2. Try to send message with only whitespace

**Expected Result**:
- ✅ Send button disabled when input is empty
- ✅ Cannot send empty/whitespace-only messages
- ✅ No error in console

**If Failed**:
- Widget should prevent empty submissions
- If it sends, backend should reject with 400 error

---

### **Test 7: Long Message Handling** ⏱️ 1 minute

**Purpose**: Verify long input handling

**Steps**:
1. Paste a very long message (2000+ characters)
2. Try to send

**Expected Result**:
- ✅ Message is accepted (up to 4000 chars limit)
- ✅ Response generated successfully
- ✅ UI scrolls properly for long messages

**If Over Limit** (>4000 chars):
- Should receive error: "Message too long"

---

### **Test 8: Rate Limiting** ⏱️ 2 minutes

**Purpose**: Verify rate limiting protection

**Steps**:
1. Send 5 quick messages in a row (spam send button)
2. Note response times
3. Try to send 20+ messages rapidly

**Expected Result**:
- ✅ First 20 messages work fine
- ✅ After 20 messages in 1 minute, get rate limit error

**Rate Limit Response**:
```
Status: 429 Too Many Requests
"Rate limit exceeded. Please try again shortly."
```

**Backend Logs**:
```
Rate limited: website_id=... ip=127.0.0.1
```

**If Failed**:
- Rate limiting may not be working
- Check `backend/routers/chat.py` rate limit config

---

### **Test 9: Error Handling - Invalid Website ID** ⏱️ 1 minute

**Purpose**: Verify error handling for bad input

**Steps**:
1. Change Website ID to: `invalid-uuid`
2. Refresh page
3. Try to send a message

**Expected Result**:
- ✅ Clear error message shown
- ✅ No stack trace visible to user
- ✅ Error is user-friendly

**Expected Error**:
```
"Invalid website_id format"
```

**If Failed**:
- Check global exception handlers in `main.py`
- Verify no raw exceptions exposed

---

### **Test 10: Error Handling - Backend Down** ⏱️ 1 minute

**Purpose**: Verify graceful degradation

**Steps**:
1. Stop the backend server (Ctrl+C)
2. Try to send a message in the widget

**Expected Result**:
- ✅ User-friendly error message
- ✅ "Retry" or helpful guidance shown
- ✅ No scary error messages

**Expected Behavior**:
- Network error detected
- Message: "Unable to connect. Please try again."

**Then**:
1. Restart backend
2. Retry the message
3. Should work normally

---

### **Test 11: Streaming Response** ⏱️ 1 minute

**Purpose**: Verify SSE streaming works correctly

**Steps**:
1. Ask: "Tell me a story in 3 paragraphs"
2. Watch the response appear

**Expected Result**:
- ✅ Text appears word-by-word, not all at once
- ✅ Smooth streaming animation
- ✅ No flickering or jumps
- ✅ Complete response arrives

**Backend Logs**:
```
INFO: "POST /chat/stream HTTP/1.1" 200 OK
```

**Browser Network Tab**:
- Response type: `text/event-stream`
- Transfer: chunked
- Multiple `event: token` events followed by `event: final`

**If Failed**:
- Check Network tab for SSE connection
- Look for disconnections or errors
- Verify OpenAI streaming is working

---

### **Test 12: Feedback Buttons** ⏱️ 1 minute

**Purpose**: Verify thumbs up/down functionality

**Steps**:
1. Send a message and get a response
2. Look for 👍 👎 buttons on assistant message
3. Click thumbs up 👍
4. Check console

**Expected Result**:
- ✅ Feedback buttons visible on assistant messages
- ✅ Click changes button color (purple when selected)
- ✅ Console log shows feedback if callback configured
- ✅ Can toggle between up/down

**Console Output** (if `onFeedback` is configured):
```javascript
{
  websiteId: "...",
  sessionId: "...",
  visitorId: "...",
  rating: "up",
  message: "...",
  ts: 1234567890
}
```

---

### **Test 13: Mobile Responsiveness** ⏱️ 2 minutes

**Purpose**: Verify widget works on mobile

**Steps**:
1. Open browser DevTools (F12)
2. Toggle device toolbar (responsive mode)
3. Switch to iPhone or Android view
4. Test widget functionality

**Expected Result**:
- ✅ Widget scales appropriately
- ✅ Chat bubble visible and clickable
- ✅ Panel opens and fits screen
- ✅ Input field accessible
- ✅ Messages readable
- ✅ Can scroll through conversation

**Test On**:
- iPhone 12/13/14 view
- iPad view
- Android phone view

**If Failed**:
- Check CSS media queries
- Verify viewport meta tag

---

### **Test 14: Theme Customization** ⏱️ 2 minutes

**Purpose**: Verify theme configuration works

**Steps**:
1. In `demo.html`, modify theme:
```javascript
window.AIChatWidget.init({
  apiBase: 'http://localhost:8000',
  websiteId: 'your-uuid',
  theme: {
    primary: '#FF0000',  // Red
    primary2: '#FF6666',
    bg: '#FFFFFF',
    text: '#000000',
  }
});
```
2. Refresh page
3. Open widget

**Expected Result**:
- ✅ Chat bubble is now red gradient
- ✅ Send button is red
- ✅ Colors match your theme settings
- ✅ Text is readable with new colors

**If Failed**:
- Theme not applying
- Check CSS variable injection

---

### **Test 15: Session Persistence** ⏱️ 1 minute

**Purpose**: Verify chat history persists

**Steps**:
1. Send 3 messages and get responses
2. Close the chat panel (click X)
3. Reopen the chat panel (click bubble)

**Expected Result**:
- ✅ All previous messages still visible
- ✅ Conversation history maintained
- ✅ Can continue conversation

**Note**: On page refresh, session may reset (by design)

---

### **Test 16: Concurrent Requests** ⏱️ 1 minute

**Purpose**: Verify backend handles multiple requests

**Steps**:
1. Send a message
2. While response is streaming, send another message
3. Observe behavior

**Expected Result**:
- ✅ Second request waits or queues
- ✅ No crashes or errors
- ✅ Both responses complete successfully

**If Failed**:
- Check for race conditions
- Verify controller abort logic

---

### **Test 17: Browser Compatibility** ⏱️ 5 minutes

**Purpose**: Verify widget works across browsers

**Test In**:
- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari (if on Mac)

**Each Browser**:
1. Open demo.html
2. Send test message
3. Verify streaming works
4. Check console for errors

**Expected Result**:
- ✅ Widget works identically in all browsers
- ✅ No browser-specific errors
- ✅ Styling consistent

---

## 📊 Test Results Template

Use this to track your testing:

```markdown
## Test Results - [Date]

### Environment
- Backend: Local (http://localhost:8000)
- Website ID: [your-uuid]
- Documents ingested: Yes/No

### Results

| Test # | Test Name | Status | Notes |
|--------|-----------|--------|-------|
| 1 | Health Check | ✅ PASS | |
| 2 | Widget Loads | ✅ PASS | |
| 3 | Basic Chat | ✅ PASS | |
| 4 | RAG Retrieval | ✅ PASS | Top score: 0.85 |
| 5 | Multi-Turn | ✅ PASS | |
| 6 | Empty Message | ✅ PASS | |
| 7 | Long Message | ✅ PASS | |
| 8 | Rate Limiting | ✅ PASS | |
| 9 | Invalid UUID | ✅ PASS | |
| 10 | Backend Down | ✅ PASS | |
| 11 | Streaming | ✅ PASS | |
| 12 | Feedback | ✅ PASS | |
| 13 | Mobile | ✅ PASS | |
| 14 | Theme | ✅ PASS | |
| 15 | Session | ✅ PASS | |
| 16 | Concurrent | ✅ PASS | |
| 17 | Browsers | ✅ PASS | Chrome, Firefox |

### Issues Found
- None / [List any issues]

### Ready for Production?
- ✅ YES / ❌ NO

### Next Steps
- Merge to main
- Deploy to Render
- Test on production domain
```

---

## 🐛 Common Issues & Fixes

### Issue: "CORS Error"
**Symptom**: Network request blocked
**Fix**: Ensure localhost is in CORS origins (should be by default)

### Issue: "Database unavailable"
**Symptom**: 503 error on all requests
**Fix**: Check `.env` has correct `SUPABASE_URL` and database schema is deployed

### Issue: "Context retrieval failed"
**Symptom**: Always says "I don't have enough information"
**Fix**:
1. Check documents are ingested: `SELECT COUNT(*) FROM document_chunks WHERE website_id = 'your-uuid'`
2. Run ingestion script if needed

### Issue: Widget not appearing
**Symptom**: No chat bubble visible
**Fix**:
1. Check browser console for JavaScript errors
2. Verify script loaded: `window.AIChatWidget` should be defined
3. Check `websiteId` format (must be valid UUID)

### Issue: Slow responses
**Symptom**: >30 seconds for response
**Fix**:
1. Check OpenAI API status
2. Verify internet connection
3. Check backend logs for delays

---

## ✅ Pre-Deployment Checklist

Before merging to main and deploying:

- [ ] All 17 tests passed locally
- [ ] No errors in browser console
- [ ] No errors in backend logs
- [ ] RAG retrieval working (if documents exist)
- [ ] Streaming responses smooth
- [ ] Mobile view tested
- [ ] Multiple browsers tested
- [ ] Rate limiting working
- [ ] Error messages user-friendly
- [ ] Theme customization working
- [ ] Code committed to branch
- [ ] Documentation reviewed

---

## 🚀 Deployment Steps (After Tests Pass)

1. **Merge to Main**
```bash
git checkout main
git merge claude/improve-error-handling-logging-1d8IE
git push origin main
```

2. **Verify Render Auto-Deploys**
- Check Render dashboard
- Wait for build to complete (~2-3 minutes)

3. **Test Production**
- Open: `https://ai-assistant-supabase.onrender.com/health/db`
- Verify: `{"ok": true, "count": X}`

4. **Test Widget on Production**
- Update demo.html: `apiBase: 'https://ai-assistant-supabase.onrender.com'`
- Run all tests again against production

5. **Deploy to Real Website**
- Add widget code to your site
- Test with real users
- Monitor Render logs

---

## 📞 Support

If tests fail:
1. Check error messages in browser console
2. Check backend logs
3. Review relevant documentation:
   - `README.md`
   - `DEPLOYMENT.md`
   - `WIDGET_INTEGRATION.md`
4. Review error handling docs:
   - `USER_FACING_ERROR_HANDLING.md`
   - `IMPROVEMENTS_SUMMARY.md`

---

**Good luck with testing!** 🧪

Once all tests pass, you're ready for production! 🚀
