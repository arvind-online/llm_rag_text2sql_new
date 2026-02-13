"""FastAPI application for the LangGraph router pattern."""

from contextlib import asynccontextmanager
from typing import Any, Optional
from pathlib import Path
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document

from config import settings
from models import QueryRequest, QueryResponse, DocumentInput
from graph import run_query, get_rag_agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - no startup initialization required (lazy loading)."""
    yield
    # Cleanup on shutdown (if needed)


# Create the API app with all routes (no prefix needed)
api_app = FastAPI(
    title="LangGraph Router API",
    description="An intelligent query router using LangGraph that directs queries to RAG, Text2SQL, or hybrid processing.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for UI integration
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str


class DocumentResponse(BaseModel):
    """Response for document operations."""
    success: bool
    document_id: Optional[str] = None
    message: str
    filename: Optional[str] = None
    pages: Optional[int] = None


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from PDF file."""
    reader = PdfReader(file_path)
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text())
    return "\n\n".join(text_parts)


def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from DOCX file."""
    doc = Document(file_path)
    text_parts = []
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text_parts.append(paragraph.text)
    return "\n\n".join(text_parts)


@api_app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", version="1.0.0")


@api_app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """
    Process a user query through the LangGraph router.
    
    The router will automatically determine whether to use:
    - RAG (for document/knowledge queries)
    - Text2SQL (for data/database queries)
    - Hybrid (for queries needing both)
    """
    try:
        result = run_query(request.query, request.context)
        
        if result.get("final_response"):
            return result["final_response"]
        elif result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
        else:
            raise HTTPException(status_code=500, detail="No response generated")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@api_app.post("/documents", response_model=DocumentResponse)
async def add_document(document: DocumentInput):
    """
    Add a text document to the RAG knowledge base.
    
    The document will be embedded and stored in ChromaDB for retrieval.
    """
    try:
        rag_agent = get_rag_agent()
        doc_id = rag_agent.add_document(document.content, document.metadata)
        return DocumentResponse(
            success=True,
            document_id=doc_id,
            message="Document added successfully"
        )
    except Exception as e:
        return DocumentResponse(
            success=False,
            document_id=None,
            message=f"Failed to add document: {str(e)}"
        )


@api_app.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    source: Optional[str] = None,
    topic: Optional[str] = None
):
    """
    Upload a PDF or DOCX document to the RAG knowledge base.
    
    Supported formats:
    - PDF (.pdf)
    - Microsoft Word (.docx)
    
    The document will be parsed, chunked, and stored in ChromaDB.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in ['.pdf', '.docx']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_extension}. Only .pdf and .docx are supported."
        )
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        
        # Extract text based on file type
        if file_extension == '.pdf':
            text = extract_text_from_pdf(temp_path)
            reader = PdfReader(temp_path)
            page_count = len(reader.pages)
        elif file_extension == '.docx':
            text = extract_text_from_docx(temp_path)
            page_count = None  # DOCX doesn't have pages
        
        # Clean up temp file
        temp_path.unlink()
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="No text could be extracted from the document")
        
        # Prepare metadata
        metadata = {
            "source": source or file.filename,
            "filename": file.filename,
            "file_type": file_extension,
        }
        if topic:
            metadata["topic"] = topic
        if page_count:
            metadata["pages"] = page_count
        
        # Store in ChromaDB
        rag_agent = get_rag_agent()
        doc_id = rag_agent.add_document(text, metadata)
        
        return DocumentResponse(
            success=True,
            document_id=doc_id,
            message=f"Document '{file.filename}' uploaded and processed successfully",
            filename=file.filename,
            pages=page_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Clean up temp file if it exists
        if 'temp_path' in locals() and temp_path.exists():
            temp_path.unlink()
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process document: {str(e)}"
        )


@api_app.get("/config")
async def get_config():
    """Get current configuration (non-sensitive values only)."""
    return {
        "llm_model": settings.llm_model,
        "embedding_model": settings.embedding_model,
        "chroma_collection": settings.chroma_collection_name,
        "debug_mode": settings.show_sql_queries,
    }


# Mount static files (React UI) if build exists
# This must be placed after API routes to avoid conflict
ui_dist_path = Path("ui/dist")
if ui_dist_path.exists():
    print(f"INFO: Mounting UI from {ui_dist_path.absolute()}")
    try:
        from fastapi.staticfiles import StaticFiles
        api_app.mount("/", StaticFiles(directory=str(ui_dist_path), html=True), name="ui")
    except ImportError:
        print("ERROR: 'aiofiles' is not installed. Static file serving will fail.")
else:
    print(f"WARNING: UI build directory not found at {ui_dist_path.absolute()}")

# Create root app and mount api_app under the configured base path
root_app = FastAPI()
base_path = settings.base_url_path.rstrip('/') or '/'
if base_path == '/':
    # If base path is root, just use api_app directly
    root_app = api_app
else:
    # Mount api_app under the base path
    root_app.mount(base_path, api_app)
    print(f"INFO: API mounted at {base_path}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:root_app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
