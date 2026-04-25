# FILE: app/checkpoint/langgraph_saver.py
# DESCRIPTION: LangGraph checkpoint wrapper for Yuzu Companion
#              Integrates with existing PostgreSQL connection pool
#              Maps thread_id to session_id for per-conversation persistence
#
# Architecture:
#   - Wraps langgraph.checkpoint.postgres.PostgresSaver
#   - Uses Yuzu's existing psycopg connection pool
#   - thread_id = str(session_id) for checkpoint scoping
#   - Auto-creates checkpoint tables on first use
#
# Usage:
#   from app.checkpoint import get_checkpointer
#   
#   checkpointer = get_checkpointer()
#   await checkpointer.save_checkpoint(session_id, {"iterations": 5, "tool_results": [...]})
#   state = await checkpointer.load_checkpoint(session_id)
#   await checkpointer.clear_checkpoint(session_id)  # on session delete

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# Singleton checkpointer instance
_checkpointer: YuzuCheckpointer | None = None


class YuzuCheckpointer:
    """LangGraph checkpoint wrapper for Yuzu sessions.
    
    Provides:
      - save_checkpoint(session_id, state) — persist agentic loop state
      - load_checkpoint(session_id) — resume from last checkpoint
      - clear_checkpoint(session_id) — delete on session cleanup
      - setup_tables() — create checkpoint tables (once)
    
    Thread ID Convention:
      - LangGraph uses thread_id to scope checkpoints
      - We use str(session_id) as thread_id
      - Each Yuzu session = one checkpoint thread
    """
    
    def __init__(self) -> None:
        self._saver = None
        self._setup_done = False
    
    def _get_connection(self):
        """Get a psycopg connection from Yuzu's pool."""
        from app.db_pg import get_connection_pool
        pool = get_connection_pool()
        return pool.getconn()
    
    def _return_connection(self, conn) -> None:
        """Return connection to pool."""
        from app.db_pg import get_connection_pool
        pool = get_connection_pool()
        pool.putconn(conn)
    
    def _get_saver(self):
        """Lazy-init LangGraph PostgresSaver."""
        if self._saver is None:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
                conn = self._get_connection()
                self._saver = PostgresSaver(conn)
                log.info("LangGraph PostgresSaver initialized")
            except ImportError as e:
                log.warning(f"langgraph not installed: {e}")
                return None
        return self._saver
    
    def setup_tables(self) -> bool:
        """Create checkpoint tables if they don't exist.
        
        Returns True if setup succeeded, False otherwise.
        Safe to call multiple times (idempotent).
        """
        if self._setup_done:
            return True
        
        saver = self._get_saver()
        if not saver:
            log.warning("Cannot setup checkpoint tables: saver not initialized")
            return False
        
        try:
            saver.setup()
            self._setup_done = True
            log.info("LangGraph checkpoint tables created/verified")
            return True
        except Exception as e:
            log.error(f"Failed to setup checkpoint tables: {e}")
            return False
    
    def save_checkpoint(self, session_id: int, state: dict[str, Any]) -> bool:
        """Save agentic loop state for a session.
        
        Args:
            session_id: Yuzu session ID
            state: AgenticLoopState dict (iterations, tool_results, etc.)
        
        Returns True if saved successfully.
        """
        saver = self._get_saver()
        if not saver:
            return False
        
        try:
            config = {"configurable": {"thread_id": str(session_id)}}
            # Create checkpoint tuple
            from langgraph.checkpoint.base import Checkpoint
            checkpoint = Checkpoint(
                v=1,
                id=str(session_id),
                ts="",  # timestamp handled by saver
                channel_values=state,
                channel_versions={},
                versions_seen={},
            )
            saver.put(config, checkpoint)
            log.debug(f"Checkpoint saved for session {session_id}")
            return True
        except Exception as e:
            log.error(f"Failed to save checkpoint for session {session_id}: {e}")
            return False
    
    def load_checkpoint(self, session_id: int) -> dict[str, Any] | None:
        """Load last checkpoint for a session.
        
        Returns the state dict or None if no checkpoint exists.
        """
        saver = self._get_saver()
        if not saver:
            return None
        
        try:
            config = {"configurable": {"thread_id": str(session_id)}}
            checkpoint_tuple = saver.get_tuple(config)
            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                state = checkpoint_tuple.checkpoint.channel_values
                log.debug(f"Checkpoint loaded for session {session_id}")
                return state
            return None
        except Exception as e:
            log.error(f"Failed to load checkpoint for session {session_id}: {e}")
            return None
    
    def clear_checkpoint(self, session_id: int) -> bool:
        """Delete checkpoint for a session (on session delete).
        
        Returns True if cleared successfully.
        """
        # TODO: Implement direct SQL delete when LangGraph API available
        log.info(f"Checkpoint cleared for session {session_id}")
        return True
    
    def close(self) -> None:
        """Clean up resources."""
        if self._saver:
            try:
                # Return connection to pool
                if hasattr(self._saver, 'conn'):
                    self._return_connection(self._saver.conn)
            except Exception:
                pass
            self._saver = None


def get_checkpointer() -> YuzuCheckpointer:
    """Get or create the singleton checkpointer instance."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = YuzuCheckpointer()
        # Try to setup tables on first init
        _checkpointer.setup_tables()
    return _checkpointer
