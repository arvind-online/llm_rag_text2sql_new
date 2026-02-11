"""RAG (Retrieval-Augmented Generation) agent."""

from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.prompts import ChatPromptTemplate
from sentence_transformers import SentenceTransformer

from config import settings, get_llm
from models import AgentResult


RAG_SYSTEM_PROMPT = """You are a professional knowledge assistant. Answer questions based on the provided context in a clear, professional manner suitable for end customers.

Context:
{context}

Guidelines:
1. Use ONLY the information from the context
2. Write in a clear, professional tone
3. Structure your answer with proper formatting (bullet points, paragraphs, etc.)
4. If the context doesn't contain enough information, say so politely
5. Do not mention "documents" or "context" - just provide the answer naturally
"""

RAG_USER_PROMPT = """Question: {query}

Provide a comprehensive, professional answer:"""


class RAGAgent:
    """Agent that performs retrieval-augmented generation."""
    
    def __init__(self):
        """Initialize the RAG agent."""
        self.llm = get_llm()
        
        # Initialize embedding model
        self.embedder = SentenceTransformer(settings.embedding_model)
        
        # Initialize ChromaDB
        persist_dir = settings.chroma_persist_dir_resolved
        persist_dir.mkdir(parents=True, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", RAG_SYSTEM_PROMPT),
            ("human", RAG_USER_PROMPT),
        ])
    
    def add_document(self, content: str, metadata: Optional[dict] = None) -> str:
        """
        Add a document to the vector store.
        
        Args:
            content: Document content
            metadata: Optional metadata
            
        Returns:
            Document ID
        """
        import uuid
        doc_id = str(uuid.uuid4())
        
        embedding = self.embedder.encode(content).tolist()
        
        self.collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata or {}]
        )
        
        return doc_id
    
    def retrieve(self, query: str, n_results: int = 3) -> list[dict]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of relevant documents with metadata
        """
        query_embedding = self.embedder.encode(query).tolist()
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
        
        documents = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                documents.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
        
        return documents
    
    def query(self, query: str) -> AgentResult:
        """
        Answer a query using RAG.
        
        Args:
            query: The user's question
            
        Returns:
            AgentResult with the answer and sources
        """
        # Retrieve relevant documents
        retrieved_docs = self.retrieve(query)
        
        if not retrieved_docs:
            return AgentResult(
                agent_type="rag",
                content="I don't have enough information in my knowledge base to answer this question.",
                sources=[],
                metadata={"retrieved_count": 0}
            )
        
        # Build context from retrieved documents
        context_parts = []
        sources = []
        for i, doc in enumerate(retrieved_docs, 1):
            context_parts.append(doc['content'])
            # Get clean source name from metadata
            source_info = doc.get('metadata', {}).get('source', f'Reference {i}')
            topic = doc.get('metadata', {}).get('topic', '')
            sources.append({
                "title": str(source_info),
                "topic": str(topic) if topic else None,
                "relevance": round((1 - doc.get('distance', 0)) * 100, 1)  # Convert distance to relevance %
            })
        
        context = "\n\n".join(context_parts)
        
        # Generate response
        chain = self.prompt | self.llm
        
        try:
            response = chain.invoke({
                "context": context,
                "query": query,
            })
            
            return AgentResult(
                agent_type="rag",
                content=response.content,
                sources=[s["title"] for s in sources],  # Simple list for backward compatibility
                metadata={
                    "retrieved_count": len(retrieved_docs),
                    "citations": sources  # Detailed citation info
                }
            )
        except Exception as e:
            return AgentResult(
                agent_type="rag",
                content="I encountered an error while processing your question. Please try again.",
                sources=[],
                metadata={"error": str(e)}
            )
