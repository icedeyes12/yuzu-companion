"""
Test IntentDetector - Tool intent detection

Tests:
1. Keyword-based detection (no LLM)
2. LLM-based detection
3. Confidence threshold handling
4. Tool parameter extraction
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration.intent_detector import IntentDetector, ToolIntent


class MockAIManager:
    """Mock AI manager for testing"""
    
    def __init__(self, should_fail=False, response=None):
        self.should_fail = should_fail
        self.response = response or {
            "needs_tool": True,
            "tool_name": "image_generate",
            "params": {"prompt": "a beautiful sunset"},
            "confidence": 0.9,
            "reasoning": "User explicitly requested image generation"
        }
        self.call_count = 0
    
    def chat(self, messages, **kwargs):
        self.call_count += 1
        if self.should_fail:
            raise Exception("Mock AI failure")
        
        import json
        return json.dumps(self.response)


class TestIntentDetector(unittest.TestCase):
    """Test cases for IntentDetector"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_ai = MockAIManager()
        self.detector = IntentDetector(ai_manager=None)  # Use keyword-based mode
    
    # ============== Keyword-based detection tests ==============
    
    def test_keyword_image_generation(self):
        """Test keyword detection for image generation"""
        test_cases = [
            ("generate an image of a cat", "image_generate", {"prompt": "a cat"}),
            ("/imagine a beautiful sunset", "image_generate", {"prompt": "a beautiful sunset"}),
            ("create an image", "image_generate", {"prompt": "create an image"}),
            ("draw a picture of mountains", "image_generate", {"prompt": "mountains"}),
            ("buatkan gambar mobil", "image_generate", {"prompt": "mobil"}),  # Indonesian
        ]
        
        for user_message, expected_tool, expected_params in test_cases:
            result = self.detector.detect(user_message)
            self.assertIsNotNone(result, f"Failed to detect tool for: {user_message}")
            self.assertEqual(result.tool_name, expected_tool, 
                           f"Wrong tool for: {user_message}")
    
    def test_keyword_http_request(self):
        """Test keyword detection for HTTP requests"""
        test_cases = [
            ("fetch https://example.com", "request", {"url": "https://example.com"}),
            ("/request https://api.example.com/data", "request", {"url": "https://api.example.com/data"}),
            ("get the page from https://google.com", "request", {"url": "https://google.com"}),
        ]
        
        for user_message, expected_tool, expected_params in test_cases:
            result = self.detector.detect(user_message)
            self.assertIsNotNone(result, f"Failed to detect for: {user_message}")
            self.assertEqual(result.tool_name, expected_tool)
    
    def test_keyword_memory_search(self):
        """Test keyword detection for memory search"""
        test_cases = [
            ("search my memory about vacation", "memory_search", {"query": "vacation"}),
            ("what do you remember about our chat", "memory_search", {"query": "our chat"}),
            ("/memory_search previous conversation", "memory_search", {"query": "previous conversation"}),
        ]
        
        for user_message, expected_tool, _ in test_cases:
            result = self.detector.detect(user_message)
            self.assertIsNotNone(result)
            self.assertEqual(result.tool_name, expected_tool)
    
    def test_keyword_memory_sql(self):
        """Test keyword detection for memory SQL"""
        test_cases = [
            ("query my memories", "memory_sql", {"query": "query my memories"}),
            ("/memory_sql SELECT * FROM memories", "memory_sql", {"query": "SELECT * FROM memories"}),
            ("show all the facts you know about me", "memory_sql", {"query": "facts about me"}),
        ]
        
        for user_message, expected_tool, _ in test_cases:
            result = self.detector.detect(user_message)
            self.assertIsNotNone(result)
            self.assertEqual(result.tool_name, expected_tool)
    
    def test_no_tool_needed(self):
        """Test detection when no tool is needed"""
        test_cases = [
            ("hello, how are you?"),
            ("what is the weather like today?"),
            ("tell me a joke"),
            ("thanks for the help"),
            ("bye see you later"),
        ]
        
        for user_message in test_cases:
            result = self.detector.detect(user_message)
            # These should not trigger tools (or return None/low confidence)
            if result:
                self.assertLess(result.confidence, 0.7, 
                               f"False positive for: {user_message}")
    
    # ============== Parameter extraction tests ==============
    
    def test_parameter_extraction_image(self):
        """Test parameter extraction for image generation"""
        result = self.detector.detect("generate an image of a cute cat playing in the park")
        self.assertIsNotNone(result)
        self.assertIn("cat", result.params.get("prompt", "").lower())
    
    def test_parameter_extraction_url(self):
        """Test parameter extraction for URL requests"""
        result = self.detector.detect("fetch https://api.example.com/users/123")
        self.assertIsNotNone(result)
        self.assertEqual(result.params.get("url"), "https://api.example.com/users/123")
    
    # ============== Confidence tests ==============
    
    def test_confidence_levels(self):
        """Test confidence scoring"""
        # High confidence: explicit commands
        result = self.detector.detect("/imagine a sunset")
        self.assertIsNotNone(result)
        self.assertGreater(result.confidence, 0.5)
        
        # Lower confidence: implied requests
        result = self.detector.detect("can you make an image?")
        # May or may not detect, depending on implementation
    
    # ============== LLM-based detection tests ==============
    
    def test_llm_detection_success(self):
        """Test LLM-based detection with mock AI"""
        detector = IntentDetector(ai_manager=self.mock_ai)
        result = detector.detect("create a beautiful landscape painting")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.tool_name, "image_generate")
        self.assertEqual(self.mock_ai.call_count, 1)
    
    def test_llm_detection_fallback_on_error(self):
        """Test fallback to keyword detection on LLM failure"""
        failing_ai = MockAIManager(should_fail=True)
        detector = IntentDetector(ai_manager=failing_ai)
        
        # Should fallback to keyword detection
        result = detector.detect("/imagine a cat")
        self.assertIsNotNone(result)
        self.assertEqual(result.tool_name, "image_generate")
    
    # ============== Edge case tests ==============
    
    def test_empty_message(self):
        """Test handling of empty message"""
        result = self.detector.detect("")
        self.assertIsNone(result)
    
    def test_very_long_message(self):
        """Test handling of very long message"""
        long_message = "generate an image of " + "a " * 1000
        result = self.detector.detect(long_message)
        self.assertIsNotNone(result)
    
    def test_special_characters(self):
        """Test handling of special characters"""
        result = self.detector.detect("/imagine 🚀🚀🚀")
        self.assertIsNotNone(result)
    
    def test_multilingual(self):
        """Test multilingual detection"""
        test_cases = [
            ("buatkan gambar rumah", "image_generate"),  # Indonesian
            ("créer une image", "image_generate"),  # French
            ("Bild erstellen", "image_generate"),  # German
        ]
        
        for message, expected_tool in test_cases:
            result = self.detector.detect(message)
            # May or may not detect depending on keyword coverage


class TestToolIntent(unittest.TestCase):
    """Test ToolIntent dataclass"""
    
    def test_creation(self):
        """Test ToolIntent creation"""
        intent = ToolIntent(
            tool_name="image_generate",
            params={"prompt": "test"},
            confidence=0.9,
            reasoning="test reason"
        )
        
        self.assertEqual(intent.tool_name, "image_generate")
        self.assertEqual(intent.params, {"prompt": "test"})
        self.assertEqual(intent.confidence, 0.9)
        self.assertEqual(intent.reasoning, "test reason")
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        intent = ToolIntent(
            tool_name="request",
            params={"url": "https://example.com"},
            confidence=0.85,
            reasoning="URL detected"
        )
        
        result = intent.to_dict()
        
        self.assertEqual(result["tool_name"], "request")
        self.assertEqual(result["params"]["url"], "https://example.com")
        self.assertEqual(result["confidence"], 0.85)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
