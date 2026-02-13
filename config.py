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
    aws_bearer_token_bedrock: str = ""  # Short-term API key (bearer token)
    
    # Database Type: "postgres" or "clickhouse"
    db_type: str = "postgres"
    
    # PostgreSQL Database Configuration
    pghost: str = "localhost"
    pguser: str = "postgres"
    pgpassword: str = ""
    pgdatabase: str = "postgres"
    pgport: int = 5432
    
    # ClickHouse Database Configuration
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "default"
    
    # Table Filtering - comma-separated list of tables to include in schema
    # Leave empty to include all tables
    table_filter_list: str = ""
    
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
    def postgres_url(self) -> str:
        """Get PostgreSQL connection URL with URL-encoded password."""
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.pgpassword)
        return f"postgresql://{self.pguser}:{encoded_password}@{self.pghost}:{self.pgport}/{self.pgdatabase}"
    
    @property
    def clickhouse_url(self) -> str:
        """Get ClickHouse connection URL with URL-encoded password."""
        from urllib.parse import quote_plus
        encoded_password = quote_plus(self.clickhouse_password)
        return f"clickhouse+http://{self.clickhouse_user}:{encoded_password}@{self.clickhouse_host}:{self.clickhouse_port}/{self.clickhouse_database}"
    
    @property
    def database_url(self) -> str:
        """Get the appropriate database connection URL based on db_type."""
        if self.db_type.lower() == "clickhouse":
            return self.clickhouse_url
        else:
            return self.postgres_url
    
    @property
    def allowed_tables(self) -> list[str]:
        """Get list of allowed tables from table_filter_list."""
        if not self.table_filter_list:
            return []
        return [table.strip() for table in self.table_filter_list.split(",") if table.strip()]
    
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
        import os
        
        # Set bearer token env var if configured (auto-detected by langchain-aws)
        if settings.aws_bearer_token_bedrock:
            os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.aws_bearer_token_bedrock
        
        # Build kwargs for Bedrock
        kwargs = {
            "model": settings.bedrock_model_id,
            "region_name": settings.aws_region,
            "temperature": settings.llm_temperature,
        }
        
        # Use named profile if provided (fallback for non-API-key auth)
        if settings.aws_profile and not settings.aws_bearer_token_bedrock:
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

