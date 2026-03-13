"""
Test ResultProcessor - Transform tool output to UI format

Tests:
1. Image result processing
2. Text result processing
3. List result processing
4. Code result processing
5. Error result processing
6. Tool card specification generation
"""

import unittest
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.orchestration.result_processor import (
    ResultProcessor, CardType, ToolCardSpec, get_result_processor
)
from tools.orchestration.tool_router import ToolResult, ToolType


class TestResultProcessor(unittest.TestCase):
    """Test cases for ResultProcessor"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.processor = ResultProcessor()
    
    # ============== Image result tests ==============
    
    def test_process_image_result(self):
        """Test processing image tool result"""
        tool_result = ToolResult(
            status="success",
            tool_name="image_generate",
            tool_type=ToolType.INTERNAL,
            raw_output={
                "image_path": "/tmp/generated_image.png",
                "prompt": "a beautiful sunset"
            },
            execution_time=3.5
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
        self.assertEqual(card_spec.card_type, CardType.IMAGE.value)
        self.assertIn("sunset", card_spec.content.get("prompt", "").lower())
    
    def test_process_image_result_with_url(self):
        """Test processing image result with URL"""
        tool_result = ToolResult(
            status="success",
            tool_name="image_generate",
            tool_type=ToolType.INTERNAL,
            raw_output={
                "image_url": "https://example.com/image.png",
                "prompt": "test"
            },
            execution_time=2.0
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertEqual(card_spec.card_type, CardType.IMAGE.value)
        self.assertEqual(card_spec.content["url"], "https://example.com/image.png")
    
    # ============== Text result tests ==============
    
    def test_process_text_result(self):
        """Test processing text tool result"""
        tool_result = ToolResult(
            status="success",
            tool_name="request",
            tool_type=ToolType.INTERNAL,
            raw_output={"text": "This is a fetched webpage content"},
            execution_time=1.2
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
        self.assertEqual(card_spec.card_type, CardType.TEXT.value)
        self.assertIn("fetched webpage", card_spec.content.get("text", ""))
    
    def test_process_text_result_from_string(self):
        """Test processing plain string result"""
        tool_result = ToolResult(
            status="success",
            tool_name="request",
            tool_type=ToolType.INTERNAL,
            raw_output="Simple string response",
            execution_time=0.5
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
        # Should handle string input gracefully
    
    # ============== List result tests ==============
    
    def test_process_list_result(self):
        """Test processing list/array result"""
        tool_result = ToolResult(
            status="success",
            tool_name="memory_search",
            tool_type=ToolType.INTERNAL,
            raw_output={
                "results": [
                    {"title": "Memory 1", "content": "Content 1"},
                    {"title": "Memory 2", "content": "Content 2"},
                    {"title": "Memory 3", "content": "Content 3"}
                ]
            },
            execution_time=0.8
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
        self.assertEqual(card_spec.card_type, CardType.LIST.value)
    
    def test_process_api_list_result(self):
        """Test processing API response as list"""
        tool_result = ToolResult(
            status="success",
            tool_name="request",
            tool_type=ToolType.INTERNAL,
            raw_output={
                "data": [1, 2, 3, 4, 5]
            },
            execution_time=0.3
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertEqual(card_spec.card_type, CardType.LIST.value)
    
    # ============== Code result tests ==============
    
    def test_process_code_result(self):
        """Test processing code output"""
        tool_result = ToolResult(
            status="success",
            tool_name="memory_sql",
            tool_type=ToolType.INTERNAL,
            raw_output={
                "query": "SELECT * FROM memories",
                "results": [{"id": 1, "content": "test"}]
            },
            execution_time=0.5
        }
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
        # SQL results might be code or list depending on format
    
    # ============== Error result tests ==============
    
    def test_process_error_result(self):
        """Test processing error result"""
        tool_result = ToolResult(
            status="error",
            tool_name="image_generate",
            tool_type=ToolType.INTERNAL,
            error="Failed to generate image: out of memory",
            execution_time=5.0
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
        self.assertEqual(card_spec.card_type, CardType.ERROR.value)
        self.assertIn("error", card_spec.content.get("message", "").lower())
    
    def test_process_error_with_details(self):
        """Test error with detailed information"""
        tool_result = ToolResult(
            status="error",
            tool_name="request",
            tool_type=ToolType.INTERNAL,
            error="HTTP 404: Not Found",
            execution_time=0.5
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertEqual(card_spec.card_type, CardType.ERROR.value)
    
    # ============== Tool card spec tests ==============
    
    def test_card_spec_header(self):
        """Test card specification header"""
        tool_result = ToolResult(
            status="success",
            tool_name="image_generate",
            tool_type=ToolType.INTERNAL,
            raw_output={"image_path": "/test.png"},
            execution_time=2.0
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec.header_title)
        self.assertIsNotNone(card_spec.header_icon)
        self.assertIn("image", card_spec.header_title.lower())
    
    def test_card_spec_llm_commentary(self):
        """Test LLM commentary generation"""
        tool_result = ToolResult(
            status="success",
            tool_name="image_generate",
            tool_type=ToolType.INTERNAL,
            raw_output={"image_path": "/test.png"},
            execution_time=2.0
        )
        
        commentary = self.processor.generate_commentary(tool_result)
        
        self.assertIsNotNone(commentary)
        self.assertIsInstance(commentary, str)
    
    # ============== Edge case tests ==============
    
    def test_process_empty_result(self):
        """Test processing empty result"""
        tool_result = ToolResult(
            status="success",
            tool_name="test",
            tool_type=ToolType.INTERNAL,
            raw_output={},
            execution_time=0.1
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
    
    def test_process_none_result(self):
        """Test processing None result"""
        tool_result = ToolResult(
            status="success",
            tool_name="test",
            tool_type=ToolType.INTERNAL,
            raw_output=None,
            execution_time=0.1
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
    
    def test_process_malformed_json(self):
        """Test processing malformed JSON result"""
        tool_result = ToolResult(
            status="success",
            tool_name="request",
            tool_type=ToolType.INTERNAL,
            raw_output="not valid json {",
            execution_time=0.5
        )
        
        # Should handle gracefully
        card_spec = self.processor.process(tool_result)
        self.assertIsNotNone(card_spec)
    
    def test_process_very_long_result(self):
        """Test processing very long result"""
        long_text = "x" * 10000
        tool_result = ToolResult(
            status="success",
            tool_name="request",
            tool_type=ToolType.INTERNAL,
            raw_output={"text": long_text},
            execution_time=1.0
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
        # Content should be handled
    
    # ============== Tool-specific tests ==============
    
    def test_process_weather_result(self):
        """Test processing weather tool result"""
        tool_result = ToolResult(
            status="success",
            tool_name="weather",
            tool_type=ToolType.INTERNAL,
            raw_output={
                "temperature": 25,
                "condition": "sunny",
                "location": "Jakarta"
            },
            execution_time=0.5
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertIsNotNone(card_spec)
    
    def test_process_web_search_result(self):
        """Test processing web search result"""
        tool_result = ToolResult(
            status="success",
            tool_name="web_search",
            tool_type=ToolType.INTERNAL,
            raw_output={
                "results": [
                    {"title": "Result 1", "url": "https://example.com/1"},
                    {"title": "Result 2", "url": "https://example.com/2"}
                ]
            },
            execution_time=1.0
        )
        
        card_spec = self.processor.process(tool_result)
        
        self.assertEqual(card_spec.card_type, CardType.LIST.value)


class TestToolCardSpec(unittest.TestCase):
    """Test ToolCardSpec dataclass"""
    
    def test_creation(self):
        """Test ToolCardSpec creation"""
        spec = ToolCardSpec(
            card_type=CardType.IMAGE.value,
            header_icon="🖼️",
            header_title="Image Generation",
            content={"url": "/test.png"},
            llm_commentary="Here you go!",
            raw_result={"image_path": "/test.png"}
        )
        
        self.assertEqual(spec.card_type, CardType.IMAGE.value)
        self.assertEqual(spec.header_icon, "🖼️")
        self.assertEqual(spec.content["url"], "/test.png")
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        spec = ToolCardSpec(
            card_type=CardType.TEXT.value,
            header_icon="📝",
            header_title="Text Tool",
            content={"text": "hello"},
            raw_result={}
        )
        
        d = spec.to_dict()
        
        self.assertEqual(d["card_type"], CardType.TEXT.value)
        self.assertEqual(d["header_icon"], "📝")


class TestCardType(unittest.TestCase):
    """Test CardType enum"""
    
    def test_enum_values(self):
        """Test CardType enum values"""
        self.assertEqual(CardType.IMAGE.value, "image")
        self.assertEqual(CardType.TEXT.value, "text")
        self.assertEqual(CardType.LIST.value, "list")
        self.assertEqual(CardType.CODE.value, "code")
        self.assertEqual(CardType.ERROR.value, "error")


class TestResultProcessorSingleton(unittest.TestCase):
    """Test ResultProcessor singleton"""
    
    def test_singleton(self):
        """Test singleton pattern"""
        processor1 = get_result_processor()
        processor2 = get_result_processor()
        
        self.assertIs(processor1, processor2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
