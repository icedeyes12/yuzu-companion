#!/usr/bin/env python3
"""
Comprehensive test for Yuzu Agentic/Coding Agent
Tests all Phase 1-4 functionality
"""

import sys
import os

# Add to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.orchestration.mcp_manager import get_mcp_manager
from tools.orchestration.agentic_loop import AgenticToolLoop
from tools.registry import build_markdown_contract

def test_mcp_servers():
    """Test all MCP servers start and have tools"""
    print("=" * 60)
    print("TEST 1: MCP Servers")
    print("=" * 60)
    
    m = get_mcp_manager()
    servers_to_test = ['shell', 'filesystem', 'memory', 'git', 'fetch']
    
    results = {}
    for server_name in servers_to_test:
        try:
            print(f"\nTesting {server_name}...")
            success = m.start_server(server_name)
            if success:
                instance = m.get_server(server_name)
                if instance:
                    tool_count = len(instance.tools)
                    print(f"  ✓ {server_name}: {tool_count} tools")
                    results[server_name] = {"status": "ok", "tools": tool_count}
                else:
                    print(f"  ✗ {server_name}: Server started but no instance")
                    results[server_name] = {"status": "error", "error": "no instance"}
            else:
                print(f"  ✗ {server_name}: Failed to start")
                results[server_name] = {"status": "error", "error": "start failed"}
        except Exception as e:
            print(f"  ✗ {server_name}: {e}")
            results[server_name] = {"status": "error", "error": str(e)}
    
    return results


def test_shell_tool():
    """Test shell tool execution and output extraction"""
    print("\n" + "=" * 60)
    print("TEST 2: Shell Tool (Phase 1.1)")
    print("=" * 60)
    
    m = get_mcp_manager()
    
    try:
        result = m.call_tool('shell', 'execute_command', {'command': 'echo "Hello from Yuzu"'})
        
        if result.get('success'):
            output = result.get('result', {})
            content = output.get('content', [])
            if content and 'text' in content[0]:
                text = content[0]['text']
                if 'Hello from Yuzu' in text:
                    print("  ✓ Shell tool output extraction works")
                    return {"status": "ok"}
                else:
                    print(f"  ✗ Output doesn't contain expected text: {text[:100]}")
                    return {"status": "error", "error": "wrong output"}
            else:
                print(f"  ✗ No content in output: {output}")
                return {"status": "error", "error": "no content"}
        else:
            print(f"  ✗ Shell command failed: {result.get('error')}")
            return {"status": "error", "error": result.get('error')}
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return {"status": "error", "error": str(e)}


def test_filesystem_tools():
    """Test filesystem read/write tools (Phase 1.2)"""
    print("\n" + "=" * 60)
    print("TEST 3: Filesystem Tools (Phase 1.2)")
    print("=" * 60)
    
    m = get_mcp_manager()
    test_file = '/home/workspace/yuzu_test_file.txt'
    
    try:
        # Test write_file
        print("  Testing write_file...")
        write_result = m.call_tool('filesystem', 'write_file', {
            'path': test_file,
            'content': 'Test content from Yuzu agent'
        })
        
        if not write_result.get('success'):
            print(f"  ✗ write_file failed: {write_result.get('error')}")
            return {"status": "error", "error": "write failed"}
        print("  ✓ write_file works")
        
        # Test read_file
        print("  Testing read_file...")
        read_result = m.call_tool('filesystem', 'read_file', {'path': test_file})
        
        if not read_result.get('success'):
            print(f"  ✗ read_file failed: {read_result.get('error')}")
            return {"status": "error", "error": "read failed"}
        
        content = read_result.get('result', {}).get('content', [{}])[0].get('text', '')
        if 'Test content from Yuzu agent' in content:
            print("  ✓ read_file works")
        else:
            print(f"  ✗ read_file wrong content: {content[:100]}")
            return {"status": "error", "error": "wrong content"}
        
        # Cleanup
        os.remove(test_file)
        
        # Test directory_tree
        print("  Testing directory_tree...")
        tree_result = m.call_tool('filesystem', 'directory_tree', {
            'path': '/home/workspace/yuzu-companion',
            'depth': 1
        })
        
        if tree_result.get('success'):
            print("  ✓ directory_tree works")
        else:
            print(f"  ⚠ directory_tree: {tree_result.get('error')}")
        
        return {"status": "ok"}
        
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return {"status": "error", "error": str(e)}


def test_simplified_agentic_loop():
    """Test simplified agentic loop (Phase 2.1)"""
    print("\n" + "=" * 60)
    print("TEST 4: Simplified Agentic Loop (Phase 2.1)")
    print("=" * 60)
    
    try:
        loop = AgenticToolLoop({}, 1)
        
        # Test simple execution (no retry loop)
        cmd_info = {
            'type': 'mcp',
            'server': 'shell',
            'command': 'execute_command',
            'args': 'echo "test"'
        }
        
        attempt = loop.execute(cmd_info)
        
        if attempt.error:
            print(f"  ✗ Execution failed: {attempt.error}")
            return {"status": "error", "error": attempt.error}
        
        if 'test' in (attempt.result or ''):
            print("  ✓ Single-pass execution works (no confusing retry)")
            return {"status": "ok"}
        else:
            print(f"  ✗ Wrong result: {attempt.result[:100]}")
            return {"status": "error", "error": "wrong result"}
            
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return {"status": "error", "error": str(e)}


def test_tool_card_features():
    """Test tool card UI features (Phase 2.2)"""
    print("\n" + "=" * 60)
    print("TEST 5: Tool Card Features (Phase 2.2)")
    print("=" * 60)
    
    try:
        # Test markdown contract generation
        output_lines = ["Line 1", "Line 2", "Line 3"]
        contract = build_markdown_contract(
            "test_tools",
            "/test command",
            output_lines,
            "Yuzu"
        )
        
        # Verify contract structure
        checks = [
            ('<details>' in contract, "details tag"),
            ('<summary>' in contract, "summary tag"),
            ('🔧 test_tools' in contract, "tool role"),
            ('Yuzu$ /test command' in contract, "command"),
            ('> Line 1' in contract, "output lines"),
        ]
        
        all_ok = True
        for check, name in checks:
            if check:
                print(f"  ✓ {name}")
            else:
                print(f"  ✗ {name}")
                all_ok = False
        
        if all_ok:
            return {"status": "ok"}
        else:
            return {"status": "error", "error": "contract format issues"}
            
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return {"status": "error", "error": str(e)}


def test_git_server():
    """Test git server (Phase 4.1)"""
    print("\n" + "=" * 60)
    print("TEST 6: Git Server (Phase 4.1)")
    print("=" * 60)
    
    m = get_mcp_manager()
    
    try:
        # Check git server is running
        instance = m.get_server('git')
        if not instance:
            print("  ⚠ Git server not running, trying to start...")
            m.start_server('git')
            instance = m.get_server('git')
        
        if instance and instance.status.value == 'running':
            tool_names = [t.name for t in instance.tools]
            expected = ['git_status', 'git_log', 'git_diff', 'git_branch', 'git_show']
            
            found = [t for t in expected if t in tool_names]
            print(f"  ✓ Git server running with {len(found)}/5 tools")
            for tool in found:
                print(f"    - {tool}")
            
            if len(found) == 5:
                return {"status": "ok"}
            else:
                return {"status": "partial", "tools_found": len(found)}
        else:
            print("  ✗ Git server not available")
            return {"status": "error", "error": "server not running"}
            
    except Exception as e:
        print(f"  ✗ Exception: {e}")
        return {"status": "error", "error": str(e)}


def run_all_tests():
    """Run all tests and print summary"""
    print("\n" + "=" * 60)
    print("YUZU AGENTIC/CODING AGENT - COMPREHENSIVE TEST")
    print("=" * 60)
    
    results = {}
    
    results['mcp_servers'] = test_mcp_servers()
    results['shell_tool'] = test_shell_tool()
    results['filesystem_tools'] = test_filesystem_tools()
    results['agentic_loop'] = test_simplified_agentic_loop()
    results['tool_cards'] = test_tool_card_features()
    results['git_server'] = test_git_server()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    all_ok = True
    for test_name, result in results.items():
        status = result.get('status', 'unknown')
        if status == 'ok':
            print(f"  ✓ {test_name}")
        elif status == 'partial':
            print(f"  ⚠ {test_name} (partial)")
            all_ok = False
        else:
            print(f"  ✗ {test_name}: {result.get('error', 'failed')}")
            all_ok = False
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ ALL TESTS PASSED")
    else:
        print("⚠️  SOME TESTS FAILED")
    print("=" * 60)
    
    return all_ok


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
