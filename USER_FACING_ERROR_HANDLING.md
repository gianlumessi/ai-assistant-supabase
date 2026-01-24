# User-Facing Error Handling

## Overview
Comprehensive error handling to ensure users **never** see raw exceptions, stack traces, or internal error details. All errors are converted to professional, user-friendly messages.

## Safety Mechanisms

### 1. Global Exception Handlers (main.py)
Added FastAPI exception handlers for all custom exception types:

| Exception Type | HTTP Status | User Message |
|---------------|-------------|--------------|
| `ConfigurationError` | 500 | "The service is not properly configured. Please contact support." |
| `DatabaseError` | 503 | "Unable to access the database. Please try again in a moment." |
| `EmbeddingError` | 503 | "Unable to process your request at this time. Please try again shortly." |
| `RetrievalError` | 500 | "We couldn't retrieve the necessary information. Please try again." |
| `StorageError` | 500/413 | "Unable to process the file. Please try again." (or "File too large" for size errors) |
| `IngestionError` | 422 | "The document could not be processed. Please check the file and try again." |
| `RateLimitError` | 429 | "Too many requests. Please try again shortly." |
| `AIAssistantError` | 500 | "An unexpected error occurred. Please try again." |
| `Exception` (catch-all) | 500 | "An unexpected error occurred. Our team has been notified." |

### 2. Error Response Format
All errors return a consistent JSON structure:
```json
{
  "error": "Brief error category",
  "message": "User-friendly explanation",
  "code": "ERROR_CODE_FOR_CLIENTS"
}
```

### 3. Sanitized Error Messages in Documents Router

**Before:**
```python
raise HTTPException(403, f"Storage upload failed: {str(e)}")  # Exposes internal error!
```

**After:**
```python
logger.error(f"Storage upload failed for {file.filename}: {str(e)}")
raise HTTPException(500, "Unable to upload file. Please try again.")
```

**Fixed locations:**
- Line ~161: Storage upload failures
- Line ~182: Database insert failures
- Line ~282: Storage deletion failures

### 4. Chat Router Error Handling
The chat router already had good error handling:
- Context retrieval failures → graceful fallback to empty context
- Message persistence failures → logged but don't break user experience
- Stream errors → user-friendly SSE error events
- All exceptions caught and converted to appropriate responses

## What Users See

### ✅ Good (User-Friendly)
```
{
  "error": "File too large",
  "message": "File exceeds 50 MB limit",
  "code": "FILE_TOO_LARGE"
}
```

### ❌ Bad (What We Prevent)
```python
Traceback (most recent call last):
  File "backend/services/storage.py", line 86
  supabase.storage.StorageException: Bucket 'documents' does not exist...
```

## Benefits

1. **Security**: Internal error details never exposed to users
2. **Professional**: Users see polished error messages
3. **Actionable**: Messages tell users what to do (e.g., "try again", "contact support")
4. **Consistent**: All errors follow the same format
5. **Debuggable**: Real errors still logged for developers
6. **Monitored**: All errors logged with context for investigation

## Error Flow

```
Service Layer                  Router/Endpoint                Global Handler
    |                               |                              |
    | raises StorageError           |                              |
    | --------------------------->  |                              |
    |                               | (no local handler)           |
    |                               | ---------------------------> |
    |                               |                              | Catches StorageError
    |                               |                              | Logs full details
    |                               |                              | Returns sanitized JSON
    |                               | <--------------------------- |
    |                               |                              |

User sees: {"error": "File operation failed", "message": "Unable to process the file..."}
Logs show: StorageError: Failed to upload file to bucket 'documents': permission denied...
```

## Testing User Experience

### Test Scenarios:
1. ✅ Missing environment variables → "Service temporarily unavailable"
2. ✅ Database connection failure → "Unable to access the database"
3. ✅ OpenAI API timeout → "Unable to process your request at this time"
4. ✅ File too large → "File exceeds 50 MB limit"
5. ✅ Rate limit exceeded → "Too many requests"
6. ✅ Unknown error → "An unexpected error occurred"

### None of these expose:
- Stack traces
- Internal error messages
- Database query details
- API keys or configuration
- File paths or system information

## Implementation Details

### Global Handlers (main.py)
```python
@app.exception_handler(StorageError)
async def storage_error_handler(request: Request, exc: StorageError):
    logger.error(f'Storage error: {exc.message}', extra={'details': exc.details})
    return JSONResponse(
        status_code=500,
        content={
            "error": "File operation failed",
            "message": "Unable to process the file. Please try again.",
            "code": "STORAGE_ERROR"
        }
    )
```

### Catch-All Handler (main.py)
```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Final safety net: prevents users from seeing raw Python stack traces."""
    logger.exception(f'Unhandled exception: {type(exc).__name__}: {str(exc)}')
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Our team has been notified.",
            "code": "UNHANDLED_EXCEPTION"
        }
    )
```

## Monitoring & Debugging

While users see sanitized messages, developers get full details:

**User sees:**
```json
{"error": "Unable to process document", "message": "The document could not be processed..."}
```

**Logs contain:**
```
2024-01-24 16:30:15 ERROR backend.services.ingest Ingestion error: Failed to generate embedding after 3 attempts
  Extra: {'details': {'document_id': 'abc-123', 'error': 'Rate limit exceeded', 'text_length': 5000}}
  Stack trace:
    File "backend/services/ingest.py", line 220, in ingest_text_into_chunks
      embedding = embed_text(chunk)
    ...
```

## Response Codes

| Code | Meaning | User Action |
|------|---------|-------------|
| 400 | Bad Request | Fix the request (validation error) |
| 401 | Unauthorized | Login or check credentials |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 413 | Payload Too Large | Use smaller file |
| 422 | Unprocessable | Fix data format |
| 429 | Too Many Requests | Wait and retry |
| 500 | Internal Error | Try again or contact support |
| 503 | Service Unavailable | Wait and retry (temporary) |

## Best Practices Applied

1. ✅ **Log the real error** - Full details in logs
2. ✅ **Return sanitized message** - User-friendly text
3. ✅ **Use appropriate status codes** - RESTful semantics
4. ✅ **Provide error codes** - For client-side handling
5. ✅ **Include actionable guidance** - Tell users what to do
6. ✅ **Never expose internals** - No stack traces, paths, or config
7. ✅ **Consistent format** - Same structure across all errors
8. ✅ **Fail gracefully** - Best-effort approach where possible

## Conclusion

Users now experience a **professional, controlled** error experience. Even when things break:
- No confusing error messages
- No scary stack traces
- No exposed internal details
- Clear guidance on what to do
- Consistent, polished responses

Developers still get all the debugging information they need in the logs.
