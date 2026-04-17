from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from app.retriever.embeddings import get_embedding_model

FAISS_INDEX_PATH = Path("faiss_index")

def build_vector_store(chunks: list[Document]) -> FAISS:
    """
    Takes a list of chunk Documents, embeds them all using
    nomic-embed-text, builds a FAISS index, saves it to disk,
    and returns the index object.
    """
    embeddings = get_embedding_model()

    vector_store = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings,
    ) # FAISS.from_documents extracts page_content, embeds into a 768-dimensional vector, builds the FAISS index with those vectors

    vector_store.save_local(str(FAISS_INDEX_PATH))
    print(f"FAISS index saved to {FAISS_INDEX_PATH}")

    return vector_store


def load_vector_store() -> FAISS:
    """
    Loads a previously saved FAISS index from disk and returns it
    ready for similarity search.
    """
    embeddings = get_embedding_model()

    vector_store = FAISS.load_local(
        str(FAISS_INDEX_PATH),
        embeddings=embeddings,
        allow_dangerous_deserialization=True,
    ) #allow_dangerous_deserialization=True allows to load pickle file which contains metadata.

    return vector_store


def search_vector_store(query: str, k: int = 3) -> list[Document]:
    """
    Embeds a query string and searches the FAISS index for the
    k most semantically similar chunks.
    """
    vector_store = load_vector_store()
    results = vector_store.similarity_search(query, k=k)

    return results