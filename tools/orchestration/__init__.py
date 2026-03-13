"""
Tool Orchestration Package

Provides unified tool execution with:
- Intent detection (LLM-based or keyword)
- Tool routing (internal, MCP stdio, MCP HTTP)
- Result processing (UI-ready format)
"""

from tools.orchestration.intent_detector import (
    IntentDetector,
    ToolIntent,
    get_intent_detector
)

from tools.orchestration.tool_router import (
    ToolRouter,
    ToolType,
    ToolResult,
    get_tool_router
)

from tools.orchestration.result_processor import (
    ResultProcessor,
    CardType,
    ToolCardSpec,
    get_result_processor
)


class ToolOrchestrator:
    """
    Main orchestration class that coordinates intent detection,
    tool execution, and result processing.
    
    This is the primary interface for the tool system.
    """
    
    def __init__(self, ai_manager=None):
        self.ai_manager = ai_manager
        self.intent_detector = get_intent_detector(ai_manager)
        self.tool_router = get_tool_router()
        self.result_processor = get_result_processor()
    
    def process_user_message(
        self,
        user_message: str,
        conversation_context: list = None,
        session_id: int = None
    ) -> dict:
        """
        Process a user message through the full tool pipeline.
        
        Args:
            user_message: The user's input message
            conversation_context: Previous messages for context
            session_id: Current session ID
        
        Returns:
            dict with keys:
            - needs_tool: bool
            - tool_result: ToolCardSpec (if tool executed)
            - llm_commentary_prompt: str (for second pass)
        """
        conversation_context = conversation_context or []
        
        # Step 1: Detect intent
        intent = self.intent_detector.detect(
            user_message,
            conversation_context,
            use_llm=True
        )
        
        if not intent:
            return {
                "needs_tool": False,
                "tool_result": None,
                "llm_commentary_prompt": None
            }
        
        # Step 2: Execute tool
        tool_type = self.tool_router.get_tool_type(intent.tool_name)
        
        tool_result = self.tool_router.execute(
            tool_name=intent.tool_name,
            params=intent.params,
            tool_type=tool_type,
            session_id=session_id
        )
        
        # Step 3: Process result
        card_spec = self.result_processor.process(tool_result)
        
        # Step 4: Generate commentary prompt if needed
        commentary_prompt = None
        if tool_result.success:
            commentary_prompt = self.result_processor.create_llm_commentary_prompt(
                tool_result, card_spec
            )
        
        return {
            "needs_tool": True,
            "intent": intent.to_dict(),
            "tool_result": card_spec.to_dict(),
            "llm_commentary_prompt": commentary_prompt,
            "execution_time_ms": tool_result.execution_time_ms
        }
    
    def execute_tool_direct(
        self,
        tool_name: str,
        params: dict,
        tool_type: str = "internal",
        session_id: int = None
    ) -> dict:
        """
        Directly execute a tool without intent detection.
        
        Used when the tool is already determined (e.g., from command detection).
        """
        # Convert string to ToolType
        if tool_type == "internal":
            enum_tool_type = ToolType.INTERNAL
        elif tool_type == "mcp_stdio":
            enum_tool_type = ToolType.MCP_STDIO
        elif tool_type == "mcp_http":
            enum_tool_type = ToolType.MCP_HTTP
        else:
            enum_tool_type = ToolType.INTERNAL
        
        # Execute
        tool_result = self.tool_router.execute(
            tool_name=tool_name,
            params=params,
            tool_type=enum_tool_type,
            session_id=session_id
        )
        
        # Process result
        card_spec = self.result_processor.process(tool_result)
        
        return {
            "success": tool_result.success,
            "card_spec": card_spec.to_dict(),
            "execution_time_ms": tool_result.execution_time_ms,
            "error": tool_result.error
        }
    
    def shutdown(self):
        """Cleanup resources"""
        self.tool_router.shutdown()


# Default orchestrator instance
_orchestrator = None

def get_orchestrator(ai_manager=None) -> ToolOrchestrator:
    """Get or create ToolOrchestrator singleton"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ToolOrchestrator(ai_manager)
    return _orchestrator


__all__ = [
    # Intent Detection
    "IntentDetector",
    "ToolIntent",
    "get_intent_detector",
    
    # Tool Routing
    "ToolRouter",
    "ToolType",
    "ToolResult",
    "get_tool_router",
    
    # Result Processing
    "ResultProcessor",
    "CardType",
    "ToolCardSpec",
    "get_result_processor",
    
    # Main Orchestrator
    "ToolOrchestrator",
    "get_orchestrator",
]
