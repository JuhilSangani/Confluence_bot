from langchain_community.document_loaders import WebBaseLoader
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from app.ingestion.chunker import chunk_documents
from app.retriever.vector_store import build_vector_store
from app.retriever.embeddings import get_embedding_model
from app.core.database import add_source, get_all_sources, source_exists
from app.retriever.vector_store import FAISS_INDEX_PATH
import re

def extract_page_title(docs: list[Document], url: str) -> str:
    """
    Tries to extract a clean page title from the fetched document. Falls back to the URL if no title is found.
    """
    if docs and docs[0].page_content:
        # Take the first line of content as the title
        first_line = docs[0].page_content.strip().split("\n")[0]
        title = re.sub(r'\s+', ' ', first_line).strip()
        # If it's reasonable length use it, otherwise fall back to URL
        if 5 < len(title) < 100:
            return title
    return url

def fetch_and_ingest_url(url: str) -> dict:
    """
    Fetches a Confluence page URL, ingests it into the RAG pipeline, and saves it to the sources database.
    """
    # Check for duplicates
    if source_exists(url):
        return {
            "success": False,
            "message": "This URL has already been added to the knowledge base.",
            "title": None
        }

    try:
        # Fetch the page content from the URL, WebBaseLoader makes an HTTP GET request and extracts
        loader = WebBaseLoader(url)
        docs = loader.load()

        if not docs or not docs[0].page_content.strip():
            return {
                "success": False,
                "message": "Could not extract any content from this URL. The page may require authentication.",
                "title": None
            }

        title = extract_page_title(docs, url)

        # Add source metadata to each document
        for doc in docs:
            doc.metadata["title"] = title
            doc.metadata["url"] = url
            doc.metadata["source"] = url

        # Chunk the fetched documents
        chunks = chunk_documents(docs)

        # Add chunks to existing FAISS index
        embedding_model = get_embedding_model()

        if FAISS_INDEX_PATH.exists():
            # Load existing index and add new chunks to it
            vector_store = FAISS.load_local(
                str(FAISS_INDEX_PATH),
                embeddings=embedding_model,
                allow_dangerous_deserialization=True
            )
            vector_store.add_documents(chunks)
        else:
            # No index exists yet — create one from scratch
            vector_store = FAISS.from_documents(
                documents=chunks,
                embedding=embedding_model
            )

        # Save the updated index back to disk
        vector_store.save_local(str(FAISS_INDEX_PATH))

        # Save source to database
        add_source(title=title, url=url)

        return {
            "success": True,
            "message": f"Successfully ingested '{title}' into the knowledge base.",
            "title": title
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to fetch URL: {str(e)}",
            "title": None
        }


def rebuild_faiss_without_source(deleted_url: str) -> bool:
    """
    Rebuilds the FAISS index from all remaining sources after one source is deleted.
    """
    try:
        # Get all remaining sources from database
        remaining_sources = get_all_sources()

        if not remaining_sources:
            # No sources left — delete the FAISS index entirely
            import shutil
            if FAISS_INDEX_PATH.exists():
                shutil.rmtree(str(FAISS_INDEX_PATH))
            return True

        # Re-fetch and re-chunk all remaining sources
        all_chunks = []

        for source in remaining_sources:
            if source["url"] == deleted_url:
                continue  # skip the deleted source

            try:
                loader = WebBaseLoader(source["url"])
                docs = loader.load()

                for doc in docs:
                    doc.metadata["title"] = source["title"]
                    doc.metadata["url"] = source["url"]

                chunks = chunk_documents(docs)
                all_chunks.extend(chunks)

            except Exception:
                # If a source fails to reload, skip it
                continue

        if not all_chunks:
            import shutil
            if FAISS_INDEX_PATH.exists():
                shutil.rmtree(str(FAISS_INDEX_PATH))
            return True

        # Rebuild FAISS index from remaining chunks
        embedding_model = get_embedding_model()
        vector_store = FAISS.from_documents(
            documents=all_chunks,
            embedding=embedding_model
        )
        vector_store.save_local(str(FAISS_INDEX_PATH))

        return True

    except Exception as e:
        print(f"Error rebuilding FAISS index: {str(e)}")
        return False