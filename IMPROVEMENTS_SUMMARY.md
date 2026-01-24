# Error Handling and Logging Improvements

## Overview
Comprehensive improvements to error handling, logging, and code reliability across the AI Assistant codebase.

## New Modules Created

### 1. `backend/core/exceptions.py`
Custom exception classes for better error categorization:
- `AIAssistantError` - Base exception class
- `EmbeddingError` - OpenAI embedding failures
- `RetrievalError` - Document/chunk retrieval failures
- `StorageError` - File storage operation failures
- `IngestionError` - Document ingestion/chunking failures
- `DatabaseError` - Database operation failures
- `ConfigurationError` - Configuration/environment validation errors
- `RateLimitError` - Rate limit exceeded errors

### 2. `backend/core/logging_config.py`
Structured logging with request tracking:
- `StructuredFormatter` - JSON logging for production
- `HumanReadableFormatter` - Human-friendly logs for development
- Context variables for request_id and website_id tracking
- `setup_logging()` - Centralized logging configuration
- `log_with_context()` - Log with additional context fields
- `set_request_context()` - Set request context for logging

### 3. `backend/core/config.py`
Environment variable validation:
- `Config` class for centralized configuration
- `validate_and_load()` - Validates all required env vars at startup
- Fails fast if required configuration is missing
- Support for optional logging configuration (LOG_LEVEL, USE_JSON_LOGGING)

## Enhanced Files

### `backend/main.py`
- ✅ Added environment validation at startup
- ✅ Configured structured logging
- ✅ Added error handling to all database operations:
  - `/health/db` - Database health check
  - `/debug/websites` - Website listing
  - `/chats` - Chat creation and listing
  - `/messages` - Message operations
- ✅ Better error messages for users
- ✅ Logging for all critical operations

### `backend/services/ingest.py`
- ✅ Comprehensive error handling for all operations
- ✅ Retry logic for OpenAI API calls (exponential backoff)
- ✅ Detailed logging throughout ingestion pipeline:
  - Document creation
  - Text chunking
  - Embedding generation
  - Database insertion
- ✅ Cleanup on failure (rollback document records)
- ✅ Performance tracking (duration, chunk counts)
- ✅ Better validation (empty text, invalid parameters)
- ✅ Partial success handling (continue on chunk failures)

### `backend/services/retrieval.py`
- ✅ Retry logic for query embedding generation
- ✅ Error handling for database queries
- ✅ Performance logging (query duration, result counts)
- ✅ Better embedding coercion with logging
- ✅ Invalid chunk tracking and warnings
- ✅ Detailed context gathering metrics:
  - Top score tracking
  - Document count
  - Context length
  - Processing duration

### `backend/services/storage.py`
- ✅ Comprehensive error handling for uploads
- ✅ File size validation (50 MB limit)
- ✅ Better bucket creation handling
- ✅ Detailed upload logging:
  - File metadata
  - Upload success/failure
  - SHA256 hash for verification
- ✅ Input validation (website_id, filename, data)
- ✅ Better error messages with context

### `backend/middleware/auth_middleware.py`
- ✅ Request ID generation for tracking
- ✅ Logging context setup (request_id, website_id)
- ✅ Authentication logging:
  - Anonymous requests
  - Successful authentication
  - JWT validation failures
  - Malformed headers
- ✅ Better error handling for edge cases

### `backend/core/supabase_client.py`
- ✅ Integration with new config system
- ✅ Better error messages
- ✅ Logging for client creation

### `backend/routers/chat.py`
- ✅ Updated to use new config system
- ✅ Import new exception classes
- ✅ Using new logger instance

## Key Improvements

### 1. Error Handling
- **Specific Exception Types**: Custom exceptions provide better error categorization
- **Retry Logic**: OpenAI API calls now retry with exponential backoff (3 attempts)
- **Graceful Degradation**: Failures don't crash the entire request
- **Cleanup on Failure**: Database records cleaned up when operations fail
- **Better Error Messages**: User-friendly messages without exposing internals

### 2. Logging
- **Structured Logging**: JSON format option for machine parsing
- **Request Tracking**: Unique request_id across all operations
- **Context Enrichment**: website_id, user_id tracked automatically
- **Performance Metrics**: Duration tracking for critical operations
- **Log Levels**: Proper use of DEBUG, INFO, WARNING, ERROR levels
- **Third-party Library Noise Reduction**: Set appropriate levels for httpx, openai, etc.

### 3. Configuration
- **Startup Validation**: Environment variables validated before accepting requests
- **Fail Fast**: Application won't start with missing configuration
- **Centralized Config**: Single source of truth for configuration
- **Better Error Messages**: Clear indication of missing variables

### 4. Reliability
- **Input Validation**: All functions validate inputs before processing
- **Partial Success Handling**: Some chunks failing doesn't fail entire ingestion
- **Idempotent Operations**: Bucket creation, etc. are idempotent
- **Resource Cleanup**: Proper cleanup on failures

## Configuration

### Environment Variables Required
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_ANON_KEY` - Supabase anonymous key
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key
- `OPENAI_API_KEY` - OpenAI API key

### Optional Configuration
- `LOG_LEVEL` - Logging level (default: INFO)
- `USE_JSON_LOGGING` - Use JSON logging format (default: false)
- `STORAGE_BUCKET_DOCS` - Storage bucket name (default: documents)
- `MAX_FILE_MB` - Max file size in MB (default: 10)
- `MAX_FILES_PER_QUERY` - Max files per query (default: 5)

## Usage

### Logging
```python
from backend.core.logging_config import get_logger, log_with_context

logger = get_logger(__name__)

# Simple logging
logger.info('Operation completed')

# Logging with context
log_with_context(logger, 'info', 'User action', user_id='123', action='upload')
```

### Custom Exceptions
```python
from backend.core.exceptions import EmbeddingError, StorageError

# Raise with context
raise EmbeddingError(
    'Failed to generate embedding',
    details={'text_length': 1000, 'error': str(e)}
)
```

### Configuration
```python
from backend.core.config import config

# Validate on startup (in main.py)
config.validate_and_load()

# Get configuration
api_key = config.get_openai_api_key()
url, anon_key, service_key = config.get_supabase_config()
```

## Testing Recommendations

1. **Test with missing environment variables** - Ensure proper error messages
2. **Test OpenAI API failures** - Verify retry logic works
3. **Test database connection issues** - Check error handling
4. **Test file upload failures** - Verify cleanup works
5. **Monitor logs in production** - Ensure useful information is captured
6. **Test partial failures** - E.g., some chunks fail during ingestion

## Future Improvements

1. **Metrics Collection**: Add Prometheus metrics for monitoring
2. **Distributed Tracing**: Add OpenTelemetry for request tracing
3. **Log Aggregation**: Consider ELK stack or similar for log analysis
4. **Circuit Breakers**: Add circuit breakers for external API calls
5. **Health Checks**: More comprehensive health checks
6. **Rate Limiting**: More sophisticated rate limiting with Redis
7. **Audit Logging**: Separate audit log for compliance

## Breaking Changes

None - All changes are backward compatible. Existing code continues to work.

## Migration Guide

No migration needed. The application will automatically use the new error handling and logging on startup.

To enable JSON logging, set environment variable:
```bash
USE_JSON_LOGGING=true
```

To change log level:
```bash
LOG_LEVEL=DEBUG  # or WARNING, ERROR, CRITICAL
```
