# FILE: app/agentic_config.py
# DESCRIPTION: Agentic mode configuration and state management
#              Controls whether Yuzuki uses local tools only or MCP tools too

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def is_agentic_mode_enabled(profile: dict[str, Any] | None = None) -> bool:
    """Check if agentic mode is enabled in the profile.
    
    Returns True if:
      - profile.providers_config.agentic_mode is True
      - ZO_ACCESS_TOKEN is set (has MCP access)
    
    Default is False (local RPC tools only).
    """
    import os
    
    # Must have MCP token first
    if not os.environ.get("ZO_ACCESS_TOKEN"):
        return False
    
    if profile is None:
        try:
            from app.database import Database
            profile = Database.get_profile()
        except Exception:
            return False
    
    if not profile:
        return False
    
    providers_config = profile.get("providers_config") or {}
    return providers_config.get("agentic_mode", False)


def set_agentic_mode(enabled: bool, profile: dict[str, Any] | None = None) -> bool:
    """Enable or disable agentic mode in the profile.
    
    Returns True if successful, False if MCP token not available.
    """
    import os
    
    # Cannot enable without MCP token
    if enabled and not os.environ.get("ZO_ACCESS_TOKEN"):
        log.warning("Cannot enable agentic mode: ZO_ACCESS_TOKEN not set")
        return False
    
    try:
        from app.database import Database
        if profile is None:
            profile = Database.get_profile()
        
        providers_config = profile.get("providers_config") or {}
        providers_config["agentic_mode"] = enabled
        Database.update_profile({"providers_config": providers_config})
        
        log.info(f"Agentic mode {'enabled' if enabled else 'disabled'}")
        return True
    except Exception as e:
        log.error(f"Failed to set agentic mode: {e}")
        return False


def get_agentic_status(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    """Get full agentic mode status including tool counts.
    """
    import os
    from app.tools.registry import get_tool_definitions
    from app.dispatch.hybrid import HybridDispatcher
    
    has_mcp_token = bool(os.environ.get("ZO_ACCESS_TOKEN"))
    enabled = is_agentic_mode_enabled(profile)
    
    local_tools = get_tool_definitions()
    local_count = len(local_tools)
    
    mcp_count = 0
    if has_mcp_token:
        try:
            dispatcher = HybridDispatcher()
            # Lazy init to count MCP tools
            mcp_tools = dispatcher._get_mcp_tools_sync()
            mcp_count = len(mcp_tools)
        except Exception:
            mcp_count = 0
    
    return {
        "enabled": enabled,
        "has_mcp_token": has_mcp_token,
        "local_tools_count": local_count,
        "mcp_tools_count": mcp_count,
        "total_tools_count": local_count + (mcp_count if enabled else 0),
    }
