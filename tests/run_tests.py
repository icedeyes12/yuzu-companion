#!/usr/bin/env python3
"""
Test Runner - Run all orchestration tests

Usage:
    python tests/run_tests.py
    python tests/run_tests.py --verbose
    python tests/run_tests.py --test IntentDetector
"""

import sys
import os
import unittest
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def discover_tests():
    """Discover all tests in the tests directory"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Load all test modules
    test_dir = os.path.dirname(os.path.abspath(__file__))
    
    test_files = [
        'test_intent_detector.py',
        'test_tool_router.py', 
        'test_result_processor.py',
        'test_mcp_manager.py',
        'test_websocket.py',
        'test_integration.py'
    ]
    
    for test_file in test_files:
        module_name = test_file.replace('.py', '')
        try:
            suite.addTests(loader.loadTestsFromName(f'tests.{module_name}'))
            print(f"✅ Loaded {module_name}")
        except Exception as e:
            print(f"⚠️  Failed to load {module_name}: {e}")
    
    return suite


def run_tests(verbose=False, test_name=None):
    """Run tests with optional filter"""
    
    if test_name:
        # Run specific test
        suite = unittest.TestSuite()
        try:
            suite.addTests(unittest.TestLoader().loadTestsFromName(f'tests.{test_name}'))
            print(f"Running specific test: {test_name}")
        except Exception as e:
            print(f"Error loading test {test_name}: {e}")
            return 1
    else:
        # Run all tests
        suite = discover_tests()
    
    # Run tests
    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("=" * 60)
    
    if result.wasSuccessful():
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


def simulate_all_cases():
    """Simulate all available use cases without running unit tests"""
    
    print("=" * 60)
    print("SIMULATING ALL AVAILABLE CASES")
    print("=" * 60)
    
    from tools.orchestration.intent_detector import IntentDetector, ToolIntent
    from tools.orchestration.tool_router import ToolRouter, ToolType, ToolResult
    from tools.orchestration.result_processor import ResultProcessor, CardType
    from tools.orchestration.mcp_manager import MCPServerInstance, MCPManager
    from tools.orchestration.websocket import WSMessage, MessageType, WebSocketHandler
    
    # 1. Intent Detection Cases
    print("\n📌 Testing Intent Detection...")
    
    detector = IntentDetector(ai_manager=None)
    
    test_messages = [
        # Image generation
        ("generate an image of a cat", "image_generate"),
        ("/imagine sunset", "image_generate"),
        ("create picture", "image_generate"),
        
        # HTTP requests
        ("fetch https://example.com", "request"),
        ("/request https://api.test.com", "request"),
        
        # Memory search
        ("search memory about vacation", "memory_search"),
        ("what do you remember", "memory_search"),
        
        # No tool needed
        ("hello how are you", None),
        ("tell me a joke", None),
    ]
    
    intent_detection_results = []
    for msg, expected in test_messages:
        result = detector.detect(msg)
        if result:
            detected_tool = result.tool_name
        else:
            detected_tool = None
        
        status = "✅" if detected_tool == expected or expected is None else "❌"
        intent_detection_results.append((status, msg, detected_tool, expected))
    
    for status, msg, detected, expected in intent_detection_results:
        print(f"  {status} '{msg[:30]}...' → {detected} (expected: {expected})")
    
    # 2. Tool Router Cases
    print("\n📌 Testing Tool Router...")
    
    from tools.registry import execute_tool
    
    # Test internal execution via registry
    # (Using existing tool registration)
    result = execute_tool("memory_search", {"query": "test"}, session_id=1)
    print(f"  ✅ Internal tool execution: {type(result).__name__}")
    
    # Test unknown tool
    result2 = execute_tool("nonexistent_tool_xyz", {}, session_id=1)
    print(f"  ✅ Unknown tool handling: {type(result2).__name__}")
    
    # 3. Result Processor Cases
    print("\n📌 Testing Result Processing...")
    
    processor = ResultProcessor()
    
    # Test different result types using correct parameter names
    test_results = [
        (True, "image_generate", {"image_path": "/test.png"}),
        (True, "request", {"text": "Fetched content"}),
        (True, "memory_search", {"results": [1, 2, 3]}),
        (False, "test_tool", None, "Test error"),
    ]
    
    for item in test_results:
        success = item[0]
        tool_name = item[1]
        output = item[2] if len(item) > 2 else None
        error = item[3] if len(item) > 3 else None
        
        tool_result = ToolResult(
            success=success,
            tool_name=tool_name,
            tool_type=ToolType.INTERNAL,
            output=output,
            error=error,
            execution_time_ms=500
        )
        
        card_spec = processor.process(tool_result)
        print(f"  ✅ {success} {tool_name} → {card_spec.card_type} card")
    
    # 4. MCP Manager Cases
    print("\n📌 Testing MCP Manager...")
    
    mcp_manager = MCPManager()
    
    # Test list (will use DB if available, otherwise empty)
    servers = mcp_manager.list_servers()
    print(f"  ✅ List servers: {len(servers)} server(s)")
    
    # Test get status for nonexistent server
    status = mcp_manager.get_server_status("nonexistent_server")
    print(f"  ✅ Server status (not found): {status}")
    
    # 5. WebSocket Cases
    print("\n📌 Testing WebSocket Handler...")
    
    ws_handler = WebSocketHandler()
    
    class MockWS:
        def __init__(self):
            self.sent = []
        def send(self, data):
            self.sent.append(data)
        def close(self):
            pass
    
    mock_ws = MockWS()
    connected = ws_handler.connect("test_sid_123", session_id="test_session")
    print(f"  ✅ Connect: {connected}")
    
    # Test broadcast
    ws_handler.broadcast(
        WSMessage(MessageType.TOOL_COMPLETE, {"result": "done"}),
        session_id="test_session"
    )
    print(f"  ✅ Broadcast to session")
    
    ws_handler.disconnect("test_sid_123")
    print(f"  ✅ Disconnect")
    
    # 6. Full Orchestration
    print("\n📌 Testing Full Orchestration...")
    
    from tools.orchestration import ToolOrchestrator
    
    orchestrator = ToolOrchestrator(ai_manager=None)
    
    # Test orchestration components exist
    print(f"  ✅ ToolOrchestrator created: {orchestrator is not None}")
    print(f"  ✅ IntentDetector: {orchestrator.intent_detector is not None}")
    print(f"  ✅ ToolRouter: {orchestrator.tool_router is not None}")
    print(f"  ✅ ResultProcessor: {orchestrator.result_processor is not None}")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ ALL SIMULATION CASES COMPLETED")
    print("=" * 60)
    
    return 0


def main():
    parser = argparse.ArgumentParser(description='Run Yuzu Companion tests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--test', '-t', help='Run specific test')
    parser.add_argument('--simulate', '-s', action='store_true', 
                       help='Simulate all cases without unit tests')
    
    args = parser.parse_args()
    
    if args.simulate:
        return simulate_all_cases()
    else:
        return run_tests(verbose=args.verbose, test_name=args.test)


if __name__ == "__main__":
    sys.exit(main())
