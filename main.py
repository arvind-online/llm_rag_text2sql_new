"""FastAPI application for the LangGraph router pattern."""

from contextlib import asynccontextmanager
from typing import Any, Optional, List
from pathlib import Path
import tempfile
import httpx
import os
import traceback

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document

from config import settings, get_llm
from models import QueryRequest, QueryResponse, DocumentInput
from graph import run_query, get_rag_agent, reset_agents


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


class ProviderInfo(BaseModel):
    """Provider information."""
    id: str
    name: str
    available: bool
    error: Optional[str] = None
    current_model: Optional[str] = None


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    name: str
    description: Optional[str] = None


class ProviderSwitchRequest(BaseModel):
    """Request to switch provider/model."""
    provider: str
    model: str


class ProviderSwitchResponse(BaseModel):
    """Response from provider switch."""
    success: bool
    provider: str
    model: str
    message: str


class CurrentProviderResponse(BaseModel):
    """Current provider info."""
    provider: str
    model: str
    provider_name: str


# ---- Static model lists ----

GROQ_MODELS = [
    ModelInfo(id="llama-3.3-70b-versatile", name="Llama 3.3 70B Versatile", description="Meta's latest, most capable open model"),
    ModelInfo(id="llama-3.1-8b-instant", name="Llama 3.1 8B Instant", description="Fast & lightweight"),
    ModelInfo(id="llama-3.2-90b-vision-preview", name="Llama 3.2 90B Vision", description="Multimodal vision model"),
    ModelInfo(id="llama-3.2-11b-vision-preview", name="Llama 3.2 11B Vision", description="Compact vision model"),
    ModelInfo(id="llama-3.2-3b-preview", name="Llama 3.2 3B", description="Ultra-lightweight model"),
    ModelInfo(id="llama-3.2-1b-preview", name="Llama 3.2 1B", description="Smallest Llama model"),
    ModelInfo(id="gemma2-9b-it", name="Gemma 2 9B IT", description="Google's efficient model"),
    ModelInfo(id="mixtral-8x7b-32768", name="Mixtral 8x7B", description="Mistral's MoE model"),
    ModelInfo(id="deepseek-r1-distill-llama-70b", name="DeepSeek R1 Distill 70B", description="Reasoning-focused model"),
]

BEDROCK_MODELS = [
    ModelInfo(id="anthropic.claude-3-haiku-20240307-v1:0", name="Claude 3 Haiku", description="Fast & affordable"),
    ModelInfo(id="anthropic.claude-3-sonnet-20240229-v1:0", name="Claude 3 Sonnet", description="Balanced performance"),
    ModelInfo(id="anthropic.claude-3-5-sonnet-20241022-v2:0", name="Claude 3.5 Sonnet v2", description="Best overall performance"),
    ModelInfo(id="anthropic.claude-3-5-haiku-20241022-v1:0", name="Claude 3.5 Haiku", description="Next-gen fast model"),
    ModelInfo(id="amazon.titan-text-express-v1", name="Titan Text Express", description="Amazon's general purpose"),
    ModelInfo(id="amazon.titan-text-lite-v1", name="Titan Text Lite", description="Amazon's lightweight model"),
    ModelInfo(id="meta.llama3-70b-instruct-v1:0", name="Llama 3 70B (Bedrock)", description="Meta via Bedrock"),
    ModelInfo(id="meta.llama3-8b-instruct-v1:0", name="Llama 3 8B (Bedrock)", description="Meta lightweight via Bedrock"),
    ModelInfo(id="mistral.mixtral-8x7b-instruct-v0:1", name="Mixtral 8x7B (Bedrock)", description="Mistral via Bedrock"),
]

PROVIDER_NAMES = {
    "groq": "GROQ",
    "ollama": "Ollama",
    "bedrock": "AWS Bedrock",
}


def _get_current_model_for_provider(provider: str) -> str:
    """Get the currently configured model for a provider."""
    if provider == "groq":
        return settings.llm_model
    elif provider == "ollama":
        return settings.ollama_model
    elif provider == "bedrock":
        return settings.bedrock_model_id
    return ""


def _check_provider_available(provider: str) -> tuple[bool, Optional[str]]:
    """Check if a provider is available based on env config. Returns (available, error_msg)."""
    if provider == "groq":
        if not settings.groq_api_key:
            return False, "GROQ_API_KEY not set in environment"
        return True, None
    elif provider == "ollama":
        # Just check config exists; actual connectivity checked on model fetch
        return True, None
    elif provider == "bedrock":
        if not settings.aws_region:
            return False, "AWS_REGION not set in environment"
        # Need either profile, bearer token, or env credentials
        has_auth = bool(
            settings.aws_profile
            or settings.aws_bearer_token_bedrock
            or os.environ.get("AWS_ACCESS_KEY_ID")
        )
        if not has_auth:
            return False, "No AWS credentials found (AWS_PROFILE, AWS_BEARER_TOKEN_BEDROCK, or AWS_ACCESS_KEY_ID not set)"
        return True, None
    return False, f"Unknown provider: {provider}"


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
        "llm_provider": settings.llm_provider,
        "llm_model": _get_current_model_for_provider(settings.llm_provider),
        "embedding_model": settings.embedding_model,
        "chroma_collection": settings.chroma_collection_name,
        "debug_mode": settings.show_sql_queries,
    }


@api_app.get("/providers/current", response_model=CurrentProviderResponse)
async def get_current_provider():
    """Get the current active provider and model."""
    provider = settings.llm_provider.lower()
    return CurrentProviderResponse(
        provider=provider,
        model=_get_current_model_for_provider(provider),
        provider_name=PROVIDER_NAMES.get(provider, provider.upper()),
    )


@api_app.get("/providers", response_model=List[ProviderInfo])
async def list_providers():
    """List available LLM providers with their status."""
    providers = []
    for pid, pname in PROVIDER_NAMES.items():
        available, error = _check_provider_available(pid)
        providers.append(ProviderInfo(
            id=pid,
            name=pname,
            available=available,
            error=error,
            current_model=_get_current_model_for_provider(pid),
        ))
    return providers


@api_app.get("/providers/{provider}/models", response_model=List[ModelInfo])
async def get_provider_models(provider: str):
    """Get available models for a provider. For Ollama, queries the local API."""
    provider = provider.lower()

    if provider == "groq":
        return GROQ_MODELS

    elif provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    size_gb = ""
                    if m.get("size"):
                        size_gb = f" ({m['size'] / 1e9:.1f} GB)"
                    models.append(ModelInfo(
                        id=name,
                        name=name,
                        description=f"{m.get('details', {}).get('family', 'Unknown family')}{size_gb}",
                    ))
                if not models:
                    raise HTTPException(status_code=404, detail="No models found in Ollama. Pull a model first with: ollama pull <model>")
                return models
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail=f"Cannot connect to Ollama at {settings.ollama_base_url}. Is it running?")
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=502, detail=f"Ollama API error: {e.response.status_code}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error fetching Ollama models: {str(e)}")

    elif provider == "bedrock":
        return BEDROCK_MODELS

    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")


@api_app.post("/providers/switch", response_model=ProviderSwitchResponse)
async def switch_provider(request: ProviderSwitchRequest):
    """
    Switch the active LLM provider and model at runtime.
    Validates connectivity before committing. Rolls back on failure.
    """
    provider = request.provider.lower()
    model = request.model

    if provider not in PROVIDER_NAMES:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Check provider availability
    available, error = _check_provider_available(provider)
    if not available:
        raise HTTPException(status_code=400, detail=error)

    # Save previous state for rollback
    prev_provider = settings.llm_provider
    prev_groq_model = settings.llm_model
    prev_ollama_model = settings.ollama_model
    prev_bedrock_model = settings.bedrock_model_id

    try:
        # Apply new settings
        settings.llm_provider = provider
        if provider == "groq":
            settings.llm_model = model
        elif provider == "ollama":
            settings.ollama_model = model
        elif provider == "bedrock":
            settings.bedrock_model_id = model

        # Validate by creating the LLM and doing a test invocation
        llm = get_llm()
        # Quick test: invoke with a minimal prompt
        test_response = llm.invoke("Reply with OK")
        if not test_response:
            raise Exception("Empty response from LLM")

        # Success — reset the lazy-loaded agents so they pick up the new LLM
        reset_agents()

        return ProviderSwitchResponse(
            success=True,
            provider=provider,
            model=model,
            message=f"Successfully switched to {PROVIDER_NAMES[provider]} / {model}",
        )

    except Exception as e:
        # Rollback
        settings.llm_provider = prev_provider
        settings.llm_model = prev_groq_model
        settings.ollama_model = prev_ollama_model
        settings.bedrock_model_id = prev_bedrock_model

        error_detail = str(e)
        if "AuthenticationError" in error_detail or "401" in error_detail:
            error_detail = f"Authentication failed for {PROVIDER_NAMES.get(provider, provider)}. Check your API key."
        elif "ConnectError" in error_detail or "Connection" in error_detail:
            error_detail = f"Could not connect to {PROVIDER_NAMES.get(provider, provider)}. Check if the service is running."

        raise HTTPException(
            status_code=400,
            detail=f"Failed to switch to {PROVIDER_NAMES.get(provider, provider)} / {model}: {error_detail}",
        )


# ---- API Key Management ----

class ProviderKeyInfo(BaseModel):
    """Key info for a provider (masked for security)."""
    provider: str
    provider_name: str
    key_label: str
    key_hint: str  # e.g. "GROQ_API_KEY"
    masked_value: str  # e.g. "••••••••gdHl"
    is_set: bool


class UpdateKeyRequest(BaseModel):
    """Request to update a provider's API key."""
    provider: str
    key_value: str


class UpdateKeyResponse(BaseModel):
    """Response from key update."""
    success: bool
    provider: str
    message: str


def _mask_key(value: str) -> str:
    """Mask a key, showing only last 4 characters."""
    if not value:
        return ""
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * min(len(value) - 4, 12) + value[-4:]


@api_app.get("/providers/keys", response_model=List[ProviderKeyInfo])
async def get_provider_keys():
    """Get masked API keys for all providers."""
    return [
        ProviderKeyInfo(
            provider="groq",
            provider_name="GROQ",
            key_label="API Key",
            key_hint="GROQ_API_KEY",
            masked_value=_mask_key(settings.groq_api_key),
            is_set=bool(settings.groq_api_key),
        ),
        ProviderKeyInfo(
            provider="ollama",
            provider_name="Ollama",
            key_label="Base URL",
            key_hint="OLLAMA_BASE_URL",
            masked_value=settings.ollama_base_url,  # URL is not secret
            is_set=bool(settings.ollama_base_url),
        ),
        ProviderKeyInfo(
            provider="bedrock",
            provider_name="AWS Bedrock",
            key_label="Bearer Token",
            key_hint="AWS_BEARER_TOKEN_BEDROCK",
            masked_value=_mask_key(settings.aws_bearer_token_bedrock),
            is_set=bool(settings.aws_bearer_token_bedrock),
        ),
    ]


@api_app.post("/providers/keys", response_model=UpdateKeyResponse)
async def update_provider_key(request: UpdateKeyRequest):
    """Update a provider's API key/token at runtime."""
    provider = request.provider.lower()
    key_value = request.key_value.strip()

    if not key_value:
        raise HTTPException(status_code=400, detail="Key value cannot be empty")

    try:
        if provider == "groq":
            settings.groq_api_key = key_value
            # Reset agents so new key is used
            reset_agents()
            return UpdateKeyResponse(
                success=True,
                provider=provider,
                message="GROQ API key updated successfully",
            )
        elif provider == "ollama":
            settings.ollama_base_url = key_value
            reset_agents()
            return UpdateKeyResponse(
                success=True,
                provider=provider,
                message=f"Ollama base URL updated to {key_value}",
            )
        elif provider == "bedrock":
            settings.aws_bearer_token_bedrock = key_value
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = key_value
            reset_agents()
            return UpdateKeyResponse(
                success=True,
                provider=provider,
                message="AWS Bedrock bearer token updated successfully",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update key: {str(e)}")


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
