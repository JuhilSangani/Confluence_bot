from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.chains.rag_chain import ask_question
from app.ingestion.loader import load_confluence_documents
from app.ingestion.chunker import chunk_documents
from app.retriever.vector_store import build_vector_store
from app.ingestion.confluence_fetcher import (
    fetch_and_ingest_url,
    rebuild_faiss_without_source
)
from app.core.database import (
    create_chat, get_all_chats, delete_chat, update_chat_title,
    save_message, get_chat_messages,
    add_source, get_all_sources, delete_source,
    source_exists
)

router = APIRouter()

class ChatRequest(BaseModel):
    """
    Defines what a valid chat request must contain.
    """
    question: str = Field(..., min_length=3, max_length=500, description="The question to ask ConfluenceBot")
    k: int = Field(default=3, ge=1, le=10, description="Number of chunks to retrieve from FAISS")
    chat_id: int = Field(..., description="ID of the current chat session")

class UpdateChatRequest(BaseModel):
    title: str = Field(..., max_length=100)

class CitationModel(BaseModel):
    """
    Represents a single citation — one Confluence page that was used as a source for the answer.
    """
    title: str
    url: str

class ChatResponse(BaseModel):
    """
    Defines the exact shape of every chat response.
    """
    question: str
    answer: str
    citations: list[CitationModel]
    sources_found: int
    chat_id: int

class CreateChatRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=100)

class ChatModel(BaseModel):
    id: int
    title: str
    created_at: str

class MessageModel(BaseModel):
    role: str
    content: str
    citations: list[CitationModel]
    created_at: str

class AddSourceRequest(BaseModel):
    url: str = Field(..., description="Confluence page URL to ingest")

class SourceModel(BaseModel):
    id: int
    title: str
    url: str
    created_at: str

class IngestResponse(BaseModel):
    """
    Response shape for the ingestion endpoint.
    """
    message: str
    documents_loaded: int
    chunks_created: int


# RAG CHAT ENDPOINT
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chatbot endpoint. Runs the full pipeline and saves the conversation to the database for persistent history.
    """
    try:
        result = ask_question(request.question, k=request.k)

        citations = [
            CitationModel(title=c["title"], url=c["url"])
            for c in result["citations"]
        ]

        # Save user question to database
        save_message(
            chat_id=request.chat_id,
            role="user",
            content=request.question,
            citations=[]
        )

        # Save assistant answer to database
        save_message(
            chat_id=request.chat_id,
            role="assistant",
            content=result["answer"],
            citations=result["citations"]
        )

        return ChatResponse(
            question=result["question"],
            answer=result["answer"],
            citations=citations,
            sources_found=len(citations),
            chat_id=request.chat_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG pipeline error: {str(e)}")


# CHAT MANAGEMENT ENDPOINTS
@router.post("/chats", response_model=ChatModel)
async def create_new_chat(request: CreateChatRequest):
    """Creates a new chat session and returns it."""
    chat_id = create_chat(request.title)
    chats = get_all_chats()
    chat = next(c for c in chats if c["id"] == chat_id)
    return ChatModel(**chat)

@router.patch("/chats/{chat_id}", response_model=ChatModel)
async def rename_chat(chat_id: int, request: UpdateChatRequest):
    """Renames an existing chat session."""
    success = update_chat_title(chat_id, request.title)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found.")
    chats = get_all_chats()
    chat = next(c for c in chats if c["id"] == chat_id)
    return ChatModel(**chat)

@router.get("/chats", response_model=list[ChatModel])
async def list_chats():
    """Returns all chat sessions for the sidebar history list."""
    chats = get_all_chats()
    return [ChatModel(**c) for c in chats]

@router.get("/chats/{chat_id}/messages", response_model=list[MessageModel])
async def get_messages(chat_id: int):
    """Returns all messages for a specific chat session."""
    messages = get_chat_messages(chat_id)
    return [
        MessageModel(
            role=m["role"],
            content=m["content"],
            citations=[CitationModel(**c) for c in m["citations"]],
            created_at=m["created_at"]
        )
        for m in messages
    ]

@router.delete("/chats/{chat_id}")
async def remove_chat(chat_id: int):
    """Deletes a chat and all its messages."""
    success = delete_chat(chat_id)
    if not success:
        raise HTTPException(status_code=404, detail="Chat not found.")
    return {"message": "Chat deleted successfully."}


# SOURCE MANAGEMENT ENDPOINTS
@router.post("/sources")
async def add_confluence_source(request: AddSourceRequest):
    """
    Fetches a Confluence URL, ingests it into FAISS, and saves it to the sources database.
    """
    result = fetch_and_ingest_url(request.url)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return {
        "message": result["message"],
        "title": result["title"]
    }

@router.get("/sources", response_model=list[SourceModel])
async def list_sources():
    """Returns all added Confluence sources."""
    sources = get_all_sources()
    return [SourceModel(**s) for s in sources]

@router.delete("/sources/{source_id}")
async def remove_source(source_id: int):
    """
    Deletes a source from the database and rebuilds the FAISS index without that source's chunks.
    """
    # Get source details before deletion
    sources = get_all_sources()
    source = next((s for s in sources if s["id"] == source_id), None)

    if not source:
        raise HTTPException(status_code=404, detail="Source not found.")

    # Delete from database first
    delete_source(source_id)

    # Rebuild FAISS index without this source
    rebuild_faiss_without_source(source["url"])

    return {"message": f"Source '{source['title']}' deleted and index rebuilt."}


# INGESTION ENDPOINT
@router.get("/ingest", response_model=IngestResponse)
async def ingest():
    """Triggers full ingestion from real Confluence API. Fetches all pages from configured space, chunks, embeds, and saves to FAISS index."""
    try:
        from app.ingestion.confluence_loader import load_confluence_documents as load_real
        documents = load_real()
        chunks = chunk_documents(documents)
        build_vector_store(chunks)

        # Save sources to database for UI display
        from app.core.database import add_source, source_exists
        for doc in documents:
            if not source_exists(doc.metadata["url"]):
                add_source(
                    title=doc.metadata["title"],
                    url=doc.metadata["url"]
                )

        return IngestResponse(
            message=f"Ingested {len(documents)} real Confluence pages successfully.",
            documents_loaded=len(documents),
            chunks_created=len(chunks),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion pipeline error: {str(e)}"
        )

@router.get("/ingest/mock", response_model=IngestResponse)
async def ingest_mock():
    """Triggers ingestion from mock JSON data. Useful for testing without hitting the Confluence API."""
    try:
        from app.ingestion.loader import load_confluence_documents as load_mock
        documents = load_mock()
        chunks = chunk_documents(documents)
        build_vector_store(chunks)

        return IngestResponse(
            message="Mock ingestion complete. FAISS index updated successfully.",
            documents_loaded=len(documents),
            chunks_created=len(chunks),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion pipeline error: {str(e)}"
        )