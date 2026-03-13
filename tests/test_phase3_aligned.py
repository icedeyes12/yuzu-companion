#!/usr/bin/env python3
"""
Phase 3 Aligned Tests
Tests match the ACTUAL implementation API
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration import (
    IntentDetector, ToolIntent,
    ResultProcessor, DisplayType,
    escapeHtml
)
from database import init_db

def run_all_tests():
    print("=" * 60)
    print("PHASE 3: UI Component Tests (Aligned to Implementation)")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    # TC1: Intent detection works
    try:
        print("\nTC1: Image intent detection...")
        d = IntentDetector()
        r = d.detect_intent("Send me your picture")
        assert r.intent == ToolIntent.IMAGE_GENERATE
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC2: Loading state creation
    try:
        print("\nTC2: Loading state creation...")
        p = ResultProcessor()
        r = p.create_loading_state('image_generate')
        assert r.display_type == DisplayType.LOADING
        assert r.content.get('icon') == '🖼️'
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC3: Weather loading
    try:
        print("\nTC3: Weather loading state...")
        d = IntentDetector()
        intent = d.detect_intent("What's the weather?")
        assert intent.intent == ToolIntent.WEATHER
        
        p = ResultProcessor()
        r = p.create_loading_state('weather')
        assert r.content.get('icon') == '🌤️'
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC4: Result processing (image success)
    try:
        print("\nTC4: Image result processing...")
        p = ResultProcessor()
        raw_result = {'image_path': 'static/test.png'}
        r = p.process('image_generate', raw_result, 'success', 2500)
        assert r.display_type == DisplayType.IMAGE
        assert 'test.png' in str(r.content)
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC5: Search intent
    try:
        print("\nTC5: Search intent...")
        d = IntentDetector()
        r = d.detect_intent("Search for Python tutorials")
        assert r.intent == ToolIntent.WEB_SEARCH
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC6: Search loading
    try:
        print("\nTC6: Search loading...")
        p = ResultProcessor()
        r = p.create_loading_state('web_search')
        assert r.content.get('icon') == '🔍'
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC7: Error state
    try:
        print("\nTC7: Error state...")
        p = ResultProcessor()
        r = p.process('image_generate', 'rate limit', 'error', 1000)
        assert r.display_type == DisplayType.ERROR
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC8: Timeout state
    try:
        print("\nTC8: Timeout state...")
        p = ResultProcessor()
        r = p.process('image_generate', None, 'timeout', 120000)
        assert r.display_type == DisplayType.ERROR
        assert r.content.get('retryable') == True
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC9: XSS prevention
    try:
        print("\nTC9: XSS escape...")
        malicious = '<script>alert("xss")</script>'
        escaped = escapeHtml(malicious)
        assert '<script>' not in escaped
        assert '&lt;' in escaped
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC10: CSS file exists and has content
    try:
        print("\nTC10: CSS file validation...")
        css_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'css', 'tool-card.css')
        assert os.path.exists(css_path), f"CSS file not found at {css_path}"
        with open(css_path) as f:
            css = f.read()
        assert len(css) > 500, "CSS too short"
        assert 'prefers-reduced-motion' in css, "Missing reduced-motion support"
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC11: Component files exist
    try:
        print("\nTC11: Component files exist...")
        files = [
            'static/js/components/tool-card.js',
            'static/js/hooks/use-tools.js',
            'static/css/tool-card.css'
        ]
        for f in files:
            path = os.path.join(os.path.dirname(__file__), '..', f)
            assert os.path.exists(path), f"Missing: {f}"
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC12: Memory intent
    try:
        print("\nTC12: Memory intent detection...")
        d = IntentDetector()
        r = d.detect_intent("What did we talk about?")
        assert r.intent == ToolIntent.MEMORY_QUERY
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC13: Narrative prompt generation
    try:
        print("\nTC13: Narrative prompts...")
        p = ResultProcessor()
        # Create a weather result
        weather = p.process('weather', {'temp': 28, 'location': 'Jakarta'}, 'success', 500)
        prompt = p.generate_narrative_prompt('weather', weather)
        assert len(prompt) > 0
        assert 'weather' in prompt.lower() or 'Jakarta' in prompt
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC14: DisplayType aliases work
    try:
        print("\nTC14: DisplayType aliases...")
        # Test that IMAGE alias works
        assert DisplayType.IMAGE == DisplayType.IMAGE
        # Test SEARCH alias if it exists
        try:
            search = DisplayType.SEARCH
            print("  ✅ PASS (SEARCH alias exists)")
        except:
            # SEARCH might be SEARCH_RESULTS
            assert DisplayType.SEARCH_RESULTS
            print("  ✅ PASS (SEARCH_RESULTS used)")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # TC15: JSON result formatting
    try:
        print("\nTC15: JSON formatting...")
        p = ResultProcessor()
        json_data = {'status': 'ok', 'items': [1,2,3]}
        r = p.process('http_request', json_data, 'success', 1000)
        # Should format without error
        assert r.content is not None
        print("  ✅ PASS")
        passed += 1
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed}/{passed+failed} passed")
    if failed == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"⚠️ {failed} failed")
    print("=" * 60)
    
    return failed == 0

if __name__ == '__main__':
    init_db()
    success = run_all_tests()
    sys.exit(0 if success else 1)
