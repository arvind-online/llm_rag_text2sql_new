"""Configuration management using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # LLM Provider: "groq", "ollama", or "bedrock"
    llm_provider: str = "groq"
    
    # Groq Configuration
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.0
    
    # Ollama Configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    
    # AWS Bedrock Configuration
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    aws_region: str = "ap-south-1"
    aws_profile: str = ""
    aws_session_token: str = ""  # For temporary credentials
    
    # PostgreSQL Database Configuration
    pghost: str = "localhost"
    pguser: str = "postgres"
    pgpassword: str = ""
    pgdatabase: str = "postgres"
    pgport: int = 5432
    
    # Vector Store
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "documents"
    
    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"
    
    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    # Debug Settings
    show_sql_queries: bool = True  # Set to True to show SQL queries in responses
    
    @property
    def database_url(self) -> str:
        """Get PostgreSQL connection URL with URL-encoded password."""
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.pgpassword)
        return f"postgresql://postgres.symkcqsvcrtgqmqcsfuq:{encoded_password}@aws-1-ap-northeast-1.pooler.supabase.com:{self.pgport}/{self.pgdatabase}"
    
    @property
    def chroma_persist_dir_resolved(self) -> Path:
        """Get resolved ChromaDB persistence directory."""
        return Path(self.chroma_persist_dir).resolve()


# Global settings instance
settings = Settings()


def get_llm():
    """
    Factory function that returns the correct LangChain chat model
    based on the LLM_PROVIDER setting.
    
    Supports:
    - "groq": ChatGroq (cloud-based, fast)
    - "ollama": ChatOllama (local or remote)
    - "bedrock": ChatBedrockConverse (AWS Bedrock)
    
    Returns:
        ChatGroq, ChatOllama, or ChatBedrockConverse instance
    """
    provider = settings.llm_provider.lower()
    
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
        )
    elif provider == "bedrock":
        from langchain_aws import ChatBedrockConverse
        import boto3
        
        # Build kwargs for Bedrock
        kwargs = {
            "model": settings.bedrock_model_id,
            "region_name": settings.aws_region,
            "temperature": settings.llm_temperature,
        }
        
        # If session token is provided, create custom boto3 client with temporary credentials
        if settings.aws_session_token:
            import os
            session = boto3.Session(
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                aws_session_token=settings.aws_session_token,
                region_name=settings.aws_region,
            )
            kwargs["client"] = session.client("bedrock-runtime")
        # Use named profile if provided
        elif settings.aws_profile:
            kwargs["credentials_profile_name"] = settings.aws_profile
        
        return ChatBedrockConverse(**kwargs)
    else:
        # Default to Groq
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.llm_model,
            api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
        )

