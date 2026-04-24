# RAG pipeline - coordinates retrieval, prompt building, LLM generation, and citation extraction into one clean function that the API layer calls.

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from app.retriever.vector_store import search_vector_store
from app .core.config import get_settings

settings = get_settings()

def get_llm() -> ChatGroq:
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.LLM_MODEL,
        temperature=0,  # no creativity, only facts
    )

def format_context(chunks) -> str:
    """
    Formats retrieved chunks into a readable context block
    that the LLM can reason over.
    """
        
    context_parts = []

    for i, chunk in enumerate(chunks):
        title = chunk.metadata.get("title", "Unknown Page")
        content = chunk.page_content
        context_parts.append(f"[Source {i + 1}: {title}]\n{content}")

    # Join all chunks into a readable block separated by blank lines
    return "\n\n".join(context_parts)

def extract_citations(chunks) -> list[dict]:
    """
    Extracts citation information from retrieved chunk metadata.

    Returns a list of dicts with title and url — ready to be
    returned in the API response for the UI to display.
    """
    citations = []
    seen_urls = set()  # deduplicate — multiple chunks from same page

    for chunk in chunks:
        url = chunk.metadata.get("url", "")
        title = chunk.metadata.get("title", "Unknown Page")

        # Only add each source page once even if multiple chunks from the same page were retrieved
        if url and url not in seen_urls:
            citations.append({
                "title": title,
                "url": url,
            })
            seen_urls.add(url)

    return citations

def ask_question(question: str, k: int = 3) -> dict:
    """
    The main RAG pipeline function. Takes a user question, retrieves relevant chunks, builds a grounded prompt,
    calls the LLM, and returns the answer with citations.
    """

    # Retrieve relevant chunks from FAISS
    chunks = search_vector_store(question, k=k)

    if not chunks:
        return {
            "answer": "I could not find any relevant information in the Confluence pages to answer your question.",
            "citations": [],
            "question": question,
        }

    # Format chunks into a readable context block
    context = format_context(chunks)

    # prompt with strict anti-hallucination instructions
    system_prompt = """You are ConfluenceBot, a precise and trustworthy assistant that answers questions strictly based on the provided Confluence page content.

STRICT RULES YOU MUST FOLLOW:
1. Answer ONLY using the information provided in the context below.
2. Do NOT use any outside knowledge, assumptions, or information not present in the context.
3. If the context does not contain enough information to answer the question, respond exactly with: "I don't have enough information from the Confluence pages to answer this question."
4. Be concise and direct. Do not pad your answer with unnecessary text.
5. Never make up URLs, page names, or facts.

Context from Confluence pages:
{context}"""

    # Call the Groq LLM
    llm = get_llm()

    messages = [
        SystemMessage(content=system_prompt.format(context=context)),
        HumanMessage(content=question),
    ]

    response = llm.invoke(messages)

    # Extract citations from chunk metadata (never from LLM)
    answer = response.content

    insufficient_answer = "i don't have enough information" in answer.lower()

    citations = [] if insufficient_answer else extract_citations(chunks)

    return {
        "answer": response.content,
        "citations": citations,
        "question": question,
    }