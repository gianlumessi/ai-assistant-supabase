# AI Assistant with Supabase Backend

A production-ready AI chatbot with RAG (Retrieval-Augmented Generation) capabilities, powered by OpenAI, Supabase, and FastAPI.

## 🌟 Features

- **AI-Powered Chat**: Stream-based responses using OpenAI GPT-4
- **RAG (Retrieval-Augmented Generation)**: Semantic search over your documents using vector embeddings
- **Multi-Tenancy**: Support for multiple websites with isolated data
- **Document Management**: Upload and process documents for knowledge base
- **Embeddable Widget**: Lightweight JavaScript widget for easy integration
- **Authentication**: JWT-based authentication with Supabase
- **Rate Limiting**: Built-in protection against abuse
- **Comprehensive Error Handling**: User-friendly error messages with detailed logging
- **Production-Ready**: Structured logging, global exception handlers, retry logic

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Supabase account (free tier works)
- OpenAI API key

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd ai-assistant-supabase
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key
- `OPENAI_API_KEY`: Your OpenAI API key

### 3. Set Up Database

Run the SQL schema in your Supabase SQL Editor:

```bash
# See database/schema.sql for the complete schema
```

Execute the contents of `database/schema.sql` in your Supabase project.

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run Locally

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 6. Test the Widget

Open `frontend/widget/demo.html` in your browser and configure:
- API base: `http://localhost:8000`
- Website ID: Use a UUID from your `websites` table

## 📁 Project Structure

```
ai-assistant-supabase/
├── backend/
│   ├── core/               # Core utilities and configuration
│   │   ├── config.py       # Environment validation
│   │   ├── exceptions.py   # Custom exception classes
│   │   ├── logging_config.py # Structured logging
│   │   ├── supabase_client.py
│   │   ├── deps.py
│   │   ├── db.py
│   │   └── website.py
│   ├── middleware/         # Request middleware
│   │   └── auth_middleware.py
│   ├── routers/           # API endpoints
│   │   ├── chat.py        # Chat streaming endpoint
│   │   └── documents.py   # Document management
│   ├── services/          # Business logic
│   │   ├── ingest.py      # Document ingestion & chunking
│   │   ├── retrieval.py   # RAG context gathering
│   │   ├── storage.py     # File storage
│   │   └── security.py    # Authentication
│   ├── schemas/           # Pydantic models
│   │   └── documents.py
│   ├── scripts/           # Utility scripts
│   │   └── ingest_one_file.py
│   └── main.py           # FastAPI app entry point
├── frontend/
│   └── widget/
│       ├── chat-widget.js  # Embeddable chat widget
│       └── demo.html       # Widget demo page
├── database/
│   └── schema.sql         # Database schema & RLS policies
├── .env.example          # Environment variables template
├── requirements.txt      # Python dependencies
└── README.md
```

## 🗄️ Database Schema

The application uses the following tables:

- **websites**: Multi-tenant configuration (domain, settings)
- **chats**: Chat sessions scoped by website
- **messages**: Chat messages (user & assistant)
- **documents**: Uploaded document metadata
- **document_chunks**: Text chunks with vector embeddings for RAG

See `database/schema.sql` for complete schema with RLS policies.

## 🔐 Security

- **Row Level Security (RLS)**: All tables use RLS policies for data isolation
- **JWT Authentication**: Supabase JWT tokens for user authentication
- **Service Role Access**: Backend uses service role for privileged operations
- **Error Sanitization**: Internal errors never exposed to users
- **Input Validation**: All inputs validated before processing
- **Rate Limiting**: IP-based rate limiting on chat endpoint

## 📡 API Endpoints

### Chat
- `POST /chat/stream` - Stream chat responses with RAG context (SSE)

### Chats & Messages
- `POST /chats` - Create a new chat
- `GET /chats` - List chats for a website
- `POST /messages` - Add a message
- `GET /messages?chat_id={id}` - List messages for a chat

### Documents (if enabled)
- `POST /documents` - Upload a document
- `GET /documents` - List documents
- `GET /documents/{id}/download` - Get signed download URL
- `DELETE /documents/{id}` - Delete a document

### Health
- `GET /` - Basic health check
- `GET /health/db` - Database health check

## 🎨 Widget Integration

Add the chat widget to any website:

```html
<!-- Include the widget script -->
<script src="https://your-domain.com/widget/chat-widget.js"></script>

<!-- Initialize the widget -->
<script>
  window.AIChatWidget.init({
    apiBase: 'https://your-api-domain.com',
    websiteId: 'your-website-uuid',
    title: 'AI Assistant',
    theme: {
      primary: '#6D28D9',
      // ... customize colors
    }
  });
</script>
```

See `WIDGET_INTEGRATION.md` for complete integration guide.

## 🚢 Deployment

### Deploy to Render

1. **Create a new Web Service** on Render
2. **Connect your repository**
3. **Configure the service**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. **Add environment variables** from `.env.example`
5. **Deploy!**

See `DEPLOYMENT.md` for detailed deployment instructions.

### Deploy to Other Platforms

The application is containerized-ready. See the Dockerfile for Docker deployment.

## 📊 Logging

The application uses structured logging with request tracking:

```python
# Development: Human-readable logs
LOG_LEVEL=INFO
USE_JSON_LOGGING=false

# Production: JSON logs for aggregation
LOG_LEVEL=INFO
USE_JSON_LOGGING=true
```

All requests are tracked with unique request IDs across the entire pipeline.

## 🛠️ Development

### Running Tests

```bash
# Run all tests (when tests are added)
pytest

# Run with coverage
pytest --cov=backend
```

### Adding a New Website

Insert a row into the `websites` table:

```sql
INSERT INTO websites (domain) VALUES ('example.com');
```

Use the generated UUID as your `websiteId` in the widget.

### Ingesting Documents

Use the ingestion script for testing:

```bash
# Edit backend/scripts/ingest_one_file.py with your website_id
python -m backend.scripts.ingest_one_file
```

Or use the documents API endpoint (if enabled).

## 📈 Monitoring

- **Logs**: All operations logged with request tracking
- **Health Checks**: `/health/db` for database connectivity
- **Error Tracking**: Global exception handlers catch all errors
- **Metrics**: OpenAI usage tracked in chat responses

## 💰 Cost Estimation

**OpenAI API Costs** (approximate):
- Embeddings (text-embedding-3-small): ~$0.0001 per 1K tokens
- Chat (gpt-4o-mini): ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- Typical chat message: ~$0.001 - $0.01

**Supabase** (free tier):
- 500 MB database
- 1 GB file storage
- 2 GB bandwidth

**Render** (free tier):
- 750 hours/month
- Sleeps after 15 min inactivity
- Upgrade to $7/mo for always-on

## 🐛 Troubleshooting

### "Configuration validation failed"
- Check that all required env vars are set in `.env`
- Ensure no trailing spaces in values

### "Database unavailable"
- Verify `SUPABASE_URL` is correct
- Check Supabase project is not paused
- Verify RLS policies are created

### "Unable to process your request" (Embedding errors)
- Verify `OPENAI_API_KEY` is valid
- Check OpenAI account has credits
- Monitor rate limits

### Widget not appearing
- Check browser console for errors
- Verify `apiBase` URL is correct and accessible
- Ensure CORS is configured correctly

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please open an issue or PR.

## 📧 Support

For issues or questions, please open a GitHub issue.

---

Built with ❤️ using FastAPI, Supabase, and OpenAI
