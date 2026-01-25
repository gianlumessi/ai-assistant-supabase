# Deployment Guide

This guide covers deploying the AI Assistant to Render.com and other platforms.

## 🚀 Deploy to Render (Recommended)

Render is excellent for this application because:
- ✅ **Free tier available** (750 hours/month)
- ✅ **Auto-deploys from Git**
- ✅ **Easy environment variable management**
- ✅ **Built-in SSL/HTTPS**
- ✅ **Good for Python/FastAPI apps**
- ✅ **Automatic health checks**

### Prerequisites

1. **Render account** (free): https://render.com
2. **GitHub/GitLab repository** with your code
3. **Supabase project** set up with database schema
4. **OpenAI API key**

### Step 1: Prepare Your Repository

Ensure these files are in your repository:
- ✅ `requirements.txt` (fixed encoding)
- ✅ `.env.example` (but NOT `.env`)
- ✅ `backend/` directory with all code
- ✅ `database/schema.sql` (for reference)

### Step 2: Set Up Supabase Database

1. Go to your Supabase project
2. Navigate to **SQL Editor**
3. Copy the entire contents of `database/schema.sql`
4. Execute the SQL to create all tables, indexes, and RLS policies
5. Verify tables were created: Go to **Table Editor**

### Step 3: Create Render Web Service

1. **Log in to Render**: https://dashboard.render.com
2. **Click "New +"** → Select **"Web Service"**
3. **Connect repository**:
   - Click "Connect account" (GitHub/GitLab)
   - Select your repository
   - Click "Connect"

### Step 4: Configure Service

Fill in the following settings:

| Setting | Value |
|---------|-------|
| **Name** | `ai-assistant-backend` (or your choice) |
| **Region** | Choose closest to your users |
| **Branch** | `main` (or your default branch) |
| **Root Directory** | Leave blank |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` (or `Starter $7/mo` for production) |

### Step 5: Add Environment Variables

In the **Environment Variables** section, add all variables from `.env.example`:

#### Required Variables

```bash
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
OPENAI_API_KEY=sk-...
```

#### Optional Variables

```bash
STORAGE_BUCKET_DOCS=documents
LOG_LEVEL=INFO
USE_JSON_LOGGING=true
```

**💡 Tip**: For production, set `USE_JSON_LOGGING=true` for better log aggregation.

### Step 6: Deploy

1. Click **"Create Web Service"**
2. Render will:
   - Clone your repository
   - Install dependencies
   - Start your application
   - Assign a URL: `https://your-service-name.onrender.com`

### Step 7: Verify Deployment

1. **Check health endpoint**: `https://your-service-name.onrender.com/health/db`
   - Should return: `{"ok": true, "count": 0}`

2. **Check logs** in Render dashboard:
   - Look for: `AI Assistant Backend starting up`
   - Verify no errors

3. **Test chat endpoint**: Use the widget demo or API client

### Step 8: Update Widget Configuration

Update your widget code with the new API URL:

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-service-name.onrender.com',
  websiteId: 'your-website-uuid',
  title: 'AI Assistant'
});
```

### Step 9: Configure CORS (Important!)

Update `backend/main.py` to allow your production domains:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://www.yourdomain.com",
        "https://yourdomain.com",
        # Add all your production domains
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Commit and push the changes - Render will auto-deploy.

## 🔄 Auto-Deployments

Render automatically deploys when you push to your main branch:

1. Push to main branch
2. Render detects the change
3. Rebuilds and redeploys
4. Zero-downtime deployment

## 📊 Monitoring on Render

### Health Checks

Render automatically monitors your service:
- **Default health check**: TCP connection to your port
- **Custom health check**: `/health/db` endpoint

To configure custom health check:
1. Go to service settings
2. Add health check path: `/health/db`

### Logs

View real-time logs:
1. Go to your service dashboard
2. Click **"Logs"** tab
3. Search, filter, and download logs

### Metrics

Monitor your service:
- CPU usage
- Memory usage
- Request count
- Response times

## 💰 Render Pricing

### Free Tier
- ✅ 750 hours/month (enough for one service)
- ✅ Sleeps after 15 minutes of inactivity
- ✅ Cold start: ~30 seconds
- ❌ Not suitable for production with strict uptime requirements

### Starter ($7/month)
- ✅ Always on (no sleep)
- ✅ Faster cold starts
- ✅ Better for production
- ✅ 400 hours/month included

### Pro ($25/month)
- ✅ Auto-scaling
- ✅ 2+ instances
- ✅ Priority support
- ✅ Better for high-traffic apps

**💡 Recommendation**: Start with Free tier for testing, upgrade to Starter for production.

## 🔧 Troubleshooting

### Service Won't Start

**Check logs for errors**:
```
FATAL: Configuration validation failed:
  - OPENAI_API_KEY is required
```

**Solution**: Verify all required environment variables are set.

### "Configuration validation failed"

**Cause**: Missing environment variables

**Solution**:
1. Go to service settings → Environment
2. Add missing variables
3. Click "Save Changes"
4. Service will auto-redeploy

### "Database unavailable"

**Causes**:
- Supabase URL incorrect
- Database not set up
- RLS policies preventing access

**Solutions**:
1. Verify `SUPABASE_URL` is correct
2. Run `database/schema.sql` in Supabase
3. Check Supabase logs for RLS errors

### CORS Errors in Widget

**Error in browser console**:
```
Access to fetch at 'https://your-service.onrender.com/chat/stream'
from origin 'https://yourdomain.com' has been blocked by CORS policy
```

**Solution**: Add your domain to CORS configuration in `backend/main.py`

### Service Sleeping (Free Tier)

**Issue**: Service takes 30 seconds to respond after inactivity

**Solutions**:
- Upgrade to Starter tier ($7/mo) for always-on
- Keep service warm with cron job (external ping every 10 minutes)
- Accept the sleep behavior for low-traffic apps

## 🌐 Custom Domain

### Add Custom Domain to Render

1. Go to service settings → **Custom Domain**
2. Add your domain: `api.yourdomain.com`
3. Add DNS records (Render provides instructions):
   ```
   Type: CNAME
   Name: api
   Value: your-service-name.onrender.com
   ```
4. Wait for DNS propagation (5-60 minutes)
5. Render auto-provisions SSL certificate

## 🔐 Security Best Practices

### Environment Variables
- ✅ Never commit `.env` to Git
- ✅ Use Render's encrypted environment variables
- ✅ Rotate keys regularly
- ✅ Use different keys for dev/staging/prod

### CORS Configuration
- ✅ Only allow specific domains in production
- ❌ Never use `allow_origins=["*"]` in production
- ✅ Update CORS when adding new domains

### Rate Limiting
- ✅ Monitor rate limit logs
- ✅ Adjust limits based on usage
- ✅ Consider adding IP allowlisting for admin endpoints

### HTTPS
- ✅ Always use HTTPS in production (Render provides free SSL)
- ✅ Enforce HTTPS in widget configuration
- ❌ Don't expose service role key to frontend

## 📈 Scaling

### When to Scale

Consider upgrading if you experience:
- Frequent cold starts impacting UX
- High traffic causing slow responses
- Memory/CPU limits reached
- Need for multiple regions

### Horizontal Scaling

Render supports auto-scaling on Pro plans:
1. Go to service settings → **Scaling**
2. Configure min/max instances
3. Set auto-scaling rules (CPU/memory thresholds)

### Database Scaling

Supabase also scales:
- **Free tier**: 500 MB database
- **Pro ($25/mo)**: 8 GB database
- **Enterprise**: Unlimited

Monitor database size:
```sql
SELECT pg_size_pretty(pg_database_size('postgres'));
```

## 🔄 Alternative Platforms

### Deploy to Railway

Similar to Render:
1. Connect GitHub repo
2. Add environment variables
3. Railway auto-detects Python and deploys
4. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

### Deploy to Fly.io

1. Install Fly CLI: `brew install flyctl`
2. Create `fly.toml` (see example below)
3. Deploy: `fly deploy`

### Deploy with Docker

See `Dockerfile` for containerized deployment to any platform.

## 📝 Deployment Checklist

Before going to production:

- [ ] Database schema deployed to Supabase
- [ ] All environment variables configured
- [ ] CORS updated with production domains
- [ ] Health checks passing
- [ ] Logs reviewed for errors
- [ ] Widget tested on production domain
- [ ] Custom domain configured (if applicable)
- [ ] SSL certificate active
- [ ] Monitoring set up
- [ ] Backup strategy defined
- [ ] Cost monitoring enabled
- [ ] Documentation updated

## 🆘 Support

If you encounter issues:
1. Check Render logs
2. Verify environment variables
3. Test health endpoints
4. Check Supabase logs
5. Review CORS configuration
6. Open GitHub issue

---

**You're all set!** 🎉

Your AI Assistant is now deployed and ready to chat with your users.
