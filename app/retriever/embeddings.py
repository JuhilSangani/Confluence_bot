from langchain_ollama import OllamaEmbeddings
from app.core.config import get_settings

settings = get_settings()

def get_embedding_model() -> OllamaEmbeddings:
    """
    Returns a configured OllamaEmbeddings instance using the
    nomic-embed-text model running locally via Ollama.
    """
    return OllamaEmbeddings(
        model=settings.EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )