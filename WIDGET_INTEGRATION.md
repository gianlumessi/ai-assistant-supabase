# Widget Integration Guide

Complete guide for embedding the AI Chat Widget on your website.

## 🎯 Quick Start (5 Minutes)

Add these two snippets to your HTML:

```html
<!-- 1. Include the widget script (before </body>) -->
<script src="https://your-api-domain.onrender.com/widget/chat-widget.js"></script>

<!-- 2. Initialize the widget -->
<script>
  window.AIChatWidget.init({
    apiBase: 'https://your-api-domain.onrender.com',
    websiteId: 'your-website-uuid-here'
  });
</script>
```

**That's it!** The chat widget will appear in the bottom-right corner.

## 📋 Prerequisites

1. **Website UUID**: Get this from your `websites` table in Supabase
2. **API URL**: Your deployed backend URL (e.g., from Render)
3. **Website domain**: Added to CORS configuration in backend

## 🔧 Configuration Options

### Basic Configuration

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',  // Required
  websiteId: 'uuid-from-supabase',                   // Required
  title: 'AI Assistant',                             // Optional
  subtitle: 'How can I help you?',                   // Optional
});
```

### Full Configuration

```javascript
window.AIChatWidget.init({
  // Required
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-website-uuid',

  // Optional: Session tracking (auto-generated if not provided)
  sessionId: null,  // Widget generates UUID automatically
  visitorId: null,  // Widget generates UUID automatically

  // Optional: Branding
  title: 'AI Assistant',
  subtitle: 'Ask me anything',

  // Optional: Theme customization
  theme: {
    primary: '#6D28D9',        // Primary purple
    primary2: '#7C3AED',       // Secondary purple
    border: 'rgba(17,24,39,.10)',
    shadow: '0 18px 50px rgba(17,24,39,.18)',
    bg: '#ffffff',
    text: '#111827',
    muted: 'rgba(17,24,39,.55)',
    botBubbleBg: 'rgba(17,24,39,.04)',
    panelBgFx1: 'rgba(124,58,237,.05)',
    panelBgFx2: 'rgba(99,102,241,.04)',
  },

  // Optional: Feedback callback
  onFeedback: function(data) {
    console.log('User feedback:', data);
    // data = { websiteId, sessionId, visitorId, rating: 'up'|'down', message, ts }

    // Send to your analytics
    // analytics.track('chat_feedback', data);
  }
});
```

## 🎨 Theme Customization

### Example: Blue Theme

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-uuid',
  title: 'Support Chat',
  theme: {
    primary: '#2563EB',     // Blue
    primary2: '#3B82F6',    // Light blue
    bg: '#ffffff',
    text: '#1F2937',
  }
});
```

### Example: Dark Theme

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-uuid',
  theme: {
    primary: '#8B5CF6',
    primary2: '#A78BFA',
    bg: '#1F2937',
    text: '#F9FAFB',
    muted: 'rgba(249,250,251,.65)',
    botBubbleBg: 'rgba(249,250,251,.08)',
  }
});
```

### Example: Brand Colors

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-uuid',
  title: 'Acme Support',
  theme: {
    primary: '#FF6B6B',      // Your brand primary
    primary2: '#FF8787',     // Your brand secondary
    bg: '#FFFFFF',
    text: '#2D3748',
  }
});
```

## 📱 Integration Examples

### Static HTML Website

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>My Website</title>
</head>
<body>
  <h1>Welcome to My Website</h1>
  <p>Your content here...</p>

  <!-- Add before closing </body> tag -->
  <script src="https://your-api-domain.onrender.com/widget/chat-widget.js"></script>
  <script>
    window.AIChatWidget.init({
      apiBase: 'https://your-api-domain.onrender.com',
      websiteId: 'your-website-uuid'
    });
  </script>
</body>
</html>
```

### React

```jsx
// components/ChatWidget.jsx
import { useEffect } from 'react';

export default function ChatWidget() {
  useEffect(() => {
    // Load the widget script
    const script = document.createElement('script');
    script.src = 'https://your-api-domain.onrender.com/widget/chat-widget.js';
    script.async = true;

    script.onload = () => {
      // Initialize when script loads
      if (window.AIChatWidget) {
        window.AIChatWidget.init({
          apiBase: 'https://your-api-domain.onrender.com',
          websiteId: 'your-website-uuid',
          title: 'Support Chat'
        });
      }
    };

    document.body.appendChild(script);

    // Cleanup
    return () => {
      document.body.removeChild(script);
    };
  }, []);

  return null; // Widget renders itself
}

// In your App.jsx or layout
import ChatWidget from './components/ChatWidget';

function App() {
  return (
    <div>
      <h1>My App</h1>
      {/* Your content */}
      <ChatWidget />
    </div>
  );
}
```

### Next.js

```jsx
// components/ChatWidget.tsx
'use client';

import { useEffect } from 'react';

export default function ChatWidget() {
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://your-api-domain.onrender.com/widget/chat-widget.js';
    script.async = true;

    script.onload = () => {
      if (typeof window !== 'undefined' && window.AIChatWidget) {
        window.AIChatWidget.init({
          apiBase: 'https://your-api-domain.onrender.com',
          websiteId: process.env.NEXT_PUBLIC_WEBSITE_ID!,
        });
      }
    };

    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, []);

  return null;
}

// In your layout.tsx
import ChatWidget from '@/components/ChatWidget';

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
        <ChatWidget />
      </body>
    </html>
  );
}
```

### Vue.js

```vue
<!-- components/ChatWidget.vue -->
<template>
  <div></div>
</template>

<script>
export default {
  name: 'ChatWidget',
  mounted() {
    const script = document.createElement('script');
    script.src = 'https://your-api-domain.onrender.com/widget/chat-widget.js';
    script.async = true;

    script.onload = () => {
      if (window.AIChatWidget) {
        window.AIChatWidget.init({
          apiBase: 'https://your-api-domain.onrender.com',
          websiteId: 'your-website-uuid'
        });
      }
    };

    document.body.appendChild(script);
  },
  beforeUnmount() {
    // Cleanup if needed
  }
}
</script>

<!-- In your App.vue or layout -->
<template>
  <div id="app">
    <router-view />
    <ChatWidget />
  </div>
</template>

<script>
import ChatWidget from './components/ChatWidget.vue';

export default {
  components: {
    ChatWidget
  }
}
</script>
```

### WordPress

```php
<!-- Add to your theme's footer.php or use a custom HTML block -->

<!-- Method 1: In footer.php (before </body>) -->
<script src="https://your-api-domain.onrender.com/widget/chat-widget.js"></script>
<script>
  window.AIChatWidget.init({
    apiBase: 'https://your-api-domain.onrender.com',
    websiteId: 'your-website-uuid'
  });
</script>

<!-- Method 2: Using wp_footer hook in functions.php -->
<?php
function add_ai_chat_widget() {
    ?>
    <script src="https://your-api-domain.onrender.com/widget/chat-widget.js"></script>
    <script>
      window.AIChatWidget.init({
        apiBase: 'https://your-api-domain.onrender.com',
        websiteId: 'your-website-uuid'
      });
    </script>
    <?php
}
add_action('wp_footer', 'add_ai_chat_widget');
?>
```

### Shopify

```liquid
<!-- In your theme.liquid, before </body> -->
<script src="https://your-api-domain.onrender.com/widget/chat-widget.js"></script>
<script>
  window.AIChatWidget.init({
    apiBase: 'https://your-api-domain.onrender.com',
    websiteId: 'your-website-uuid',
    title: 'Shop Assistant'
  });
</script>
```

## 🎮 Advanced Features

### Feedback Tracking

Capture user feedback (thumbs up/down):

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-uuid',

  onFeedback: function(feedback) {
    // feedback = {
    //   websiteId: 'uuid',
    //   sessionId: 'uuid',
    //   visitorId: 'uuid',
    //   rating: 'up' | 'down',
    //   message: 'last assistant message',
    //   ts: 1234567890
    // }

    // Send to your analytics
    fetch('/api/track-feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(feedback)
    });

    // Or use Google Analytics
    gtag('event', 'chat_feedback', {
      rating: feedback.rating,
      session_id: feedback.sessionId
    });
  }
});
```

### Custom Session/Visitor IDs

Persist session across page reloads:

```javascript
// Get or create session ID
let sessionId = localStorage.getItem('chat_session_id');
if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem('chat_session_id', sessionId);
}

// Get or create visitor ID
let visitorId = localStorage.getItem('visitor_id');
if (!visitorId) {
  visitorId = crypto.randomUUID();
  localStorage.setItem('visitor_id', visitorId);
}

window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-uuid',
  sessionId: sessionId,
  visitorId: visitorId
});
```

### Conditional Loading

Only show widget on certain pages:

```javascript
// Only on support pages
if (window.location.pathname.startsWith('/support')) {
  window.AIChatWidget.init({
    apiBase: 'https://your-api-domain.onrender.com',
    websiteId: 'your-uuid'
  });
}

// Not on checkout pages
if (!window.location.pathname.includes('/checkout')) {
  window.AIChatWidget.init({
    apiBase: 'https://your-api-domain.onrender.com',
    websiteId: 'your-uuid'
  });
}
```

## 🔍 Testing

### Test Locally

1. **Run backend locally**:
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```

2. **Open demo page**: `frontend/widget/demo.html`

3. **Configure**:
   - API base: `http://localhost:8000`
   - Website ID: Your test UUID

### Test in Production

1. Deploy backend to Render
2. Add test domain to CORS configuration
3. Test widget on staging site first
4. Verify:
   - Widget loads
   - Chat responses work
   - Feedback works (if enabled)
   - Styling looks correct

## 🐛 Troubleshooting

### Widget Not Appearing

**Check browser console for errors:**

```
Failed to load resource: net::ERR_BLOCKED_BY_CLIENT
```
**Cause**: Ad blocker blocking the widget
**Solution**: Whitelist your domain or self-host the widget

---

```
Access to fetch blocked by CORS policy
```
**Cause**: Domain not in CORS configuration
**Solution**: Add your domain to `backend/main.py` CORS settings

---

```
AIChatWidget is not defined
```
**Cause**: Script not loaded yet
**Solution**: Ensure script loads before `init()` call

### Widget Loads But No Responses

**Check Network tab:**

```
POST /chat/stream - Status: 401
```
**Cause**: Authentication issue
**Solution**: Check `websiteId` is correct UUID

---

```
POST /chat/stream - Status: 429
```
**Cause**: Rate limit exceeded
**Solution**: Wait a minute and try again

### Styling Issues

**Widget covered by other elements:**
```css
/* Add to your CSS */
#ai-chat-widget {
  z-index: 2147483000 !important;
}
```

**Widget too small/large:**
- Widget is fixed size (responsive)
- Customize via theme if needed

## 📊 Analytics Integration

### Google Analytics

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-uuid',

  onFeedback: function(data) {
    gtag('event', 'chat_feedback', {
      event_category: 'Chat',
      event_label: data.rating,
      value: data.rating === 'up' ? 1 : -1
    });
  }
});

// Track widget open (custom implementation)
document.addEventListener('click', function(e) {
  if (e.target.closest('#ai-chat-bubble')) {
    gtag('event', 'chat_opened', {
      event_category: 'Chat'
    });
  }
});
```

### Mixpanel

```javascript
window.AIChatWidget.init({
  apiBase: 'https://your-api-domain.onrender.com',
  websiteId: 'your-uuid',

  onFeedback: function(data) {
    mixpanel.track('Chat Feedback', {
      rating: data.rating,
      session_id: data.sessionId,
      visitor_id: data.visitorId
    });
  }
});
```

## 🔐 Security

### Best Practices

1. **Never expose service role key** - Only use in backend
2. **Use HTTPS** - Always load widget over HTTPS in production
3. **Validate websiteId** - Ensure it's a valid UUID from your database
4. **Rate limiting** - Backend has built-in rate limiting
5. **CORS** - Only allow your domains

### Content Security Policy (CSP)

If using CSP, allow:

```html
<meta http-equiv="Content-Security-Policy"
      content="
        script-src 'self' https://your-api-domain.onrender.com 'unsafe-inline';
        connect-src 'self' https://your-api-domain.onrender.com;
        style-src 'self' 'unsafe-inline';
      ">
```

## 📝 Checklist

Before going live:

- [ ] Website UUID created in Supabase
- [ ] Domain added to CORS configuration
- [ ] Widget script URL is correct
- [ ] `websiteId` is correct
- [ ] Widget loads on all target pages
- [ ] Chat responses work
- [ ] Styling matches your brand
- [ ] Tested on mobile devices
- [ ] Analytics tracking (if applicable)
- [ ] Feedback callback working (if enabled)

## 🆘 Support

If you need help:
1. Check browser console for errors
2. Check network tab for failed requests
3. Verify environment variables
4. Review CORS configuration
5. Check backend logs
6. Open GitHub issue

---

**You're ready to chat!** 💬

Your users can now get instant AI-powered support.
