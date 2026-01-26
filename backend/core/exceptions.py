"""Custom exception classes for better error categorization and handling."""

from typing import Optional


class AIAssistantError(Exception):
    """Base exception for all AI Assistant errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EmbeddingError(AIAssistantError):
    """Raised when OpenAI embedding generation fails."""
    pass


class RetrievalError(AIAssistantError):
    """Raised when document/chunk retrieval fails."""
    pass


class StorageError(AIAssistantError):
    """Raised when file storage operations fail."""
    pass


class IngestionError(AIAssistantError):
    """Raised when document ingestion/chunking fails."""
    pass


class DatabaseError(AIAssistantError):
    """Raised when database operations fail."""
    pass


class ConfigurationError(AIAssistantError):
    """Raised when configuration or environment variables are invalid."""
    pass


class RateLimitError(AIAssistantError):
    """Raised when rate limits are exceeded."""
    pass
