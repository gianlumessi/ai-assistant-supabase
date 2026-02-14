# AI Assistant Landing Page

Professional landing page for showcasing the AI chatbot to potential clients.

## 🎨 Features

- **Clear Value Proposition**: Instant FAQ answers with AI
- **Live Demo**: Embedded chatbot for visitors to try
- **Contact Options**: Email, calendar booking, and live chat
- **Fully Responsive**: Works on desktop, tablet, and mobile
- **Easy Customization**: CSS variables for colors and styling
- **Modern Design**: Dark theme with gradients and animations

## 🚀 Deployment

The landing page is automatically served at the root URL (`/`) of your Render deployment.

**Live URL**: `https://your-app.onrender.com/`

## 🎨 Customization

### Colors & Theme

Edit `theme.css` to customize the look:

```css
:root {
  /* Change these values */
  --primary-color: #3B82F6;      /* Main brand color */
  --primary-light: #60A5FA;      /* Lighter shade */
  --accent-color: #8B5CF6;       /* Accent purple */

  /* Background colors */
  --bg-dark: #0F172A;            /* Main background */
  --bg-card: #1E293B;            /* Card backgrounds */

  /* Text colors */
  --text-primary: #F8FAFC;       /* Main text */
  --text-secondary: #CBD5E1;     /* Secondary text */
}
```

**Pre-built themes** are included in comments - just uncomment to switch to light mode!

### Content

Edit `index.html` to update:

- **Hero Text** (lines 50-62): Change headline and description
- **Features** (lines 90-175): Add/remove feature cards
- **Steps** (lines 190-230): Modify "How it Works" steps
- **Contact Info** (lines 285-330): Update email, calendar link
- **Chatbot Widget** (line 450): Configure your website ID

### Chatbot Configuration

Update the widget initialization in `index.html`:

```javascript
window.AIChatWidget.init({
  apiBase: window.location.origin,
  websiteId: 'YOUR-DEMO-WEBSITE-UUID',  // ← Change this!
  title: 'AI Assistant Demo'
});
```

**Important**: Create a demo website in Supabase with sample FAQ data for visitors to try.

## 📁 File Structure

```
frontend/landing/
├── index.html      # Main landing page HTML
├── styles.css      # All page styles
├── theme.css       # Color theme configuration
└── README.md       # This file
```

## 🛠️ Development

### Test Locally

1. Start the backend:
```bash
uvicorn backend.main:app --reload
```

2. Visit: `http://localhost:8000/`

### Update Contact Form

The contact form currently just logs to console. To integrate with your backend:

Edit `index.html` (around line 460):

```javascript
document.getElementById('contactForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const formData = new FormData(this);
  const data = Object.fromEntries(formData);

  // Send to your backend endpoint
  fetch('/api/contact', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })
  .then(response => response.json())
  .then(data => {
    alert('Thank you! We\'ll get back to you soon.');
    this.reset();
  });
});
```

## 🔗 Links to Update

Before going live, update these placeholders:

1. **Email** (line 293): `contact@example.com` → your email
2. **Calendar** (line 311): `https://calendly.com/your-link` → your booking link
3. **Footer Links** (lines 420-440): Add your actual pages

## 📱 Responsive Breakpoints

The design is responsive with these breakpoints:

- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px

Test on all devices before launch!

## ✨ Sections Overview

1. **Hero**: Value proposition + CTA buttons + Stats
2. **Features**: 6 feature cards highlighting benefits
3. **How it Works**: 4-step process explanation
4. **Live Demo**: Embedded chatbot for trying
5. **Contact**: 3 contact options + form
6. **Footer**: Links and company info

## 🎯 SEO

The page includes basic SEO meta tags. Consider adding:

- Open Graph tags for social sharing
- Additional meta descriptions
- Structured data (JSON-LD)
- Google Analytics

## 🚀 Next Steps

1. **Customize Colors**: Edit `theme.css` with your brand colors
2. **Update Content**: Change text in `index.html` to match your offering
3. **Configure Chatbot**: Set correct `websiteId` with demo FAQ data
4. **Add Contact Info**: Update email and calendar links
5. **Test Everything**: Check all links, forms, and chatbot
6. **Deploy**: Push to master and Render auto-deploys

## 💡 Tips

- **Keep it Simple**: Don't over-customize - the design is already optimized
- **Test the Chatbot**: Make sure demo FAQ data is helpful and accurate
- **Mobile First**: Most visitors will be on mobile - test there first
- **Fast Loading**: Landing page is lightweight and loads quickly
- **Clear CTA**: Make it obvious how to get started

## 📞 Support

Questions about customization? Check:
- `theme.css` for color variables
- `styles.css` for layout and components
- `index.html` for content and structure

---

**Your landing page is ready to convert visitors into customers!** 🎉
