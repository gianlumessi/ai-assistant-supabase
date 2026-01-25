# 🚀 Quickstart Guide

Get your AI Assistant running in **15 minutes**.

## Prerequisites

- [ ] Supabase account (free tier works)
- [ ] OpenAI API key
- [ ] Render account (free tier works)

## Step 1: Clone & Configure (2 minutes)

```bash
# Clone the repository
git clone <your-repo-url>
cd ai-assistant-supabase

# Copy environment template
cp .env.example .env

# Edit .env and fill in your credentials
nano .env
```

Required values:
```bash
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGci...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
OPENAI_API_KEY=sk-...
```

## Step 2: Set Up Database (3 minutes)

1. Go to [Supabase SQL Editor](https://app.supabase.com)
2. Open `database/schema.sql`
3. Copy **entire file** contents
4. Paste into SQL Editor
5. Click **Run**
6. Verify tables created in Table Editor

## Step 3: Create Your First Website (1 minute)

In Supabase SQL Editor:

```sql
INSERT INTO websites (domain)
VALUES ('yourdomain.com')
RETURNING id;
```

**Copy the UUID** - you'll need it for the widget!

## Step 4: Deploy to Render (5 minutes)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New +** → **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Build**: `pip install -r requirements.txt`
   - **Start**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables (copy from your `.env`)
6. Click **Create Web Service**
7. Wait for deployment (~2 minutes)

Copy your Render URL: `https://your-service.onrender.com`

## Step 5: Test the API (1 minute)

Visit: `https://your-service.onrender.com/health/db`

Should return:
```json
{"ok": true, "count": 1}
```

✅ Backend is live!

## Step 6: Add Widget to Your Website (3 minutes)

Add this code before `</body>` on your website:

```html
<script src="https://your-service.onrender.com/widget/chat-widget.js"></script>
<script>
  window.AIChatWidget.init({
    apiBase: 'https://your-service.onrender.com',
    websiteId: 'your-uuid-from-step-3'
  });
</script>
```

## Step 7: Update CORS (Important!)

Edit `backend/main.py` line ~44:

```python
allow_origins=[
    "https://yourdomain.com",  # Add your domain!
    "https://www.yourdomain.com",
    # ... existing origins
],
```

Commit and push - Render auto-deploys!

## Step 8: Upload Knowledge Base (Optional)

### Option A: Use the ingestion script

1. Upload a file to Supabase Storage bucket `documents`
2. Edit `backend/scripts/ingest_one_file.py`:
   ```python
   WEBSITE_ID = 'your-uuid-from-step-3'
   PATH = "path/to/your/file.txt"
   ```
3. Run:
   ```bash
   python -m backend.scripts.ingest_one_file
   ```

### Option B: Use the API (if documents router enabled)

```bash
curl -X POST https://your-service.onrender.com/documents \
  -H "X-Website-Id: your-uuid" \
  -F "file=@document.pdf"
```

## ✅ You're Done!

Your AI Assistant is now:
- ✅ Deployed and running
- ✅ Embedded on your website
- ✅ Ready to answer questions

## 🧪 Test It Out

1. Open your website
2. Click the chat bubble
3. Ask a question
4. Get an AI response!

## 🎨 Customize (Optional)

### Change Colors

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-service.onrender.com',
  websiteId: 'your-uuid',
  theme: {
    primary: '#FF6B6B',  // Your brand color
    primary2: '#FF8787',
  }
});
```

### Change Title

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-service.onrender.com',
  websiteId: 'your-uuid',
  title: 'Support Assistant'  // Custom title
});
```

## 📚 Next Steps

- **Add more documents**: Upload PDFs, text files to your knowledge base
- **Monitor usage**: Check Render logs for activity
- **Customize styling**: See `WIDGET_INTEGRATION.md`
- **Scale up**: Upgrade Render to Starter ($7/mo) for always-on

## 🐛 Troubleshooting

### Widget not appearing?

1. Check browser console for errors
2. Verify `websiteId` is correct
3. Check CORS configuration includes your domain

### No responses?

1. Check `/health/db` endpoint works
2. Verify `OPENAI_API_KEY` is set
3. Check Render logs for errors

### "Database unavailable"?

1. Verify `SUPABASE_URL` is correct
2. Ensure `schema.sql` was executed
3. Check Supabase is not paused

## 💡 Pro Tips

1. **Free tier sleep**: Render free tier sleeps after 15min. Upgrade to Starter ($7/mo) for always-on
2. **Test locally first**: Run `uvicorn backend.main:app --reload` before deploying
3. **Monitor costs**: Check OpenAI usage at https://platform.openai.com/usage
4. **Backup database**: Export Supabase data regularly

## 📖 Documentation

- **README.md**: Full documentation
- **DEPLOYMENT.md**: Detailed deployment guide
- **WIDGET_INTEGRATION.md**: Widget customization
- **database/schema.sql**: Database schema reference

## 🆘 Need Help?

1. Check the troubleshooting section above
2. Review Render logs
3. Check Supabase logs
4. Open GitHub issue

---

**Congratulations!** 🎉

You now have a production-ready AI chatbot on your website.
