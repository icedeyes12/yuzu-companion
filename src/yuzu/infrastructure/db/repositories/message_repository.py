"""SQLAlchemy implementation of MessageRepository."""

from typing import Optional, List, Dict, Any
from datetime import datetime

from ....domain.interfaces.db_interface import MessageRepository
from ....domain.models import Message, MessageRole


import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from database import Database as LegacyDatabase, Message as MessageModel, TOOL_ROLES


class SQLAlchemyMessageRepository(MessageRepository):
    """Message repository using SQLAlchemy."""
    
    def _map_to_domain(self, db_message: MessageModel) -> Message:
        """Map database message to domain model."""
        # Parse image paths
        import json
        image_paths = None
        if db_message.image_paths:
            try:
                image_paths = json.loads(db_message.image_paths)
            except:
                image_paths = None
        
        # Determine role
        role = MessageRole(db_message.role) if db_message.role in [r.value for r in MessageRole] else MessageRole.ASSISTANT
        
        return Message(
            id=db_message.id,
            session_id=db_message.session_id,
            role=role,
            content=db_message.content,
            timestamp=datetime.strptime(db_message.timestamp, '%Y-%m-%d %H:%M:%S') if isinstance(db_message.timestamp, str) else db_message.timestamp,
            image_paths=image_paths,
        )
    
    def _map_to_db(self, message: Message) -> Dict[str, Any]:
        """Map domain message to database dict."""
        import json
        return {
            'session_id': message.session_id,
            'role': message.role.value,
            'content': message.content,
            'image_paths': json.dumps(message.image_paths) if message.image_paths else None,
        }
    
    def get_history(
        self,
        session_id: int,
        limit: int = 50,
        include_tools: bool = True
    ) -> List[Message]:
        """Get chat history for session."""
        try:
            # Get from legacy database
            history = LegacyDatabase.get_chat_history(session_id=session_id)
            
            messages = []
            for msg in history[-limit:]:  # Get last 'limit' messages
                role = MessageRole(msg.get('role', 'assistant'))
                
                # Skip tool messages if not requested
                if not include_tools and role in [
                    MessageRole.TOOL, MessageRole.IMAGE_TOOLS, 
                    MessageRole.REQUEST_TOOLS, MessageRole.MEMORY_SEARCH_TOOLS
                ]:
                    continue
                
                messages.append(Message(
                    id=msg.get('id', 0),
                    session_id=session_id,
                    role=role,
                    content=msg.get('content', ''),
                    timestamp=datetime.strptime(msg.get('timestamp', ''), '%Y-%m-%d %H:%M:%S') 
                        if msg.get('timestamp') else datetime.now(),
                ))
            
            return messages
        except Exception as e:
            print(f"[MessageRepository] Error getting history: {e}")
            return []
    
    def get_history_for_ai(
        self,
        session_id: int,
        limit: int = 25,
    ) -> List[Message]:
        """Get history formatted for LLM context."""
        try:
            # Use legacy method
            history = LegacyDatabase.get_chat_history_for_ai(session_id=session_id, limit=limit)
            
            messages = []
            for msg in history:
                messages.append(Message(
                    id=0,  # Not available in dict format
                    session_id=session_id,
                    role=MessageRole(msg.get('role', 'assistant')),
                    content=msg.get('content', ''),
                    timestamp=datetime.now(),  # Not available in dict format
                ))
            
            return messages
        except Exception as e:
            print(f"[MessageRepository] Error getting AI history: {e}")
            return []
    
    def add(self, message: Message) -> Message:
        """Add message to session."""
        try:
            LegacyDatabase.add_message(
                role=message.role.value,
                content=message.content,
                session_id=message.session_id,
                image_paths=message.image_paths,
            )
            return message
        except Exception as e:
            print(f"[MessageRepository] Error adding message: {e}")
            raise
    
    def add_tool_result(
        self,
        session_id: int,
        tool_name: str,
        result_content: str,
    ) -> Message:
        """Add tool result message."""
        try:
            LegacyDatabase.add_tool_result(tool_name, result_content, session_id)
            
            return Message(
                id=0,
                session_id=session_id,
                role=MessageRole.TOOL,
                content=result_content,
            )
        except Exception as e:
            print(f"[MessageRepository] Error adding tool result: {e}")
            raise
    
    def clear_session(self, session_id: int) -> bool:
        """Clear all messages in session (legacy name, deprecated)."""
        return self.clear_history(session_id)
    
    def clear_history(self, session_id: int) -> bool:
        """Clear all messages in session."""
        try:
            LegacyDatabase.clear_chat_history(session_id)
            return True
        except Exception as e:
            print(f"[MessageRepository] Error clearing session: {e}")
            return False
