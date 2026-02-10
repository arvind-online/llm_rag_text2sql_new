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
    
    # Database Type: "postgres" or "clickhouse"
    db_type: str = "postgres"
    
    # PostgreSQL Database Configuration
    pghost: str = "localhost"
    pguser: str = "postgres"
    pgpassword: str = ""
    pgdatabase: str = "postgres"
    pgport: int = 5432
    
    # ClickHouse Database Configuration
    ch_host: str = "localhost"
    ch_port: int = 8123
    ch_user: str = "default"
    ch_password: str = ""
    ch_database: str = "default"
    
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
    def clickhouse_url(self) -> str:
        """Get ClickHouse connection URL (HTTP protocol)."""
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.ch_password) if self.ch_password else ""
        if encoded_password:
            return f"clickhouse+http://{self.ch_user}:{encoded_password}@{self.ch_host}:{self.ch_port}/{self.ch_database}"
        return f"clickhouse+http://{self.ch_user}@{self.ch_host}:{self.ch_port}/{self.ch_database}"
    
    @property
    def active_database_url(self) -> str:
        """Get the active database URL based on DB_TYPE setting."""
        if self.db_type.lower() == "clickhouse":
            return self.clickhouse_url
        return self.database_url
    
    @property
    def db_dialect(self) -> str:
        """Get the human-readable dialect name for prompt injection."""
        if self.db_type.lower() == "clickhouse":
            return "ClickHouse"
        return "PostgreSQL"
    
    @property
    def chroma_persist_dir_resolved(self) -> Path:
        """Get resolved ChromaDB persistence directory."""
        return Path(self.chroma_persist_dir).resolve()


# Global settings instance
settings = Settings()
