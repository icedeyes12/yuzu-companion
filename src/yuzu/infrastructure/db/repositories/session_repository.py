"""SQLAlchemy implementation of SessionRepository."""

from typing import Optional, List

from ....domain.interfaces.db_interface import SessionRepository
from ....domain.models import ChatSession, SessionMemory


import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from database import Database as LegacyDatabase, ChatSession as SessionModel


class SQLAlchemySessionRepository(SessionRepository):
    """Session repository using SQLAlchemy."""
    
    def _map_to_domain(self, db_session: SessionModel) -> ChatSession:
        """Map database session to domain model."""
        import json
        
        memory_data = json.loads(db_session.memory_json or '{}')
        memory = SessionMemory(
            context=memory_data.get('session_context', ''),
            summary_count=memory_data.get('summary_count', 0),
        )
        
        return ChatSession(
            id=db_session.id,
            name=db_session.name or 'New Chat',
            is_active=db_session.is_active or False,
            message_count=db_session.message_count or 0,
            memory=memory,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
        )
    
    def _map_to_db(self, session: ChatSession, db_session: SessionModel) -> None:
        """Map domain session to database model."""
        import json
        
        db_session.name = session.name
        db_session.is_active = session.is_active
        db_session.message_count = session.message_count
        db_session.memory_json = json.dumps({
            'session_context': session.memory.context,
            'summary_count': session.memory.summary_count,
        })
    
    def get_active(self) -> Optional[ChatSession]:
        """Get currently active session."""
        try:
            db_session = LegacyDatabase.get_active_session()
            if db_session:
                return self._map_to_domain(db_session)
            return None
        except Exception as e:
            print(f"[SessionRepository] Error getting active session: {e}")
            return None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> List[ChatSession]:
        """Get all sessions with pagination."""
        try:
            db_sessions = LegacyDatabase.get_all_sessions()
            sessions = [self._map_to_domain(s) for s in db_sessions]
            return sessions[offset:offset + limit] if limit else sessions
        except Exception as e:
            print(f"[SessionRepository] Error getting sessions: {e}")
            return []
    
    def get_by_id(self, session_id: int) -> Optional[ChatSession]:
        """Get session by ID."""
        try:
            # Legacy API doesn't have get_by_id, filter from get_all
            sessions = self.get_all()
            return next((s for s in sessions if s.id == session_id), None)
        except Exception as e:
            print(f"[SessionRepository] Error getting session by ID: {e}")
            return None
    
    def create(self, name: str) -> ChatSession:
        """Create new session."""
        try:
            session_id = LegacyDatabase.create_session(name)
            # Return the created session
            sessions = LegacyDatabase.get_all_sessions()
            db_session = next((s for s in sessions if s['id'] == session_id), None)
            
            if db_session:
                # Convert dict to SessionModel-like object
                from types import SimpleNamespace
                session_obj = SimpleNamespace(
                    id=db_session['id'],
                    name=db_session['name'],
                    is_active=db_session['is_active'],
                    message_count=db_session['message_count'],
                    memory_json='{}',
                    created_at=db_session.get('created_at'),
                    updated_at=db_session.get('updated_at'),
                )
                return self._map_to_domain(session_obj)
            
            # Fallback: return minimal session
            return ChatSession(
                id=session_id,
                name=name,
                is_active=False,
                message_count=0,
            )
        except Exception as e:
            print(f"[SessionRepository] Error creating session: {e}")
            raise
    
    def switch_to(self, session_id: int) -> Optional[ChatSession]:
        """Switch to session and return it."""
        try:
            LegacyDatabase.switch_session(session_id)
            return self.get_active()
        except Exception as e:
            print(f"[SessionRepository] Error switching session: {e}")
            return None
    
    def update(self, session: ChatSession) -> ChatSession:
        """Update session."""
        try:
            LegacyDatabase.rename_session(session.id, session.name)
            # Memory updates go through separate method
            import json
            memory = {
                'session_context': session.memory.context,
                'summary_count': session.memory.summary_count,
            }
            LegacyDatabase.update_session_memory(session.id, memory)
            return session
        except Exception as e:
            print(f"[SessionRepository] Error updating session: {e}")
            raise
    
    def delete(self, session_id: int) -> bool:
        """Delete session."""
        try:
            return LegacyDatabase.delete_session(session_id)
        except Exception as e:
            print(f"[SessionRepository] Error deleting session: {e}")
            return False
