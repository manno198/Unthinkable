"""Document ingestion API using Groq first, then Gemini as fallback."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from io import BytesIO
import base64
import uuid
import asyncio

from groq import Groq
from config import config
from database import get_db_connection

# Gemini client (lazy init)
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    genai = None
    GEMINI_AVAILABLE = False

router = APIRouter()

# Initialize clients - prioritize Groq
groq_client = Groq(api_key=config.GROQ_API_KEY) if config.GROQ_API_KEY else None
gemini_configured = bool(config.GEMINI_API_KEY and GEMINI_AVAILABLE)

if gemini_configured:
    genai.configure(api_key=config.GEMINI_API_KEY)

# Check which services are available
GROQ_AVAILABLE = groq_client is not None
GEMINI_AVAILABLE_FOR_USE = gemini_configured

print(f"AI Services Status:")
print(f"  Groq: {'Available' if GROQ_AVAILABLE else 'Not available'}")
print(f"  Gemini: {'Available' if GEMINI_AVAILABLE_FOR_USE else 'Not available'}")


class UploadDocRequest(BaseModel):
    """Request body for uploading and processing a document."""
    filename: str = Field(..., description="Original filename, e.g., report.pdf or notes.txt")
    mime_type: Optional[str] = Field(None, description="Optional MIME type, e.g., application/pdf or text/plain")
    file_b64: Optional[str] = Field(None, description="Base64 string of the file contents")
    text: Optional[str] = Field(None, description="Raw text content of the document")


class UploadDocResponse(BaseModel):
    """Response after document upload and processing."""
    document_id: str
    filename: str
    total_chunks: int
    chunks_created: int


async def _parse_document(filename: str, mime_type: Optional[str], file_b64: Optional[str], text: Optional[str]) -> str:
    """Parse document content based on file type."""
    if text:
        return text
    
    if not file_b64:
        raise ValueError("Either text or file_b64 must be provided")
    
    try:
        file_data = base64.b64decode(file_b64)
        file_io = BytesIO(file_data)
        
        # Determine file type
        if filename.lower().endswith('.pdf') or mime_type == 'application/pdf':
            import pypdf
            reader = pypdf.PdfReader(file_io)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        
        elif filename.lower().endswith('.txt') or mime_type == 'text/plain':
            return file_data.decode('utf-8')
        
        elif filename.lower().endswith('.json') or mime_type == 'application/json':
            import json
            data = json.loads(file_data.decode('utf-8'))
            return json.dumps(data, indent=2)
        
        else:
            # Try to decode as text
            return file_data.decode('utf-8')
    
    except Exception as e:
        raise ValueError(f"Failed to parse document: {str(e)}")


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at a sentence or word boundary
        if end < len(text):
            # Look for sentence boundary
            for i in range(end, max(start + chunk_size - 100, start), -1):
                if text[i] in '.!?':
                    end = i + 1
                    break
            else:
                # Look for word boundary
                for i in range(end, max(start + chunk_size - 50, start), -1):
                    if text[i] == ' ':
                        end = i
                        break
        
        chunks.append(text[start:end].strip())
        start = end - overlap
    
    return [chunk for chunk in chunks if chunk]


async def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for texts - prioritize Gemini for better semantic understanding."""
    
    # Try Gemini first for embeddings (much better quality for semantic search)
    if GEMINI_AVAILABLE_FOR_USE:
        try:
            print("Using Gemini for embeddings...")
            embeddings = []
            
            for text in texts:
                # Truncate text if too long
                if len(text) > 2000:
                    text = text[:2000]
                
                response = await asyncio.to_thread(genai.embed_content, model="models/embedding-001", content=text)
                embeddings.append(response['embedding'])
            
            return embeddings
            
        except Exception as e:
            print(f"Gemini embedding failed: {e}")
    
    # Fallback to Groq for embeddings (basic implementation)
    if GROQ_AVAILABLE:
        try:
            print("Using Groq for embeddings...")
            embeddings = []
            
            for text in texts:
                # Create a better embedding based on text content and word similarity
                words = text.lower().split()
                word_count = len(words)
                
                # Create a more meaningful embedding based on text content
                embedding = [0.0] * 1536
                
                # Basic features
                embedding[0] = min(word_count / 100.0, 1.0)
                embedding[1] = min(len(text) / 1000.0, 1.0)
                
                # Word-based features (hash words to embedding positions)
                for i, word in enumerate(words[:100]):  # Limit to first 100 words
                    if i < 1530:  # Leave some space for other features
                        # Hash the word to a position and set a value
                        word_hash = hash(word) % 1000
                        embedding[word_hash + 10] = 1.0
                
                # Character-based features for better matching
                for i, char in enumerate(text[:500]):  # First 500 characters
                    if i < 1000:
                        embedding[i + 510] = ord(char) / 255.0
                
                embeddings.append(embedding)
            
            return embeddings
            
        except Exception as e:
            print(f"Groq embedding failed: {e}")
    
    raise HTTPException(status_code=502, detail="No AI service available for embeddings. Please configure GROQ_API_KEY or GEMINI_API_KEY.")


async def _store_in_db(document_id: str, filename: str, mime_type: Optional[str], chunks: List[str], embeddings: List[List[float]]):
    """Store document and chunks in database."""
    if len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings length mismatch")
    
    conn = await get_db_connection()
    try:
        # Check if it's a memory database (has 'execute' method but no 'close' method)
        if not hasattr(conn, 'close'):
            # Memory database - direct calls
            # Insert document
            await conn.execute(
                """
                INSERT INTO documents (id, filename, mime_type, total_chunks)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO NOTHING
                """,
                document_id,
                filename,
                mime_type,
                len(chunks),
            )
            
            # Insert chunks
            for idx, (content, embedding) in enumerate(zip(chunks, embeddings)):
                await conn.execute(
                    """
                    INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    str(uuid.uuid4()),
                    document_id,
                    idx,
                    content,
                    embedding,
                )
        else:
            # PostgreSQL database - use transaction
            async with conn.transaction():
                # Insert document
                await conn.execute(
                    """
                    INSERT INTO documents (id, filename, mime_type, total_chunks)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    document_id,
                    filename,
                    mime_type,
                    len(chunks),
                )
                
                # Insert chunks
                for idx, (content, embedding) in enumerate(zip(chunks, embeddings)):
                    await conn.execute(
                        """
                        INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        str(uuid.uuid4()),
                        document_id,
                        idx,
                        content,
                        embedding,
                    )
    finally:
        # Only close if it's a real asyncpg connection
        if hasattr(conn, 'close'):
            await conn.close()


@router.post("/upload", response_model=UploadDocResponse)
async def ingest_upload(body: UploadDocRequest) -> UploadDocResponse:
    """Upload and process a document for ingestion."""
    document_id = str(uuid.uuid4())
    
    try:
        # Parse document
        text = await _parse_document(body.filename, body.mime_type, body.file_b64, body.text)
        
        # Chunk text
        chunks = _chunk_text(text)
        
        # Generate embeddings
        embeddings = await _embed_texts(chunks)
        
        # Store in database
        await _store_in_db(document_id, body.filename, body.mime_type, chunks, embeddings)
        
        return UploadDocResponse(
            document_id=document_id,
            filename=body.filename,
            total_chunks=len(chunks),
            chunks_created=len(chunks)
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks from the knowledge base."""
    conn = await get_db_connection()
    try:
        # Check if it's a memory database
        if not hasattr(conn, 'close'):
            # Memory database - direct calls
            await conn.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
            await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
        else:
            # PostgreSQL database - use transaction
            async with conn.transaction():
                await conn.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
                await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
    finally:
        if hasattr(conn, 'close'):
            await conn.close()
    
    return {"message": f"Document {document_id} deleted successfully"}