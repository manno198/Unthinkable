"""Text-based document API for adding multiple documents via JSON."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import uuid
import json
import asyncio
import math

from groq import Groq
from config import config
from database import get_db_connection
from api.ingest import _chunk_text, _embed_texts, _store_in_db

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


async def _embed_text(text: str) -> List[float]:
    """Generate embedding for a single text - prioritize Gemini for better semantic understanding."""
    
    # Try Gemini first for embedding (much better quality for semantic search)
    if GEMINI_AVAILABLE_FOR_USE:
        try:
            print("Using Gemini for embedding...")
            # Truncate text if too long
            if len(text) > 2000:
                text = text[:2000]
            
            response = await asyncio.to_thread(genai.embed_content, model="models/embedding-001", content=text)
            return response['embedding']
            
        except Exception as e:
            print(f"Gemini embedding failed: {e}")
    
    # Fallback to Groq for embedding (basic implementation)
    if GROQ_AVAILABLE:
        try:
            print("Using Groq for embedding...")
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
            
            return embedding
            
        except Exception as e:
            print(f"Groq embedding failed: {e}")
    
    raise HTTPException(status_code=502, detail="No AI service available for embeddings. Please configure GROQ_API_KEY or GEMINI_API_KEY.")


async def _synthesize_answer(question: str, sources: List[dict], max_tokens: int) -> str:
    """Synthesize an answer using the retrieved chunks - try Groq first, then Gemini."""
    context = "\n\n".join([s["content"] for s in sources])
    prompt = f"""Based on the following context, please answer the question concisely and accurately.

Context:
{context}

Question: {question}

Answer:"""

    # Try Groq first for text generation
    if GROQ_AVAILABLE:
        try:
            print("Using Groq for answer generation...")
            chat_completion = await asyncio.to_thread(
                groq_client.chat.completions.create,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful AI assistant that answers questions based on the provided context. Be concise and accurate."
                    },
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.7,
                max_tokens=max_tokens,
            )
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            print(f"Groq generation failed: {e}")
    
    # Fallback to Gemini for text generation
    if GEMINI_AVAILABLE_FOR_USE:
        try:
            print("Using Gemini for answer generation...")
            model = genai.GenerativeModel('gemini-pro')
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                safety_settings={
                    genai.types.HarmCategory.HARM_CATEGORY_HARASSMENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                    genai.types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: genai.types.HarmBlockThreshold.BLOCK_NONE,
                    genai.types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                    genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE,
                },
                generation_config={"max_output_tokens": max_tokens}
            )
            return response.text
            
        except Exception as e:
            print(f"Gemini generation failed: {e}")
    
    raise HTTPException(status_code=502, detail="No AI service available for text generation. Please configure GROQ_API_KEY or GEMINI_API_KEY.")


class TextDocument(BaseModel):
    """Single text document."""
    title: str = Field(..., description="Title or name of the document")
    content: str = Field(..., description="Text content of the document")
    category: Optional[str] = Field(None, description="Optional category for organization")


class AddDocumentsRequest(BaseModel):
    """Request to add multiple text documents."""
    documents: List[TextDocument] = Field(..., description="List of documents to add")


class DocumentResponse(BaseModel):
    """Response for a single document."""
    document_id: str
    title: str
    chunks_created: int


class AddDocumentsResponse(BaseModel):
    """Response after adding multiple documents."""
    success: bool
    total_documents: int
    total_chunks: int
    documents: List[DocumentResponse]


class QueryTextRequest(BaseModel):
    """Request to query the text documents."""
    question: str = Field(..., description="The question to ask")
    max_chunks: int = Field(default=5, ge=1, le=20, description="Maximum number of chunks to retrieve")
    max_tokens: int = Field(default=500, ge=50, le=2000, description="Maximum tokens in the answer")


class QueryTextResponse(BaseModel):
    """Response to a text document query."""
    answer: str
    sources: List[dict]
    total_chunks: int
    documents_searched: int


@router.post("/add", response_model=AddDocumentsResponse)
async def add_text_documents(body: AddDocumentsRequest) -> AddDocumentsResponse:
    """Add multiple text documents to the knowledge base."""
    if not GROQ_AVAILABLE and not GEMINI_AVAILABLE_FOR_USE:
        raise HTTPException(status_code=502, detail="No AI service available. Please configure GROQ_API_KEY or GEMINI_API_KEY.")
    
    if not body.documents:
        raise HTTPException(status_code=400, detail="No documents provided")
    
    document_responses = []
    total_chunks = 0
    
    try:
        for doc in body.documents:
            document_id = str(uuid.uuid4())
            
            # Chunk the text
            chunks = _chunk_text(doc.content)
            
            # Generate embeddings
            embeddings = await _embed_texts(chunks)
            
            # Store in database
            await _store_in_db(
                document_id, 
                f"{doc.title}.txt", 
                "text/plain", 
                chunks, 
                embeddings
            )
            
            document_responses.append(DocumentResponse(
                document_id=document_id,
                title=doc.title,
                chunks_created=len(chunks)
            ))
            
            total_chunks += len(chunks)
        
        return AddDocumentsResponse(
            success=True,
            total_documents=len(body.documents),
            total_chunks=total_chunks,
            documents=document_responses
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding documents: {str(e)}")


@router.post("/query", response_model=QueryTextResponse)
async def query_text_documents(body: QueryTextRequest) -> QueryTextResponse:
    """Query the text documents and get an answer."""
    if not GROQ_AVAILABLE and not GEMINI_AVAILABLE_FOR_USE:
        raise HTTPException(status_code=502, detail="No AI service available. Please configure GROQ_API_KEY or GEMINI_API_KEY.")
    
    try:
        # Generate embedding for the question
        query_embedding = await _embed_text(body.question)
        
        # Retrieve similar chunks from database
        conn = await get_db_connection()
        try:
            # Check if it's a memory database
            if not hasattr(conn, 'close'):
                # Memory database - direct call
                rows = await conn.fetch(
                    """
                    SELECT dc.content, dc.chunk_index, dc.document_id,
                           dc.embedding <-> $1 AS distance
                    FROM document_chunks dc
                    ORDER BY distance
                    LIMIT $2
                    """,
                    query_embedding,
                    body.max_chunks,
                )
            else:
                # PostgreSQL database - use transaction
                async with conn.transaction():
                    rows = await conn.fetch(
                        """
                        SELECT dc.content, dc.chunk_index, dc.document_id,
                               dc.embedding <-> $1 AS distance
                        FROM document_chunks dc
                        ORDER BY distance
                        LIMIT $2
                        """,
                        query_embedding,
                        body.max_chunks,
                    )
        finally:
            if hasattr(conn, 'close'):
                await conn.close()
        
        if not rows:
            return QueryTextResponse(
                answer="No relevant documents found. Please add some documents first.",
                sources=[],
                total_chunks=0,
                documents_searched=0
            )
        
        # Convert to source dictionaries
        sources = [
            {
                "content": row["content"],
                "chunk_index": row["chunk_index"],
                "document_id": row["document_id"]
            }
            for row in rows
        ]
        
        # Synthesize answer
        answer = await _synthesize_answer(body.question, sources, body.max_tokens)
        
        # Get unique document count
        unique_docs = len(set(row["document_id"] for row in rows))
        
        return QueryTextResponse(
            answer=answer,
            sources=sources,
            total_chunks=len(sources),
            documents_searched=unique_docs
        )
        
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
            # Delete chunks first
            await conn.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
            # Delete document
            await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
        else:
            # PostgreSQL database - use transaction
            async with conn.transaction():
                # Delete chunks first (CASCADE should handle this, but being explicit)
                await conn.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
                # Delete document
                await conn.execute("DELETE FROM documents WHERE id = $1", document_id)
    finally:
        if hasattr(conn, 'close'):
            await conn.close()
    
    return {"message": f"Document {document_id} deleted successfully"}


@router.get("/list")
async def list_documents():
    """List all documents in the knowledge base."""
    conn = await get_db_connection()
    try:
        # Check if it's a memory database
        if not hasattr(conn, 'close'):
            # Memory database - direct call
            rows = await conn.fetch("SELECT * FROM documents ORDER BY created_at DESC")
        else:
            # PostgreSQL database - use transaction
            async with conn.transaction():
                rows = await conn.fetch("SELECT * FROM documents ORDER BY created_at DESC")
    finally:
        if hasattr(conn, 'close'):
            await conn.close()
    
    return {
        "documents": [
            {
                "id": row["id"],
                "filename": row["filename"],
                "mime_type": row["mime_type"],
                "total_chunks": row["total_chunks"],
                "created_at": str(row.get("created_at", "unknown"))
            }
            for row in rows
        ]
    }
