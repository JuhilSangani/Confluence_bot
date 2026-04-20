#SQLite database

import sqlite3
import json
from datetime import datetime
from pathlib import Path

# Database file lives at the project root
DB_PATH = Path("confluencebot.db")

def get_connection() -> sqlite3.Connection:
    """
    Creates and returns a SQLite database connection.
    """
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)  # check_same_thread=False to allow multiple threads to access the database
    conn.row_factory = sqlite3.Row     # makes query results accessible by column name
    return conn

def initialize_database():
    """
    Creates all tables if they don't already exist.
    """
    conn = get_connection()

    try:
        cursor = conn.cursor()

        # Chats table — one row per conversation session
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Messages table — one row per message in a conversation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats (id)
                    ON DELETE CASCADE
            )
        """)

        # Sources table — one row per Confluence URL added
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
        """)

        conn.commit()
        print("Database initialized successfully.")

    finally:
        conn.close()

# CHAT OPERATIONS
def create_chat(title: str) -> int:
    """
    Creates a new chat session and returns its ID. Title is auto-generated from the first question asked.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chats (title, created_at) VALUES (?, ?)",
            (title, datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid  # returns the new chat's ID
    finally:
        conn.close()


def get_all_chats() -> list[dict]:
    """
    Returns all chat sessions ordered by most recent first.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, created_at FROM chats ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def delete_chat(chat_id: int) -> bool:
    """
    Deletes a chat and all its messages.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        conn.commit()
        return cursor.rowcount > 0  # True if something was deleted
    finally:
        conn.close()

def update_chat_title(chat_id: int, title: str) -> bool:
    """Updates the title of an existing chat session."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE chats SET title = ? WHERE id = ?",
            (title, chat_id)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

# MESSAGE OPERATIONS
def save_message(
    chat_id: int,
    role: str,
    content: str,
    citations: list[dict]
) -> int:
    """
    Saves a single message to the database. Citations are serialized to JSON string for storage.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO messages
               (chat_id, role, content, citations, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                chat_id,
                role,
                content,
                json.dumps(citations),  # serialize list to JSON string
                datetime.now().isoformat()
            )
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_chat_messages(chat_id: int) -> list[dict]:
    """
    Returns all messages for a given chat, oldest first. Citations are deserialized from JSON string back to list.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT role, content, citations, created_at
               FROM messages
               WHERE chat_id = ?
               ORDER BY created_at ASC""",
            (chat_id,)
        )
        rows = cursor.fetchall()
        messages = []
        for row in rows:
            msg = dict(row)
            msg["citations"] = json.loads(msg["citations"])
            messages.append(msg)
        return messages
    finally:
        conn.close()

# SOURCE OPERATIONS
def add_source(title: str, url: str) -> int:
    """
    Adds a Confluence URL to the sources table.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sources (title, url, created_at) VALUES (?, ?, ?)",
            (title, url, datetime.now().isoformat())
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_all_sources() -> list[dict]:
    """
    Returns all added Confluence sources.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, url, created_at FROM sources ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def delete_source(source_id: int) -> bool:
    """
    Deletes a source from the database.
    Note: after deletion, the FAISS index must be rebuilt to remove that source's chunks from the knowledge base.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()

def source_exists(url: str) -> bool:
    """
    Checks if a URL has already been added.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM sources WHERE url = ?", (url,))
        return cursor.fetchone() is not None
    finally:
        conn.close()