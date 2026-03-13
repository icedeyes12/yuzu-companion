#!/usr/bin/env python3
"""
Phase 2 Simulation Tests
Tests all orchestration cases without requiring full app.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration import IntentDetector, ToolIntent, ToolRouter, ResultProcessor
from tools.orchestration.result_processor import DisplayType


def test_intent_detection():
    """Test cases TC1-TC7: Intent detection"""
    print("\n" + "="*60)
    print("TEST SUITE: Intent Detection (TC1-TC7)")
    print("="*60)
    
    detector = IntentDetector()
    
    test_cases = [
        ("TC1", "Send me your picture", ToolIntent.IMAGE_GENERATE, 0.6),
        ("TC2", "/imagine a cat", ToolIntent.IMAGE_GENERATE, 1.0),
        ("TC3", "What's the weather?", ToolIntent.WEATHER, 0.6),
        ("TC4", "Search for Python docs", ToolIntent.WEB_SEARCH, 0.6),
        ("TC5", "What did we talk about yesterday?", ToolIntent.MEMORY_QUERY, 0.6),
        ("TC6", "Hello, how are you?", ToolIntent.NONE, 0.9),
        ("TC7", "Draw me something", ToolIntent.IMAGE_GENERATE, 0.5),
    ]
    
    passed = 0
    failed = 0
    
    for tc_id, input_text, expected_intent, min_confidence in test_cases:
        result = detector.detect(input_text)
        
        intent_match = result.intent == expected_intent
        confidence_ok = result.confidence >= min_confidence
        
        status = "PASS" if intent_match and confidence_ok else "FAIL"
        if status == "PASS":
            passed += 1
        else:
            failed += 1
        
        print(f"\n{tc_id}: {status}")
        print(f"  Input: '{input_text}'")
        print(f"  Expected: {expected_intent.value} (confidence >= {min_confidence})")
        print(f"  Got: {result.intent.value} (confidence: {result.confidence:.2f})")
        if not intent_match:
            print(f"  ❌ Intent mismatch!")
        if not confidence_ok:
            print(f"  ❌ Confidence too low!")
        if result.tool_name:
            print(f"  Tool: {result.tool_name}")
        if result.suggested_params:
            print(f"  Params: {result.suggested_params}")
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    return failed == 0


def test_result_processing():
    """Test cases TC11-TC15: Result processing"""
    print("\n" + "="*60)
    print("TEST SUITE: Result Processing (TC11-TC15)")
    print("="*60)
    
    processor = ResultProcessor()
    
    test_cases = [
        ("TC11", "image_generate", "static/generated_images/test.png", "success"),
        ("TC12", "weather", {
            'location': 'Jakarta',
            'temperature': 28,
            'condition': 'Partly cloudy',
            'humidity': 75
        }, "success"),
        ("TC13", "web_search", [
            {'title': 'Python Docs', 'snippet': 'Official documentation', 'url': 'https://docs.python.org'},
            {'title': 'Learn Python', 'snippet': 'Tutorial site', 'url': 'https://learnpython.org'},
        ], "success"),
        ("TC14", "http_request", {'status': 200, 'data': {'key': 'value'}}, "success"),
        ("TC15", "image_generate", Exception("GPU out of memory"), "error"),
    ]
    
    passed = 0
    failed = 0
    
    for tc_id, tool_name, result, status in test_cases:
        try:
            processed = processor.process(tool_name, result, status)
            
            # Check expected display type
            expected_types = {
                'image_generate': DisplayType.IMAGE,
                'weather': DisplayType.WEATHER_CARD,
                'web_search': DisplayType.SEARCH_RESULTS,
                'http_request': DisplayType.JSON,
            }
            
            expected_type = expected_types.get(tool_name, DisplayType.TEXT)
            if status == 'error':
                expected_type = DisplayType.ERROR
            
            type_match = processed.display_type == expected_type
            
            # For image, check path normalization
            if tool_name == 'image_generate' and status == 'success':
                has_url = 'image_url' in processed.content
                type_match = type_match and has_url
            
            status_str = "PASS" if type_match else "FAIL"
            if status_str == "PASS":
                passed += 1
            else:
                failed += 1
            
            print(f"\n{tc_id}: {status_str}")
            print(f"  Tool: {tool_name}")
            print(f"  Status: {status}")
            print(f"  Display Type: {processed.display_type.value}")
            print(f"  Tool Visible: {processed.tool_visible}")
            print(f"  Inline: {processed.inline}")
            if processed.narrative:
                print(f"  Narrative Prompt: {processed.narrative[:60]}...")
            
            if not type_match:
                print(f"  ❌ Expected type: {expected_type.value}")
            
        except Exception as e:
            failed += 1
            print(f"\n{tc_id}: FAIL (exception)")
            print(f"  Error: {e}")
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'='*60}")
    
    return failed == 0


def test_loading_states():
    """Test loading state generation"""
    print("\n" + "="*60)
    print("TEST SUITE: Loading States")
    print("="*60)
    
    processor = ResultProcessor()
    
    tools = ['image_generate', 'weather', 'web_search', 'memory_search']
    
    for tool in tools:
        loading = processor.create_loading_state(tool, f"using {tool}")
        print(f"\n{tool}:")
        print(f"  Display Type: {loading.display_type.value}")
        print(f"  Icon: {loading.content.get('icon')}")
        print(f"  Description: {loading.content.get('description')}")
        print(f"  Tool Visible: {loading.tool_visible}")
    
    print(f"\n{'='*60}")
    print("Results: All loading states generated")
    print(f"{'='*60}")
    
    return True


def test_error_formatting():
    """Test error result formatting"""
    print("\n" + "="*60)
    print("TEST SUITE: Error Formatting")
    print("="*60)
    
    processor = ResultProcessor()
    
    errors = [
        ("image_generate", "GPU out of memory"),
        ("weather", "API key invalid"),
        ("web_search", "Connection timeout"),
        ("unknown_tool", "Something went wrong"),
    ]
    
    for tool, error_msg in errors:
        result = processor._create_error_result(tool, error_msg)
        print(f"\n{tool}:")
        print(f"  Friendly: {result.content.get('friendly_message')}")
        print(f"  Technical: {result.content.get('technical_message')}")
        print(f"  Retryable: {result.content.get('retryable')}")
        print(f"  Narrative: {result.narrative}")
    
    print(f"\n{'='*60}")
    print("Results: All error formats generated")
    print(f"{'='*60}")
    
    return True


def run_all_simulations():
    """Run all simulation tests"""
    print("\n" + "#"*60)
    print("# PHASE 2 ORCHESTRATION SIMULATION")
    print("#"*60)
    
    results = []
    
    results.append(("Intent Detection", test_intent_detection()))
    results.append(("Result Processing", test_result_processing()))
    results.append(("Loading States", test_loading_states()))
    results.append(("Error Formatting", test_error_formatting()))
    
    print("\n" + "#"*60)
    print("# FINAL RESULTS")
    print("#"*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "#"*60)
    if all_passed:
        print("# ALL SIMULATIONS PASSED")
        print("# Ready for Phase 3: UI Component System")
    else:
        print("# SOME SIMULATIONS FAILED")
        print("# Review issues before Phase 3")
    print("#"*60)
    
    return all_passed


if __name__ == "__main__":
    success = run_all_simulations()
    sys.exit(0 if success else 1)
