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
    
    # LLM Configuration (GROQ)
    groq_api_key: str = ""
    llm_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.0
    
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
        return f"postgresql://{self.pguser}:{encoded_password}@{self.pghost}:{self.pgport}/{self.pgdatabase}"
    
    @property
    def chroma_persist_dir_resolved(self) -> Path:
        """Get resolved ChromaDB persistence directory."""
        return Path(self.chroma_persist_dir).resolve()


# Global settings instance
settings = Settings()
