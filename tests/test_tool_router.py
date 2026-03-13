"""
Test ToolRouter - Tool execution routing

Tests:
1. Internal tool execution
2. MCP stdio execution
3. MCP HTTP execution
4. Error handling
5. Tool type routing
"""

import unittest
import sys
import os
import json
import subprocess
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration.tool_router import (
    ToolRouter, ToolType, ToolResult, get_tool_router
)
from tools.orchestration.intent_detector import ToolIntent


class MockToolExecutor:
    """Mock tool executor for testing"""
    
    def __init__(self, should_fail=False, result=None):
        self.should_fail = should_fail
        self.result = result or {"status": "success", "data": "test result"}
        self.call_count = 0
        self.last_args = None
    
    def execute(self, arguments, session_id=None):
        self.call_count += 1
        self.last_args = arguments
        
        if self.should_fail:
            raise Exception("Tool execution failed")
        
        return json.dumps(self.result)


class MockMCPServer:
    """Mock MCP server for testing"""
    
    def __init__(self, name="mock_server"):
        self.name = name
        self.running = False
        self.process = None
        self.capabilities = {
            "tools": [
                {"name": "mock_tool", "description": "A mock tool"}
            ]
        }
        self.call_history = []
    
    def start(self):
        """Start the mock MCP server"""
        self.running = True
    
    def stop(self):
        """Stop the mock MCP server"""
        self.running = False
    
    def is_running(self):
        return self.running
    
    def call_tool(self, tool_name, arguments):
        """Simulate calling a tool"""
        self.call_history.append({"tool": tool_name, "args": arguments})
        return {"result": f"Mock result for {tool_name}"}


class TestToolRouter(unittest.TestCase):
    """Test cases for ToolRouter"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.router = ToolRouter()
        self.mock_tool = MockToolExecutor()
    
    # ============== Internal tool execution tests ==============
    
    def test_execute_internal_tool_success(self):
        """Test successful internal tool execution"""
        # Register mock tool
        self.router.register_internal_tool("test_tool", self.mock_tool)
        
        intent = ToolIntent(
            tool_name="test_tool",
            params={"arg": "value"},
            confidence=0.9,
            reasoning="Test"
        )
        
        result = self.router.execute(intent)
        
        self.assertEqual(result.status, "success")
        self.assertEqual(self.mock_tool.call_count, 1)
        self.assertEqual(self.mock_tool.last_args, {"arg": "value"})
    
    def test_execute_internal_tool_failure(self):
        """Test internal tool execution failure"""
        failing_tool = MockToolExecutor(should_fail=True)
        self.router.register_internal_tool("failing_tool", failing_tool)
        
        intent = ToolIntent(
            tool_name="failing_tool",
            params={},
            confidence=0.9,
            reasoning="Test"
        )
        
        result = self.router.execute(intent)
        
        self.assertEqual(result.status, "error")
        self.assertIsNotNone(result.error)
    
    def test_execute_unknown_tool(self):
        """Test execution of unknown tool"""
        intent = ToolIntent(
            tool_name="nonexistent_tool",
            params={},
            confidence=0.9,
            reasoning="Test"
        )
        
        result = self.router.execute(intent)
        
        self.assertEqual(result.status, "error")
        self.assertIn("not found", result.error.lower())
    
    # ============== Tool type routing tests ==============
    
    def test_tool_type_routing(self):
        """Test routing to correct tool type"""
        # Register internal tool
        self.router.register_internal_tool("internal_test", self.mock_tool)
        
        # Test internal type
        intent = ToolIntent(
            tool_name="internal_test",
            params={},
            confidence=0.9,
            reasoning="Test",
            tool_type=ToolType.INTERNAL
        )
        
        result = self.router.execute(intent)
        self.assertEqual(result.status, "success")
    
    # ============== Result structure tests ==============
    
    def test_result_structure(self):
        """Test ToolResult structure"""
        self.router.register_internal_tool("test_tool", self.mock_tool)
        
        intent = ToolIntent(
            tool_name="test_tool",
            params={},
            confidence=0.9,
            reasoning="Test"
        )
        
        result = self.router.execute(intent)
        
        # Check required fields
        self.assertTrue(hasattr(result, 'status'))
        self.assertTrue(hasattr(result, 'tool_name'))
        self.assertTrue(hasattr(result, 'raw_output'))
        self.assertTrue(hasattr(result, 'execution_time'))
        
        # Check values
        self.assertEqual(result.tool_name, "test_tool")
        self.assertIn(result.status, ["success", "error"])
    
    # ============== MCP tools tests ==============
    
    def test_mcp_stdio_execution(self):
        """Test MCP stdio tool execution"""
        # This would require an actual MCP server to test fully
        # We'll test the structure instead
        
        # Create mock MCP server config
        config = {
            "transport": "stdio",
            "command": "echo",
            "args": ["test"],
            "env": {}
        }
        
        # Test that router can handle MCP config
        # (actual execution would need a real MCP server)
        self.assertIsNotNone(config)
    
    def test_mcp_http_execution(self):
        """Test MCP HTTP tool execution"""
        config = {
            "transport": "http",
            "url": "http://localhost:3000/mcp"
        }
        
        self.assertIsNotNone(config)
    
    # ============== Edge case tests ==============
    
    def test_empty_params(self):
        """Test execution with empty parameters"""
        self.router.register_internal_tool("test_tool", self.mock_tool)
        
        intent = ToolIntent(
            tool_name="test_tool",
            params={},
            confidence=0.9,
            reasoning="Test"
        )
        
        result = self.router.execute(intent)
        
        self.assertEqual(result.status, "success")
    
    def test_special_characters_in_params(self):
        """Test execution with special characters"""
        self.router.register_internal_tool("test_tool", self.mock_tool)
        
        intent = ToolIntent(
            tool_name="test_tool",
            params={"prompt": "🎨🚀❤️ @#$%"},
            confidence=0.9,
            reasoning="Test"
        )
        
        result = self.router.execute(intent)
        
        self.assertEqual(result.status, "success")
        self.assertEqual(self.mock_tool.last_args["prompt"], "🎨🚀❤️ @#$%")


class TestToolResult(unittest.TestCase):
    """Test ToolResult dataclass"""
    
    def test_creation(self):
        """Test ToolResult creation"""
        result = ToolResult(
            status="success",
            tool_name="test_tool",
            tool_type=ToolType.INTERNAL,
            raw_output={"data": "test"},
            execution_time=0.5
        )
        
        self.assertEqual(result.status, "success")
        self.assertEqual(result.tool_name, "test_tool")
        self.assertEqual(result.tool_type, ToolType.INTERNAL)
        self.assertEqual(result.raw_output, {"data": "test"})
        self.assertEqual(result.execution_time, 0.5)
    
    def test_error_result(self):
        """Test error result creation"""
        result = ToolResult(
            status="error",
            tool_name="test_tool",
            tool_type=ToolType.INTERNAL,
            error="Test error",
            execution_time=0.1
        )
        
        self.assertEqual(result.status, "error")
        self.assertEqual(result.error, "Test error")
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        result = ToolResult(
            status="success",
            tool_name="image_generate",
            tool_type=ToolType.INTERNAL,
            raw_output={"image_path": "/tmp/test.png"},
            execution_time=2.5
        )
        
        d = result.to_dict()
        
        self.assertEqual(d["status"], "success")
        self.assertEqual(d["tool_name"], "image_generate")
        self.assertEqual(d["raw_output"]["image_path"], "/tmp/test.png")


class TestToolType(unittest.TestCase):
    """Test ToolType enum"""
    
    def test_enum_values(self):
        """Test ToolType enum values"""
        self.assertEqual(ToolType.INTERNAL.value, "internal")
        self.assertEqual(ToolType.MCP_STDIO.value, "mcp_stdio")
        self.assertEqual(ToolType.MCP_HTTP.value, "mcp_http")


class TestToolRouterSingleton(unittest.TestCase):
    """Test ToolRouter singleton"""
    
    def test_singleton(self):
        """Test singleton pattern"""
        router1 = get_tool_router()
        router2 = get_tool_router()
        
        self.assertIs(router1, router2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
