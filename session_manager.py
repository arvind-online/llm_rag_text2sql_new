"""Session management for multi-user query handling."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
from threading import Lock

from models import QueryContext


@dataclass
class UserSession:
    """Represents a user session with cached schema and query history."""
    session_id: str
    cached_schema: Optional[str] = None
    query_history: list[QueryContext] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    max_history: int = 5  # Maximum number of queries to keep


class SessionManager:
    """Manages user sessions with automatic cleanup of expired sessions."""
    
    def __init__(self, ttl_seconds: int = 1800):
        """
        Initialize the session manager.
        
        Args:
            ttl_seconds: Time-to-live for sessions in seconds (default: 30 minutes)
        """
        self.sessions: dict[str, UserSession] = {}
        self.ttl = ttl_seconds
        self._lock = Lock()  # Thread-safe for concurrent requests
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> UserSession:
        """
        Get an existing session or create a new one.
        
        Args:
            session_id: Optional session ID. If None, generates a new UUID
            
        Returns:
            UserSession object
        """
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        with self._lock:
            # Clean up expired sessions before proceeding
            self._cleanup_expired()
            
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.last_accessed = time.time()
                return session
            
            # Create new session
            session = UserSession(session_id=session_id)
            self.sessions[session_id] = session
            return session
    
    def get_session(self, session_id: str) -> Optional[UserSession]:
        """
        Get an existing session by ID.
        
        Args:
            session_id: Session ID to retrieve
            
        Returns:
            UserSession if found, None otherwise
        """
        with self._lock:
            session = self.sessions.get(session_id)
            if session:
                session.last_accessed = time.time()
            return session
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if session was deleted, False if not found
        """
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False
    
    def _cleanup_expired(self) -> None:
        """Remove expired sessions based on TTL."""
        current_time = time.time()
        expired_sessions = [
            session_id
            for session_id, session in self.sessions.items()
            if (current_time - session.last_accessed) > self.ttl
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
    
    def get_active_session_count(self) -> int:
        """
        Get the number of active sessions.
        
        Returns:
            Number of active sessions
        """
        with self._lock:
            self._cleanup_expired()
            return len(self.sessions)
    
    def clear_all_sessions(self) -> None:
        """Clear all sessions (use with caution)."""
        with self._lock:
            self.sessions.clear()


# Global session manager instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """
    Get the global session manager instance (singleton pattern).
    
    Returns:
        SessionManager instance
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
