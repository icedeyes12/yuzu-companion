"""Unit tests for CLI and Web adapters."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))) + '/src')

from yuzu.interfaces.cli.adapter import CLIAdapter
from yuzu.interfaces.web.adapter import WebAdapter, WebResponse
from yuzu.infrastructure.config.container import FeatureFlags


class TestCLIAdapter:
    """Test CLI adapter."""

    @pytest.fixture
    def cli_adapter(self):
        return CLIAdapter()

    def test_adapter_creation(self, cli_adapter):
        """Test CLI adapter can be created."""
        assert cli_adapter is not None
        assert cli_adapter._container is not None

    def test_feature_flags_accessible(self, cli_adapter):
        """Test feature flags work."""
        # Should not raise any errors
        old_value = FeatureFlags.USE_NEW_CHAT_HANDLER
        FeatureFlags.USE_NEW_CHAT_HANDLER = True
        assert FeatureFlags.USE_NEW_CHAT_HANDLER is True
        FeatureFlags.USE_NEW_CHAT_HANDLER = old_value

    def test_get_status(self, cli_adapter):
        """Test getting status."""
        status = cli_adapter.get_status()
        assert isinstance(status, dict)
        assert "feature_flags" in status
        assert "container" in status


class TestWebAdapter:
    """Test Web adapter."""

    @pytest.fixture
    def web_adapter(self):
        return WebAdapter()

    def test_adapter_creation(self, web_adapter):
        """Test Web adapter can be created."""
        assert web_adapter is not None

    def test_web_response_creation(self):
        """Test WebResponse dataclass."""
        response = WebResponse(
            status="success",
            message="Test message",
            data={"test": "data"}
        )
        assert response.status == "success"
        assert response.message == "Test message"
        assert response.data == {"test": "data"}

        # Test to_dict
        dict_response = response.to_dict()
        assert dict_response["status"] == "success"
        assert dict_response["test"] == "data"

    def test_web_response_error(self):
        """Test WebResponse error format."""
        response = WebResponse(
            status="error",
            message="Something went wrong"
        )
        assert response.status == "error"
        dict_response = response.to_dict()
        assert "error" not in dict_response  # No 'error' key in merge, status is the indicator
        assert dict_response["status"] == "error"


class TestFeatureFlags:
    """Test feature flags."""

    def test_flags_exist(self):
        """Test feature flags exist."""
        # Just check they exist and are boolean
        assert hasattr(FeatureFlags, 'USE_NEW_DATABASE')
        assert hasattr(FeatureFlags, 'USE_NEW_PROVIDERS')
        assert hasattr(FeatureFlags, 'USE_NEW_TOOLS')
        assert hasattr(FeatureFlags, 'USE_NEW_CHAT_HANDLER')
        assert hasattr(FeatureFlags, 'DEBUG')
        
        # Check types
        assert isinstance(FeatureFlags.USE_NEW_CHAT_HANDLER, bool)
        assert isinstance(FeatureFlags.DEBUG, bool)