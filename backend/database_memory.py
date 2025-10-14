"""In-memory database for development without PostgreSQL."""

from typing import Dict, List, Optional, AsyncGenerator
import uuid
from datetime import datetime


class InMemoryDatabase:
    def __init__(self):
        self.documents: Dict[str, Dict] = {}
        self.chunks: Dict[str, Dict] = {}
        self.embeddings: Dict[str, List[float]] = {}
    
    async def init_tables(self):
        """Initialize in-memory tables (no-op for memory storage)."""
        print("Using in-memory database for development")
        pass
    
    async def execute(self, query: str, *params):
        """Execute SQL-like operations on in-memory storage."""
        if "INSERT INTO documents" in query:
            doc_id = params[0]
            self.documents[doc_id] = {
                'id': doc_id,
                'filename': params[1],
                'mime_type': params[2],
                'total_chunks': params[3],
                'uploaded_at': datetime.now()
            }
        
        elif "INSERT INTO document_chunks" in query:
            chunk_id = params[0]
            self.chunks[chunk_id] = {
                'id': chunk_id,
                'document_id': params[1],
                'chunk_index': params[2],
                'content': params[3],
                'created_at': datetime.now()
            }
            # Store embedding separately
            if len(params) > 4:
                self.embeddings[chunk_id] = params[4]
        
        elif "DELETE FROM document_chunks WHERE document_id" in query:
            doc_id = params[0]
            # Remove all chunks for this document
            chunks_to_remove = [chunk_id for chunk_id, chunk in self.chunks.items() 
                               if chunk['document_id'] == doc_id]
            for chunk_id in chunks_to_remove:
                del self.chunks[chunk_id]
                if chunk_id in self.embeddings:
                    del self.embeddings[chunk_id]
        
        elif "DELETE FROM documents WHERE id" in query:
            doc_id = params[0]
            if doc_id in self.documents:
                del self.documents[doc_id]
    
    async def fetch(self, query: str, *params):
        """Fetch data from in-memory storage."""
        if "SELECT c.id, c.document_id, c.chunk_index, c.content, c.embedding, d.filename" in query:
            limit = params[0] if params else 1000
            results = []
            count = 0
            
            for chunk_id, chunk_data in self.chunks.items():
                if count >= limit:
                    break
                
                doc_data = self.documents.get(chunk_data['document_id'], {})
                embedding = self.embeddings.get(chunk_id, [])
                
                results.append((
                    chunk_id,
                    chunk_data['document_id'],
                    chunk_data['chunk_index'],
                    chunk_data['content'],
                    embedding,
                    doc_data.get('filename', 'Unknown')
                ))
                count += 1
            
            return results
        
        elif "SELECT dc.content, dc.chunk_index, dc.document_id" in query and "distance" in query:
            # Handle similarity search query
            query_embedding = params[0] if params else []
            limit = params[1] if len(params) > 1 else 5
            
            # Calculate distances and sort by similarity
            results_with_distance = []
            
            for chunk_id, chunk_data in self.chunks.items():
                chunk_embedding = self.embeddings.get(chunk_id, [])
                
                if chunk_embedding and query_embedding:
                    # Calculate cosine distance (simple implementation)
                    distance = self._cosine_distance(query_embedding, chunk_embedding)
                else:
                    distance = 1.0  # Max distance if no embedding
                
                # Return as dictionary-like object that supports both dict and tuple access
                result = {
                    'content': chunk_data['content'],
                    'chunk_index': chunk_data['chunk_index'],
                    'document_id': chunk_data['document_id'],
                    'distance': distance
                }
                results_with_distance.append(result)
            
            # Sort by distance (ascending = most similar first)
            results_with_distance.sort(key=lambda x: x['distance'])
            
            # Return top results
            return results_with_distance[:limit]
        
        return []
    
    def _cosine_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine distance between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 1.0
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Calculate magnitudes
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 1.0
        
        # Cosine similarity = dot_product / (magnitude1 * magnitude2)
        cosine_similarity = dot_product / (magnitude1 * magnitude2)
        
        # Convert to distance (1 - similarity)
        return 1.0 - cosine_similarity
    
    def transaction(self):
        """Context manager for transactions (no-op for memory storage)."""
        return self
    
    def __aenter__(self):
        """Async context manager entry."""
        return self
    
    def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass


# Global in-memory database instance
_memory_db = InMemoryDatabase()


async def get_memory_db_connection():
    """Get in-memory database connection."""
    return _memory_db


async def init_memory_database():
    """Initialize in-memory database."""
    await _memory_db.init_tables()
    print("In-memory database initialized successfully")
