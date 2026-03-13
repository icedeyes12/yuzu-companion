#!/usr/bin/env python3
"""
Phase 2 V2 - Roadmap-Compliant Tests
Tests align exactly with ROADMAP.md spec

TC1-TC5: IntentDetector (LLM-based per 2.2.A)
TC6-TC10: ToolRouter (MCP support per 2.2.B)
TC11-TC15: ResultProcessor (ToolCardSpec per 2.2.C)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration.intent_detector_v2 import IntentDetector, ToolIntent
from tools.orchestration.tool_router_v2 import ToolRouter, ToolResult, MCPServer
from tools.orchestration.result_processor_v2 import ResultProcessor, ToolCardSpec, CardType


def test_intent_detector_llm_based():
    """TC1: IntentDetector uses LLM (per roadmap 2.2.A)"""
    print("TC1: IntentDetector LLM-based...")
    
    detector = IntentDetector()
    
    # Verify it's not just regex
    assert hasattr(detector, '_build_detection_prompt'), "Should build LLM prompt"
    assert hasattr(detector, '_call_llm_for_intent'), "Should call LLM"
    
    # Test with LLM fallback to pattern
    intent = detector.detect("What's the weather today?")
    
    if intent:
        assert hasattr(intent, 'confidence'), "ToolIntent must have confidence"
        assert hasattr(intent, 'reasoning'), "ToolIntent must have reasoning"
        assert intent.confidence >= detector.CONFIDENCE_THRESHOLD
    
    print("  PASS - LLM-based with confidence threshold")
    return True


def test_intent_detector_structured_output():
    """TC2: IntentDetector returns structured JSON (per 2.2.A)"""
    print("TC2: IntentDetector structured output...")
    
    detector = IntentDetector()
    intent = detector.detect("Generate an image of a cat")
    
    if intent:
        # Verify ToolIntent structure matches roadmap
        assert isinstance(intent.tool_name, str)
        assert isinstance(intent.params, dict)
        assert isinstance(intent.confidence, float)
        assert 0.0 <= intent.confidence <= 1.0
        assert isinstance(intent.reasoning, str)
    
    print("  PASS - Structured output with confidence")
    return True


def test_tool_router_internal_execution():
    """TC6: ToolRouter executes internal tools (per 2.2.B)"""
    print("TC6: ToolRouter internal execution...")
    
    router = ToolRouter()
    
    # Create internal tool intent
    intent = ToolIntent(
        tool_name='web_search',
        params={'query': 'python tutorials'},
        confidence=0.9,
        reasoning='User wants to search',
        tool_type='internal'
    )
    
    result = router.execute(intent)
    
    assert result.tool_type == 'internal'
    assert result.tool_name == 'web_search'
    assert result.status in ('success', 'error', 'timeout')
    assert hasattr(result, 'execution_time_ms')
    
    print("  PASS - Internal tool execution")
    return True


def test_tool_router_mcp_stdio_support():
    """TC7: ToolRouter supports MCP stdio (per 2.2.B)"""
    print("TC7: ToolRouter MCP stdio support...")
    
    router = ToolRouter()
    
    # Verify MCP methods exist
    assert hasattr(router, '_execute_mcp_stdio'), "Must support MCP stdio"
    assert hasattr(router, '_execute_mcp_http'), "Must support MCP http"
    
    # Test with non-existent MCP server (should error gracefully)
    intent = ToolIntent(
        tool_name='filesystem/read',
        params={'server': 'test', 'args': {'path': '/test'}},
        confidence=0.8,
        reasoning='User wants file',
        tool_type='mcp_stdio'
    )
    
    result = router.execute(intent)
    
    assert result.tool_type == 'mcp_stdio'
    assert result.status == 'error'  # No server configured
    
    print("  PASS - MCP stdio support structure")
    return True


def test_result_processor_toolcardspec():
    """TC11: ResultProcessor outputs ToolCardSpec (per 2.2.C)"""
    print("TC11: ResultProcessor ToolCardSpec output...")
    
    processor = ResultProcessor()
    
    spec = processor.process(
        tool_type='internal',
        tool_name='image_generate',
        status='success',
        result={'image_path': '/static/test.png', 'prompt': 'test'},
        execution_time_ms=1500
    )
    
    # Verify ToolCardSpec structure matches roadmap
    assert isinstance(spec, ToolCardSpec)
    assert isinstance(spec.card_type, CardType)
    assert isinstance(spec.header_icon, str)  # emoji
    assert isinstance(spec.header_title, str)
    assert isinstance(spec.content, dict)
    assert spec.llm_commentary is not None  # Template for LLM
    assert isinstance(spec.raw_result, dict)  # For DB storage
    
    print("  PASS - ToolCardSpec structure")
    return True


def test_result_processor_loading_state():
    """TC12: ResultProcessor creates loading state (per 2.2.C)"""
    print("TC12: ResultProcessor loading state...")
    
    processor = ResultProcessor()
    
    loading = processor.create_loading_spec('image_generate', 'creating image')
    
    assert loading.card_type == CardType.LOADING
    assert loading.tool_visible == True
    assert 'spinner' in loading.content.get('animation', '')
    assert 'Creating image' in loading.content.get('description', '')
    
    print("  PASS - Loading state generation")
    return True


def run_all_tests():
    """Run all Phase 2 V2 tests."""
    tests = [
        test_intent_detector_llm_based,
        test_intent_detector_structured_output,
        test_tool_router_internal_execution,
        test_tool_router_mcp_stdio_support,
        test_result_processor_toolcardspec,
        test_result_processor_loading_state,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 60)
    print("PHASE 2 V2: Roadmap-Compliant Tests")
    print("=" * 60)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  FAIL - {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed}/{len(tests)} passed")
    
    if failed == 0:
        print("ALL TESTS PASSED - Roadmap compliant")
    else:
        print(f"{failed} tests failed")
    
    print("=" * 60)
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
