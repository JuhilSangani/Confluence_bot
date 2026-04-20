# ARCHITECTURE:
# Streamlit (port 8501) → FastAPI (port 8000) → RAG pipeline

import streamlit as st
import requests
from datetime import datetime

API_BASE_URL = "http://localhost:8000"

def api_post(endpoint: str, data: dict) -> dict:
    try:
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            json=data,
            timeout=60
        )
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to FastAPI. Make sure it is running on port 8000."}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": e.response.json().get("detail", str(e))}
    except Exception as e:
        return {"success": False, "error": str(e)}


def api_get(endpoint: str) -> dict:
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}", timeout=60)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Cannot connect to FastAPI. Make sure it is running on port 8000."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def api_delete(endpoint: str) -> dict:
    try:
        response = requests.delete(f"{API_BASE_URL}{endpoint}", timeout=30)
        response.raise_for_status()
        return {"success": True, "data": response.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_date(iso_string: str) -> str:
    """Converts ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso_string


# PAGE CONFIG — must be first Streamlit command
st.set_page_config(
    page_title="ConfluenceBot",
    page_icon="🤖",
    layout="wide",
)

# Custom CSS to pin chat input to bottom of viewport
st.markdown("""
    <style>
        .stChatInput {
            position: fixed;
            bottom: 0;
            left: 320px;
            right: 0;
            padding: 1rem 2rem;
            background: #0e1117;
            z-index: 999;
            border-top: 1px solid rgba(255,255,255,0.1);
        }
        .stChatInput textarea {
            width: 100% !important;
        }
        section[data-testid="stMain"] > div {
            padding-bottom: 6rem;
        }
    </style>
""", unsafe_allow_html=True)

# SESSION STATE INITIALIZATION
if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = None

if "active_chat_title" not in st.session_state:
    st.session_state.active_chat_title = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat_initialized" not in st.session_state:
    st.session_state.chat_initialized = False

# SIDEBAR
with st.sidebar:
    st.title("🤖 ConfluenceBot")
    st.markdown("---")

    # New Chat button
    if st.button("+ New Chat", use_container_width=True):
        result = api_post("/api/chats", {"title": "New Chat"})
        if result["success"]:
            st.session_state.active_chat_id = result["data"]["id"]
            st.session_state.active_chat_title = result["data"]["title"]
            st.session_state.messages = []
            st.session_state.chat_initialized = True
            st.rerun()
        else:
            st.error(result["error"])

    st.markdown("---")
    st.markdown("**Recent Chats**")

    # Load and display chat history
    chats_result = api_get("/api/chats")
    if chats_result["success"]:
        chats = chats_result["data"]
        if not chats:
            st.caption("No chats yet. Start a new one above.")
        else:
            for chat in chats:
                col1, col2 = st.columns([4, 1])
                with col1:
                    # Highlight active chat
                    is_active = chat["id"] == st.session_state.active_chat_id
                    label = f"**{chat['title']}**" if is_active else chat["title"]
                    if st.button(
                        label,
                        key=f"chat_{chat['id']}",
                        use_container_width=True,
                    ):
                        # Load this chat's messages
                        st.session_state.active_chat_id = chat["id"]
                        st.session_state.active_chat_title = chat["title"]
                        msgs_result = api_get(f"/api/chats/{chat['id']}/messages")
                        if msgs_result["success"]:
                            st.session_state.messages = msgs_result["data"]
                        st.rerun()
                with col2:
                    if st.button("✕", key=f"del_{chat['id']}"):
                        del_result = api_delete(f"/api/chats/{chat['id']}")
                        if del_result["success"]:
                            if st.session_state.active_chat_id == chat["id"]:
                                st.session_state.active_chat_id = None
                                st.session_state.messages = []
                            st.rerun()
    else:
        st.error(chats_result["error"])

    st.markdown("---")

    # Settings
    st.markdown("**⚙ Settings**")
    st.session_state.k = st.slider(
        "Chunks to retrieve (k)",
        min_value=1,
        max_value=10,
        value=3,
        help="Higher k = more context but more noise."
    )

    st.markdown("---")
    st.caption("FastAPI · LangChain · FAISS · Groq")

# MAIN AREA
st.title("ConfluenceBot")
st.caption("Answers grounded in your Confluence pages — with citations.")

# Tabs
tab_chat, tab_sources = st.tabs(["💬 Chat", "📄 Sources"])

# CHAT TAB
with tab_chat:

    # Auto-create a chat on first load so input is always visible
    if not st.session_state.chat_initialized:
        result = api_post("/api/chats", {"title": "New Chat"})
        if result["success"]:
            st.session_state.active_chat_id = result["data"]["id"]
            st.session_state.active_chat_title = result["data"]["title"]
            st.session_state.messages = []
            st.session_state.chat_initialized = True

    # Message display container
    messages_container = st.container()

    with messages_container:
        if not st.session_state.messages:
            st.markdown(
                "<div style='text-align:center; color:gray; padding:3rem 0;'>"
                "Ask a question about your Confluence pages to get started."
                "</div>",
                unsafe_allow_html=True
            )
        else:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    if message["role"] == "assistant" and message.get("citations"):
                        st.markdown("**📚 Sources:**")
                        for citation in message["citations"]:
                            st.markdown(
                                f"- [{citation['title']}]({citation['url']})"
                            )

    # Chat input — Streamlit always renders this at page bottom
    if prompt := st.chat_input("Ask a question about your Confluence pages..."):

        # Rename chat from first real question
        if len(st.session_state.messages) == 0:
            new_title = prompt[:50]
            requests.patch(
                f"{API_BASE_URL}/api/chats/{st.session_state.active_chat_id}",
                json={"title": new_title},
                timeout=10
            )
            st.session_state.active_chat_title = new_title

        # Add user message to state
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "citations": []
        })

        # Call RAG pipeline
        with st.spinner("Searching Confluence pages..."):
            result = api_post("/api/chat", {
                "question": prompt,
                "k": st.session_state.k,
                "chat_id": st.session_state.active_chat_id
            })

        if not result["success"]:
            error_msg = result["error"]
            if "string_too_short" in str(error_msg):
                error_msg = "Please type at least 3 characters before asking a question."
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg,
                "citations": []
            })
        else:
            data = result["data"]
            st.session_state.messages.append({
                "role": "assistant",
                "content": data["answer"],
                "citations": data["citations"]
            })

        st.rerun()

# SOURCES TAB
with tab_sources:

    st.markdown("### Add a Confluence Page")
    st.caption("Paste a Confluence page URL to add it to the knowledge base.")

    col1, col2 = st.columns([5, 1])
    with col1:
        new_url = st.text_input(
            "Confluence URL",
            placeholder="https://company.atlassian.net/wiki/spaces/...",
            label_visibility="collapsed"
        )
    with col2:
        add_clicked = st.button("+ Add", use_container_width=True)

    if add_clicked:
        if not new_url:
            st.warning("Please enter a URL.")
        else:
            with st.spinner("Fetching and ingesting page..."):
                result = api_post("/api/sources", {"url": new_url})
            if result["success"]:
                st.success(result["data"]["message"])
                st.rerun()
            else:
                st.error(result["error"])

    st.markdown("---")
    st.markdown("### Knowledge Base Sources")

    # Load and display sources
    sources_result = api_get("/api/sources")

    if not sources_result["success"]:
        st.error(sources_result["error"])
    else:
        sources = sources_result["data"]

        if not sources:
            st.caption("No sources added yet. Paste a Confluence URL above or run ingestion from the API.")
        else:
            st.caption(f"{len(sources)} source(s) in knowledge base.")

            for source in sources:
                with st.container():
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"**{source['title']}**")
                        st.markdown(
                            f"<span style='font-size:12px;color:gray;'>{source['url']}</span>",
                            unsafe_allow_html=True
                        )
                        st.caption(f"Added {format_date(source['created_at'])}")
                    with col2:
                        if st.button(
                            "Delete",
                            key=f"src_{source['id']}",
                            type="secondary"
                        ):
                            with st.spinner("Deleting and rebuilding index..."):
                                del_result = api_delete(
                                    f"/api/sources/{source['id']}"
                                )
                            if del_result["success"]:
                                st.success("Source deleted.")
                                st.rerun()
                            else:
                                st.error(del_result["error"])
                    st.markdown("---")