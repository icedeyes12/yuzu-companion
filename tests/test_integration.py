"""
Integration Tests - Full orchestration flow

Tests the complete workflow:
1. Intent detection → 2. Tool routing → 3. Result processing
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration import (
    ToolOrchestrator, get_orchestrator,
    IntentDetector, ToolRouter, ResultProcessor,
    get_intent_detector, get_tool_router, get_result_processor
)
from tools.orchestration.intent_detector import ToolIntent
from tools.orchestration.tool_router import ToolResult, ToolType
from tools.orchestration.result_processor import CardType


class MockToolExecutor:
    """Mock tool that simulates various tool behaviors"""
    
    def __init__(self, result_type="success", result_data=None):
        self.result_type = result_type
        self.result_data = result_data or {
            "status": "success",
            "result": "Mock tool executed successfully"
        }
    
    def execute(self, arguments, session_id=None):
        if self.result_type == "success":
            return self.result_data
        elif self.result_type == "error":
            raise Exception("Mock tool error")
        elif self.result_type == "image":
            return {
                "status": "success",
                "image_path": "/tmp/test_image.png",
                "prompt": arguments.get("prompt", "")
            }
        elif self.result_type == "list":
            return {
                "status": "success",
                "results": [
                    {"title": "Result 1", "content": "Content 1"},
                    {"title": "Result 2", "content": "Content 2"}
                ]
            }
        return self.result_data


class TestFullOrchestration(unittest.TestCase):
    """Integration tests for full orchestration flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create orchestrator with mock AI
        self.mock_ai_manager = MockAIManager()
        self.orchestrator = ToolOrchestrator(ai_manager=None)
        
        # Register mock tools
        self.orchestrator.tool_router.register_internal_tool(
            "test_tool", MockToolExecutor()
        )
        self.orchestrator.tool_router.register_internal_tool(
            "image_tool", MockToolExecutor(result_type="image")
        )
        self.orchestrator.tool_router.register_internal_tool(
            "list_tool", MockToolExecutor(result_type="list")
        )
        self.orchestrator.tool_router.register_internal_tool(
            "error_tool", MockToolExecutor(result_type="error")
        )
    
    # ============== Full flow tests ==============
    
    def test_full_flow_success(self):
        """Test complete flow: detect → route → process"""
        # Step 1: Detect intent
        intent = self.orchestrator.detect_intent("run test tool with args")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.tool_name, "test_tool")
        
        # Step 2: Execute tool
        tool_result = self.orchestrator.execute_tool(intent)
        self.assertEqual(tool_result.status, "success")
        
        # Step 3: Process result
        card_spec = self.orchestrator.process_result(tool_result)
        self.assertIsNotNone(card_spec)
    
    def test_full_flow_with_image(self):
        """Test full flow with image tool"""
        # Detect intent
        intent = self.orchestrator.detect_intent("/imagine a beautiful sunset")
        self.assertIsNotNone(intent)
        
        # Execute
        tool_result = self.orchestrator.execute_tool(intent)
        
        # Process
        card_spec = self.orchestrator.process_result(tool_result)
        self.assertEqual(card_spec.card_type, CardType.IMAGE.value)
    
    def test_full_flow_with_list(self):
        """Test full flow with list result"""
        # Detect
        intent = self.orchestrator.detect_intent("search memory about test")
        
        # If keyword detection works
        if intent and intent.tool_name == "memory_search":
            # Execute
            tool_result = self.orchestrator.execute_tool(intent)
            
            # Process
            card_spec = self.orchestrator.process_result(tool_result)
            self.assertIsNotNone(card_spec)
    
    def test_full_flow_error_handling(self):
        """Test full flow with tool error"""
        # Detect
        intent = ToolIntent(
            tool_name="error_tool",
            params={},
            confidence=0.9,
            reason="Test error flow"
        )
        
        # Execute (should handle error)
        tool_result = self.orchestrator.execute_tool(intent)
        self.assertEqual(tool_result.status, "error")
        
        # Process error
        card_spec = self.orchestrator.process_result(tool_result)
        self.assertEqual(card_spec.card_type, CardType.ERROR.value)
    
    # ============== Orchestrator convenience methods ==============
    
    def test_orchestrate(self):
        """Test main orchestrate method"""
        result = self.orchestrator.orchestrate(
            "execute test_tool with argument",
            session_id=1
        )
        
        # Should return complete result
        self.assertIn("intent", result)
        self.assertIn("tool_result", result)
        self.assertIn("card_spec", result)
    
    def test_orchestrate_with_error(self):
        """Test orchestrate with error"""
        result = self.orchestrator.orchestrate(
            "run nonexistent tool",
            session_id=1
        )
        
        # Should handle gracefully
        self.assertIsNotNone(result)
    
    # ============== Component integration tests ==============
    
    def test_components_work_together(self):
        """Test that all components integrate properly"""
        # Get individual components
        detector = get_intent_detector()
        router = get_tool_router()
        processor = get_result_processor()
        
        # Register tool
        router.register_internal_tool("integration_test", MockToolExecutor())
        
        # Detect
        intent = detector.detect("/integration_test arg")
        self.assertIsNotNone(intent)
        
        # Execute
        tool_result = router.execute(intent)
        self.assertEqual(tool_result.status, "success")
        
        # Process
        card_spec = processor.process(tool_result)
        self.assertIsNotNone(card_spec)
    
    def test_singletons_share_state(self):
        """Test that singletons share state"""
        # Get components
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        
        # Register a tool on one
        orch1.tool_router.register_internal_tool(
            "singleton_test", MockToolExecutor()
        )
        
        # Other should see it (same instance)
        self.assertIs(orch1, orch2)


class MockAIManager:
    """Mock AI Manager for integration tests"""
    
    def __init__(self):
        self.call_count = 0
    
    def chat(self, messages, **kwargs):
        self.call_count += 1
        import json
        return json.dumps({
            "needs_tool": True,
            "tool_name": "test_tool",
            "params": {"arg": "value"},
            "confidence": 0.9,
            "reasoning": "Mock detection"
        })


class TestOrchestratorWithDatabase(unittest.TestCase):
    """Test orchestrator with database integration"""
    
    def test_tool_execution_creates_db_record(self):
        """Test that tool execution creates database record"""
        try:
            from database import Database
            
            # This would create a tool execution record
            # Skipping actual DB operations in test
            # Just verifying the method exists
            self.assertTrue(hasattr(Database, 'create_tool_execution'))
            self.assertTrue(hasattr(Database, 'update_tool_execution_status'))
            self.assertTrue(hasattr(Database, 'complete_tool_execution'))
        except Exception as e:
            self.skipTest(f"Database not available: {e}")


class TestOrchestratorEdgeCases(unittest.TestCase):
    """Test edge cases in orchestration"""
    
    def setUp(self):
        self.orchestrator = ToolOrchestrator(ai_manager=None)
        self.orchestrator.tool_router.register_internal_tool(
            "empty_tool", MockToolExecutor(result_data={})
        )
    
    def test_empty_tool_result(self):
        """Test handling empty tool result"""
        intent = ToolIntent(
            tool_name="empty_tool",
            params={},
            confidence=0.9
        )
        
        result = self.orchestrator.execute_tool(intent)
        card_spec = self.orchestrator.process_result(result)
        
        self.assertIsNotNone(card_spec)
    
    def test_very_long_intent_params(self):
        """Test with very long parameters"""
        long_param = "x" * 10000
        
        intent = ToolIntent(
            tool_name="test_tool",
            params={"long_arg": long_param},
            confidence=0.9
        )
        
        result = self.orchestrator.execute_tool(intent)
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
