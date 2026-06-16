"""
In-memory session-based data store.

Stores uploaded DataFrames and chat histories keyed by session ID.
Includes automatic cleanup of stale sessions.
"""

import uuid
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.config import settings


@dataclass
class SessionData:
    """Holds all data for a single user session."""
    session_id: str
    file_name: str
    raw_df: pd.DataFrame
    normalized_df: pd.DataFrame
    column_mapping: dict[str, str]
    upload_timestamp: datetime = field(default_factory=datetime.utcnow)
    chat_history: list[dict] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.normalized_df)

    @property
    def is_expired(self) -> bool:
        ttl = timedelta(hours=settings.SESSION_TTL_HOURS)
        return datetime.utcnow() - self.upload_timestamp > ttl


class DataStore:
    """
    Thread-safe in-memory store for session data.
    
    For production, replace with Redis or database-backed store.
    """

    def __init__(self):
        self._sessions: dict[str, SessionData] = {}
        self._lock = threading.Lock()

    def create_session(
        self,
        file_name: str,
        raw_df: pd.DataFrame,
        normalized_df: pd.DataFrame,
        column_mapping: dict[str, str],
    ) -> str:
        """
        Create a new session with uploaded data.
        
        Returns the generated session_id.
        """
        session_id = str(uuid.uuid4())
        session = SessionData(
            session_id=session_id,
            file_name=file_name,
            raw_df=raw_df,
            normalized_df=normalized_df,
            column_mapping=column_mapping,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get a session by ID. Returns None if not found or expired."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired:
                del self._sessions[session_id]
                return None
            return session

    def get_latest_session(self) -> Optional[SessionData]:
        """Get the most recently uploaded session (ignores expiration)."""
        with self._lock:
            if not self._sessions:
                return None
            return sorted(self._sessions.values(), key=lambda s: s.upload_timestamp)[-1]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def add_chat_message(self, session_id: str, role: str, content: str) -> bool:
        """Add a chat message to a session's history."""
        session = self.get_session(session_id)
        if session is None:
            return False
        session.chat_history .append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        return True

    def get_chat_history(self, session_id: str) -> list[dict]:
        """Get the chat history for a session."""
        session = self.get_session(session_id)
        if session is None:
            return []
        return session.chat_history.copy()

    def clear_chat_history(self, session_id: str) -> bool:
        """Clear a session's chat history."""
        session = self.get_session(session_id)
        if session is None:
            return False
        session.chat_history.clear()
        return True

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        removed = 0
        with self._lock:
            expired_ids = [
                sid for sid, session in self._sessions.items()
                if session.is_expired
            ]
            for sid in expired_ids:
                del self._sessions[sid]
                removed += 1
        return removed

    @property
    def active_session_count(self) -> int:
        with self._lock:
            return len(self._sessions)


# Singleton instance
data_store = DataStore()
