"""Database connection management with fallback to in-memory storage."""

import asyncpg
from typing import AsyncGenerator
from config import config

# Try to import memory database for fallback
try:
    from database_memory import get_memory_db_connection, init_memory_database, InMemoryDatabase
    MEMORY_DB_AVAILABLE = True
except ImportError:
    MEMORY_DB_AVAILABLE = False

# Global flag to track if we're using memory database
_using_memory_db = False


async def get_db_connection():
    """Get a database connection, with fallback to in-memory storage."""
    global _using_memory_db
    
    try:
        if not _using_memory_db:
            # Try PostgreSQL first
            conn = await asyncpg.connect(config.DATABASE_URL)
            return conn
    except Exception as e:
        print(f"PostgreSQL connection failed: {e}")
        if MEMORY_DB_AVAILABLE:
            print("Falling back to in-memory database...")
            _using_memory_db = True
            return await get_memory_db_connection()
        else:
            raise Exception("No database available and memory fallback not available")
    
    # If we're using memory db, return it directly
    if _using_memory_db and MEMORY_DB_AVAILABLE:
        return await get_memory_db_connection()
    
    raise Exception("No database connection available")


async def get_db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Get a database connection pool."""
    global _using_memory_db
    
    try:
        if not _using_memory_db:
            pool = await asyncpg.create_pool(config.DATABASE_URL)
            try:
                yield pool
            finally:
                await pool.close()
    except Exception as e:
        print(f"PostgreSQL pool creation failed: {e}")
        if MEMORY_DB_AVAILABLE:
            print("Falling back to in-memory database...")
            _using_memory_db = True
            # Create a mock pool-like object
            mock_pool = InMemoryDatabase()
            try:
                yield mock_pool
            finally:
                pass
        else:
            raise Exception("No database available and memory fallback not available")


async def init_database():
    """Initialize database tables."""
    global _using_memory_db
    
    try:
        if not _using_memory_db:
            # Try PostgreSQL first
            conn = await asyncpg.connect(config.DATABASE_URL)
            try:
                # Create documents table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        filename TEXT NOT NULL,
                        mime_type TEXT,
                        total_chunks INTEGER DEFAULT 0,
                        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create document_chunks table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS document_chunks (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding VECTOR(1536),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes
                await conn.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id)")
                # Note: Vector index requires pgvector extension
                try:
                    await conn.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops)")
                except Exception:
                    print("Warning: Could not create vector index. Make sure pgvector extension is installed.")
                
                print("PostgreSQL database initialized successfully")
            finally:
                await conn.close()
    except Exception as e:
        print(f"PostgreSQL initialization failed: {e}")
        if MEMORY_DB_AVAILABLE:
            print("Falling back to in-memory database...")
            _using_memory_db = True
            await init_memory_database()
        else:
            raise Exception("No database available and memory fallback not available")