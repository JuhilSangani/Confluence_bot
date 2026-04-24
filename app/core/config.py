# single source file for all the configuration.

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    """
    Pydantic's BaseSettings automatically reads from .env file.
    """

    APP_NAME: str = "ConfluenceBot"
    APP_VERSION: str = "0.1.0"

    # Embedding model — runs locally via Ollama
    EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # LLM — runs via Groq cloud API
    GROQ_API_KEY: str
    LLM_MODEL: str = "llama-3.1-8b-instant"

    # Confluence API credentials
    CONFLUENCE_URL: str
    CONFLUENCE_EMAIL: str
    CONFLUENCE_API_TOKEN: str
    CONFLUENCE_SPACE_KEY: str = ""

    class Config:
        env_file = ".env",  #Tells Pydantic where to find .env file
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    """
    @lru_cache ensures this function runs only ONCE — on the first call. After that, Python returns the cached Settings object directly.
    """
    return Settings()
