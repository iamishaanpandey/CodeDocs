from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App
    app_name: str = "CodeDocs"
    app_env: str = "development"
    app_version: str = "1.0.0"
    secret_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    allowed_origins: str = "http://localhost:5173,http://localhost:3000"
    frontend_url: str = "http://localhost:5173"

    # Database
    database_url: str
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Neo4j
    neo4j_uri: str
    neo4j_username: str = "neo4j"
    neo4j_password: str

    # Qdrant
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection_name: str = "code_chunks"

    # Redis
    redis_url: str

    # Google OAuth
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    github_app_id: str
    github_app_private_key: str
    github_oauth_client_id: str | None = None
    github_oauth_client_secret: str | None = None
    github_oauth_redirect_uri: str | None = None
    github_webhook_secret: str

    # LLM
    gemini_api_key: str
    groq_api_key: str
    deepseek_api_key: str
    gemini_flash_model: str = "gemini-1.5-flash"
    gemini_pro_model: str = "gemini-1.5-pro"
    gemini_embedding_model: str = "text-embedding-004"
    groq_fast_model: str = "llama-3.1-8b-instant"
    groq_powerful_model: str = "llama-3.1-70b-versatile"
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"

    # Storage
    temp_repo_dir: str = "/tmp/codedocs_repos"
    max_repo_size_mb: int = 500

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
