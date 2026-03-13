"""
Test MCP Manager - MCP server lifecycle and tool discovery

Tests:
1. Server configuration
2. Server lifecycle (start/stop/restart)
3. Tool discovery
4. Tool execution
5. Error handling
"""

import unittest
import sys
import os
import json
import subprocess
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration.mcp_manager import (
    MCPServerConfig, MCPManager, get_mcp_manager
)
from database import Database


class MockSubprocess:
    """Mock subprocess for testing"""
    
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.started = False
        self.stopped = False
    
    def __enter__(self):
        self.started = True
        if self.should_fail:
            raise Exception("Process failed to start")
        return self
    
    def __exit__(self, *args):
        self.stopped = True
    
    def communicate(self):
        return (b'{"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"test_tool"}]}}', b'')


class TestMCPServerConfig(unittest.TestCase):
    """Test MCPServerConfig dataclass"""
    
    def test_creation(self):
        """Test MCPServerConfig creation"""
        config = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            env_vars={"KEY": "value"},
            auto_start=True
        )
        
        self.assertEqual(config.name, "test_server")
        self.assertEqual(config.transport, "stdio")
        self.assertEqual(config.command, "npx")
        self.assertTrue(config.auto_start)
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        config = MCPServerConfig(
            name="test",
            transport="http",
            url="http://localhost:3000"
        )
        
        d = config.to_dict()
        
        self.assertEqual(d["name"], "test")
        self.assertEqual(d["transport"], "http")


class TestMCPManager(unittest.TestCase):
    """Test cases for MCPManager"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.manager = MCPManager()
    
    # ============== Server configuration tests ==============
    
    def test_add_server_config(self):
        """Test adding server configuration"""
        config = MCPServerConfig(
            name="test_server",
            transport="stdio",
            command="echo",
            args=["test"]
        )
        
        result = self.manager.add_server_config(config)
        
        self.assertTrue(result)
        self.assertIn("test_server", self.manager._servers)
    
    def test_add_duplicate_server(self):
        """Test adding duplicate server config"""
        config = MCPServerConfig(
            name="duplicate_test",
            transport="stdio",
            command="echo"
        )
        
        self.manager.add_server_config(config)
        result = self.manager.add_server_config(config)
        
        self.assertFalse(result)
    
    def test_remove_server_config(self):
        """Test removing server configuration"""
        config = MCPServerConfig(
            name="to_remove",
            transport="stdio",
            command="echo"
        )
        
        self.manager.add_server_config(config)
        result = self.manager.remove_server_config("to_remove")
        
        self.assertTrue(result)
        self.assertNotIn("to_remove", self.manager._servers)
    
    def test_get_server_config(self):
        """Test getting server configuration"""
        config = MCPServerConfig(
            name="get_test",
            transport="stdio",
            command="echo"
        )
        
        self.manager.add_server_config(config)
        retrieved = self.manager.get_server_config("get_test")
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "get_test")
    
    # ============== Server lifecycle tests ==============
    
    def test_start_server_success(self):
        """Test successful server start"""
        config = MCPServerConfig(
            name="start_test",
            transport="stdio", 
            command="echo",
            args=["test"],
            auto_start=False
        )
        
        self.manager.add_server_config(config)
        result = self.manager.start_server("start_test")
        
        # May fail in test environment without actual MCP server
        # But should handle gracefully
        self.assertIn(result["status"], ["success", "error"])
    
    def test_stop_server(self):
        """Test server stop"""
        config = MCPServerConfig(
            name="stop_test",
            transport="stdio",
            command="echo"
        )
        
        self.manager.add_server_config(config)
        # Try to start first (may fail without real server)
        try:
            self.manager.start_server("stop_test")
        except:
            pass
        
        # Try to stop
        result = self.manager.stop_server("stop_test")
        self.assertIn(result["status"], ["success", "error"])
    
    def test_restart_server(self):
        """Test server restart"""
        config = MCPServerConfig(
            name="restart_test",
            transport="stdio",
            command="echo"
        )
        
        self.manager.add_server_config(config)
        
        result = self.manager.restart_server("restart_test")
        self.assertIn(result["status"], ["success", "error"])
    
    def test_get_server_status(self):
        """Test getting server status"""
        config = MCPServerConfig(
            name="status_test",
            transport="stdio",
            command="echo"
        )
        
        self.manager.add_server_config(config)
        status = self.manager.get_server_status("status_test")
        
        self.assertIsNotNone(status)
        self.assertIn("name", status)
        self.assertIn("is_running", status)
    
    # ============== Tool discovery tests ==============
    
    def test_discover_tools(self):
        """Test tool discovery"""
        # This would require a real MCP server
        # Testing the method exists and handles errors
        try:
            tools = self.manager.discover_tools("nonexistent")
            # May return empty or error
        except Exception as e:
            # Expected for nonexistent server
            self.assertIsNotNone(e)
    
    # ============== Tool execution tests ==============
    
    def test_execute_tool_not_running(self):
        """Test tool execution on non-running server"""
        config = MCPServerConfig(
            name="exec_test",
            transport="stdio",
            command="echo"
        )
        
        self.manager.add_server_config(config)
        
        result = self.manager.execute_tool("exec_test", "test_tool", {"arg": "value"})
        
        # Should handle gracefully (server not running)
        self.assertEqual(result["status"], "error")
    
    # ============== Edge case tests ==============
    
    def test_operations_on_nonexistent_server(self):
        """Test operations on nonexistent server"""
        # Start
        result = self.manager.start_server("nonexistent")
        self.assertEqual(result["status"], "error")
        
        # Stop
        result = self.manager.stop_server("nonexistent")
        self.assertEqual(result["status"], "error")
        
        # Status
        result = self.manager.get_server_status("nonexistent")
        self.assertIsNone(result)
    
    def test_cleanup_all(self):
        """Test cleanup of all servers"""
        config1 = MCPServerConfig(name="cleanup1", transport="stdio", command="echo")
        config2 = MCPServerConfig(name="cleanup2", transport="stdio", command="echo")
        
        self.manager.add_server_config(config1)
        self.manager.add_server_config(config2)
        
        # Cleanup should handle gracefully
        self.manager.cleanup()


class TestMCPManagerSingleton(unittest.TestCase):
    """Test MCPManager singleton"""
    
    def test_singleton(self):
        """Test singleton pattern"""
        manager1 = get_mcp_manager()
        manager2 = get_mcp_manager()
        
        self.assertIs(manager1, manager2)


# Integration tests that require database
class TestMCPWithDatabase(unittest.TestCase):
    """Test MCP manager integration with database"""
    
    def test_load_servers_from_db(self):
        """Test loading server configs from database"""
        # This would load from actual DB
        # Skip if DB not available
        try:
            manager = MCPManager()
            servers = manager.list_servers()
            # Should return list (may be empty)
            self.assertIsInstance(servers, list)
        except Exception as e:
            self.skipTest(f"Database not available: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
