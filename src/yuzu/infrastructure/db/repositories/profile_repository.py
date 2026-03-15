"""SQLAlchemy implementation of ProfileRepository.

Adapts from existing database.py patterns while following Repository pattern.
"""

from typing import Optional, Dict, Any, List
from contextlib import contextmanager

from ....domain.interfaces.db_interface import ProfileRepository
from ....domain.models import Profile, PartnerProfile, UserPreferences, ApiKeys


# Import from existing database to leverage schema
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from database import Database as LegacyDatabase, Profile as ProfileModel, APIKey as APIKeyModel


class SQLAlchemyProfileRepository(ProfileRepository):
    """Profile repository using SQLAlchemy."""
    
    def __init__(self, session_factory=None):
        self._session_factory = session_factory
    
    def _map_to_domain(self, db_profile: ProfileModel) -> Profile:
        """Map database profile to domain model."""
        import json
        
        # Parse JSON fields
        memory = json.loads(db_profile.memory_json or '{}')
        providers_config = json.loads(db_profile.providers_config_json or '{}')
        context = json.loads(db_profile.context or '{}')
        
        # Extract partner info
        partner = PartnerProfile(
            name=db_profile.partner_name,
            relationship_stage="",  # Could be derived from affection
            personality=""  # Could be stored in memory
        )
        
        # Extract preferences
        preferences = UserPreferences(
            providers_config=providers_config,
            image_model=db_profile.image_model or 'hunyuan',
            vision_model=db_profile.vision_model or 'moonshotai/Kimi-K2.5-TEE',
            streaming_enabled=providers_config.get('streaming_enabled', False),
            preferred_provider=providers_config.get('preferred_provider', 'ollama'),
            preferred_model=providers_config.get('preferred_model', 'glm-4.6:cloud'),
        )
        
        # Build API keys (loaded lazily)
        api_keys = ApiKeys()
        
        return Profile(
            id=db_profile.id,
            display_name=db_profile.display_name or 'bani',
            partner=partner,
            affection=db_profile.affection or 85,
            theme=db_profile.theme or 'default',
            preferences=preferences,
            api_keys=api_keys,  # Will be loaded on demand
            memory=memory,
            global_knowledge=json.loads(db_profile.global_knowledge_json or '{}'),
            context=context,
            created_at=db_profile.created_at,
            updated_at=db_profile.updated_at,
        )
    
    def _map_to_db(self, profile: Profile, db_profile: ProfileModel) -> None:
        """Map domain profile to database model."""
        import json
        
        db_profile.display_name = profile.display_name
        db_profile.partner_name = profile.partner.name if profile.partner else 'Yuzu'
        db_profile.affection = profile.affection
        db_profile.theme = profile.theme or 'default'
        db_profile.memory_json = json.dumps(profile.memory)
        db_profile.providers_config_json = json.dumps(profile.preferences.providers_config)
        db_profile.global_knowledge_json = json.dumps(profile.global_knowledge)
        db_profile.context = json.dumps(profile.context)
        db_profile.image_model = profile.preferences.image_model
        db_profile.vision_model = profile.preferences.vision_model
    
    def get(self) -> Optional[Profile]:
        """Get current user profile."""
        try:
            db_profile = LegacyDatabase.get_profile()
            if db_profile:
                return self._map_to_domain(db_profile)
            return None
        except Exception as e:
            # Log error
            print(f"[ProfileRepository] Error getting profile: {e}")
            return None
    
    def update(self, profile: Profile) -> Profile:
        """Update profile."""
        try:
            import json
            updates = {
                'display_name': profile.display_name,
                'partner_name': profile.partner.name if profile.partner else 'Yuzu',
                'affection': profile.affection,
                'theme': profile.theme,
                'memory_json': json.dumps(profile.memory),
                'providers_config_json': json.dumps(profile.preferences.providers_config),
                'global_knowledge_json': json.dumps(profile.global_knowledge),
                'context': json.dumps(profile.context),
                'image_model': profile.preferences.image_model,
                'vision_model': profile.preferences.vision_model,
            }
            LegacyDatabase.update_profile(updates)
            return profile
        except Exception as e:
            print(f"[ProfileRepository] Error updating profile: {e}")
            raise
    
    def get_api_keys(self) -> Dict[str, str]:
        """Get API keys for user."""
        try:
            return LegacyDatabase.get_api_keys()
        except Exception as e:
            print(f"[ProfileRepository] Error getting API keys: {e}")
            return {}
    
    def save_api_key(self, provider: str, key: str) -> bool:
        """Save API key for provider."""
        try:
            return LegacyDatabase.save_api_key(provider, key)
        except Exception as e:
            print(f"[ProfileRepository] Error saving API key: {e}")
            return False
    
    def update_api_keys(self, api_keys: Dict[str, str]) -> bool:
        """Update multiple API keys."""
        try:
            for provider, key in api_keys.items():
                LegacyDatabase.save_api_key(provider, key)
            return True
        except Exception as e:
            print(f"[ProfileRepository] Error updating API keys: {e}")
            return False
