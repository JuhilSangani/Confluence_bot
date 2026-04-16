from langchain_ollama import OllamaEmbeddings

def get_embedding_model() -> OllamaEmbeddings:
    """
    Returns a configured OllamaEmbeddings instance using the
    nomic-embed-text model running locally via Ollama.
    """
    return OllamaEmbeddings(
        model="nomic-embed-text",
        base_url="http://localhost:11434"
    )