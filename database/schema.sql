-- =====================================================
-- AI Assistant with Supabase - Database Schema
-- =====================================================
-- This schema creates all necessary tables, indexes, and
-- Row Level Security (RLS) policies for the AI Assistant.
--
-- IMPORTANT: Run this in your Supabase SQL Editor
-- =====================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =====================================================
-- Tables
-- =====================================================

-- Websites (multi-tenant configuration)
CREATE TABLE IF NOT EXISTS websites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    settings JSONB DEFAULT '{}'::jsonb,
    -- Optional: owner_id for website ownership
    owner_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

COMMENT ON TABLE websites IS 'Multi-tenant website configuration';
COMMENT ON COLUMN websites.domain IS 'Website domain (e.g., example.com)';
COMMENT ON COLUMN websites.settings IS 'Website-specific settings (JSON)';


-- Chats (chat sessions scoped by website)
CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    website_id UUID NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
    title TEXT DEFAULT 'New Chat',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Optional: session_id and visitor_id for widget tracking
    session_id TEXT,
    visitor_id TEXT,
    metadata JSONB DEFAULT '{}'::jsonb
);

COMMENT ON TABLE chats IS 'Chat sessions scoped by website';
COMMENT ON COLUMN chats.session_id IS 'Widget session ID';
COMMENT ON COLUMN chats.visitor_id IS 'Widget visitor ID';


-- Messages (chat messages)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

COMMENT ON TABLE messages IS 'Chat messages (user and assistant)';
COMMENT ON COLUMN messages.role IS 'Message role: user, assistant, or system';


-- Documents (uploaded document metadata)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    website_id UUID NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER,
    storage_path TEXT NOT NULL,
    checksum_sha256 TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}'::jsonb
);

COMMENT ON TABLE documents IS 'Document metadata for uploaded files';
COMMENT ON COLUMN documents.status IS 'Document processing status';
COMMENT ON COLUMN documents.storage_path IS 'Path in Supabase Storage';


-- Document Chunks (text chunks with embeddings for RAG)
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    website_id UUID NOT NULL REFERENCES websites(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE(document_id, chunk_index)
);

COMMENT ON TABLE document_chunks IS 'Text chunks with vector embeddings for RAG';
COMMENT ON COLUMN document_chunks.embedding IS 'Vector embedding (1536 dimensions for text-embedding-3-small)';
COMMENT ON COLUMN document_chunks.chunk_index IS 'Chunk position in original document';


-- =====================================================
-- Indexes for Performance
-- =====================================================

-- Websites
CREATE INDEX IF NOT EXISTS idx_websites_domain ON websites(domain);
CREATE INDEX IF NOT EXISTS idx_websites_owner_id ON websites(owner_id);

-- Chats
CREATE INDEX IF NOT EXISTS idx_chats_website_id ON chats(website_id);
CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chats_session_id ON chats(session_id);
CREATE INDEX IF NOT EXISTS idx_chats_visitor_id ON chats(visitor_id);

-- Messages
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

-- Documents
CREATE INDEX IF NOT EXISTS idx_documents_website_id ON documents(website_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_created_by ON documents(created_by);

-- Document Chunks
CREATE INDEX IF NOT EXISTS idx_document_chunks_website_id ON document_chunks(website_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);

-- CRITICAL: Vector similarity search index (IVFFlat for fast approximate search)
-- Adjust lists parameter based on your dataset size:
-- - Small dataset (<1M rows): lists = rows / 1000
-- - Large dataset (>1M rows): lists = sqrt(rows)
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

COMMENT ON INDEX idx_document_chunks_embedding IS 'Vector similarity search index (cosine distance)';


-- =====================================================
-- Row Level Security (RLS) Policies
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE websites ENABLE ROW LEVEL SECURITY;
ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;


-- =====================================================
-- Websites Policies
-- =====================================================

-- Allow authenticated users to read websites they own
CREATE POLICY "Users can read their own websites"
ON websites FOR SELECT
TO authenticated
USING (owner_id = auth.uid());

-- Allow authenticated users to insert websites
CREATE POLICY "Users can create websites"
ON websites FOR INSERT
TO authenticated
WITH CHECK (owner_id = auth.uid());

-- Allow authenticated users to update their own websites
CREATE POLICY "Users can update their own websites"
ON websites FOR UPDATE
TO authenticated
USING (owner_id = auth.uid())
WITH CHECK (owner_id = auth.uid());

-- Allow authenticated users to delete their own websites
CREATE POLICY "Users can delete their own websites"
ON websites FOR DELETE
TO authenticated
USING (owner_id = auth.uid());

-- Allow service role full access to websites
CREATE POLICY "Service role has full access to websites"
ON websites FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- =====================================================
-- Chats Policies
-- =====================================================

-- Allow authenticated users to read chats from their websites
CREATE POLICY "Users can read chats from their websites"
ON chats FOR SELECT
TO authenticated
USING (
    website_id IN (
        SELECT id FROM websites WHERE owner_id = auth.uid()
    )
);

-- Allow service role full access to chats (for chatbot operations)
CREATE POLICY "Service role has full access to chats"
ON chats FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- =====================================================
-- Messages Policies
-- =====================================================

-- Allow authenticated users to read messages from their website's chats
CREATE POLICY "Users can read messages from their chats"
ON messages FOR SELECT
TO authenticated
USING (
    chat_id IN (
        SELECT c.id FROM chats c
        JOIN websites w ON c.website_id = w.id
        WHERE w.owner_id = auth.uid()
    )
);

-- Allow service role full access to messages (for chatbot operations)
CREATE POLICY "Service role has full access to messages"
ON messages FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- =====================================================
-- Documents Policies
-- =====================================================

-- Allow authenticated users to read documents from their websites
CREATE POLICY "Users can read documents from their websites"
ON documents FOR SELECT
TO authenticated
USING (
    website_id IN (
        SELECT id FROM websites WHERE owner_id = auth.uid()
    )
);

-- Allow authenticated users to insert documents to their websites
CREATE POLICY "Users can insert documents to their websites"
ON documents FOR INSERT
TO authenticated
WITH CHECK (
    website_id IN (
        SELECT id FROM websites WHERE owner_id = auth.uid()
    )
);

-- Allow authenticated users to update documents in their websites
CREATE POLICY "Users can update documents in their websites"
ON documents FOR UPDATE
TO authenticated
USING (
    website_id IN (
        SELECT id FROM websites WHERE owner_id = auth.uid()
    )
)
WITH CHECK (
    website_id IN (
        SELECT id FROM websites WHERE owner_id = auth.uid()
    )
);

-- Allow authenticated users to delete documents from their websites
CREATE POLICY "Users can delete documents from their websites"
ON documents FOR DELETE
TO authenticated
USING (
    website_id IN (
        SELECT id FROM websites WHERE owner_id = auth.uid()
    )
);

-- Allow service role full access to documents
CREATE POLICY "Service role has full access to documents"
ON documents FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- =====================================================
-- Document Chunks Policies
-- =====================================================

-- Allow authenticated users to read chunks from their websites
CREATE POLICY "Users can read chunks from their websites"
ON document_chunks FOR SELECT
TO authenticated
USING (
    website_id IN (
        SELECT id FROM websites WHERE owner_id = auth.uid()
    )
);

-- Allow service role full access to document chunks (for RAG operations)
CREATE POLICY "Service role has full access to document chunks"
ON document_chunks FOR ALL
TO service_role
USING (true)
WITH CHECK (true);


-- =====================================================
-- Functions & Triggers
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-update updated_at
CREATE TRIGGER update_websites_updated_at
    BEFORE UPDATE ON websites
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chats_updated_at
    BEFORE UPDATE ON chats
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- =====================================================
-- Vector Similarity Search Function
-- =====================================================

-- Function to search similar chunks using vector similarity
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding vector(1536),
    match_website_id UUID,
    match_threshold FLOAT DEFAULT 0.5,
    match_count INT DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    chunk_index INT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        document_chunks.id,
        document_chunks.document_id,
        document_chunks.content,
        document_chunks.chunk_index,
        1 - (document_chunks.embedding <=> query_embedding) AS similarity
    FROM document_chunks
    WHERE document_chunks.website_id = match_website_id
        AND 1 - (document_chunks.embedding <=> query_embedding) > match_threshold
    ORDER BY document_chunks.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION match_document_chunks IS 'Search for similar document chunks using cosine similarity';


-- =====================================================
-- Storage Bucket Setup
-- =====================================================

-- Note: Storage buckets must be created via Supabase dashboard or storage API
-- The backend code will attempt to create the "documents" bucket automatically

-- To manually create the bucket:
-- 1. Go to Supabase Dashboard > Storage
-- 2. Create a new bucket named "documents"
-- 3. Set it to Private (not public)
-- 4. Configure RLS policies for the bucket if needed


-- =====================================================
-- Seed Data (Optional)
-- =====================================================

-- Insert a test website (optional - for development)
-- Uncomment and modify as needed:

-- INSERT INTO websites (domain, owner_id)
-- VALUES ('example.com', (SELECT id FROM auth.users LIMIT 1))
-- ON CONFLICT (domain) DO NOTHING;


-- =====================================================
-- Verification Queries
-- =====================================================

-- Run these queries to verify the schema was created successfully:

-- Check all tables exist
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Check all indexes
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- Check RLS is enabled
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- Check RLS policies
SELECT schemaname, tablename, policyname, permissive, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- =====================================================
-- Schema Complete!
-- =====================================================
-- Next steps:
-- 1. Insert a website record
-- 2. Configure CORS in backend/main.py with your domain
-- 3. Upload and ingest documents
-- 4. Test the chat endpoint
-- =====================================================
