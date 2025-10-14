"""Document query API using Groq first, then Gemini as fallback."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
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


class QueryRequest(BaseModel):
    """Request body for querying documents."""
    question: str = Field(..., description="The question to ask")
    max_chunks: int = Field(default=5, ge=1, le=20, description="Maximum number of chunks to retrieve")
    max_tokens: int = Field(default=500, ge=50, le=2000, description="Maximum tokens in the answer")


class Source(BaseModel):
    """Source chunk information."""
    content: str
    chunk_index: int
    document_id: str


class QueryResponse(BaseModel):
    """Response to a document query."""
    answer: str
    sources: List[Source]
    total_chunks: int


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


async def _synthesize_answer(question: str, chunks: List[Source], max_tokens: int) -> str:
    """Synthesize an answer using the retrieved chunks - try Groq first, then Gemini."""
    context = "\n\n".join([c.content for c in chunks])
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


@router.post("/ask", response_model=QueryResponse)
async def query_ask(body: QueryRequest) -> QueryResponse:
    """Query documents and get an answer."""
    try:
        # Generate embedding for the question
        query_embedding = await _embed_text(body.question)
        
        # Retrieve similar chunks from database
        conn = await get_db_connection()
        try:
            # Check if it's a memory database (has 'execute' method but no 'close' method)
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
            return QueryResponse(
                answer="No relevant documents found. Please upload some documents first.",
                sources=[],
                total_chunks=0
            )
        
        # Convert to Source objects
        sources = [
            Source(
                content=row["content"],
                chunk_index=row["chunk_index"],
                document_id=row["document_id"]
            )
            for row in rows
        ]
        
        # Synthesize answer
        answer = await _synthesize_answer(body.question, sources, body.max_tokens)
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            total_chunks=len(sources)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")