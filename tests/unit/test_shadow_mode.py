"""Tests for shadow mode testing infrastructure."""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))) + '/src')

from yuzu.infrastructure.monitoring.shadow_mode import (
    ShadowModeComparator,
    ComparisonResult,
    get_shadow_comparator,
)


class TestShadowModeComparator:
    """Test shadow mode comparison."""

    def test_comparator_creation(self):
        """Test comparator can be created."""
        comparator = ShadowModeComparator()
        assert comparator is not None
        assert comparator._enabled is True

    def test_compare_identical_outputs(self):
        """Test identical outputs detected."""
        comparator = ShadowModeComparator()
        result, diff = comparator._compare_outputs(
            "Hello World", "Hello World",
            None, None
        )
        assert result == ComparisonResult.IDENTICAL
        assert diff is None

    def test_compare_different_outputs(self):
        """Test different outputs detected."""
        comparator = ShadowModeComparator()
        result, diff = comparator._compare_outputs(
            "Old output", "New output",
            None, None
        )
        assert result == ComparisonResult.DIFFERENT
        assert diff is not None

    def test_compare_errors(self):
        """Test error detection."""
        comparator = ShadowModeComparator()
        result, diff = comparator._compare_outputs(
            None, None,
            "Old error", "New error"
        )
        assert result == ComparisonResult.BOTH_ERROR

    def test_hash_input_deterministic(self):
        """Test input hashing is deterministic."""
        comparator = ShadowModeComparator()
        h1 = comparator._hash_input("test message")
        h2 = comparator._hash_input("test message")
        assert h1 == h2

    def test_get_stats_empty(self):
        """Test stats with no runs."""
        comparator = ShadowModeComparator()
        stats = comparator.get_stats()
        assert stats["total"] == 0


class TestShadowModeSingleton:
    """Test singleton pattern."""

    def test_get_shadow_comparator(self):
        """Test singleton returns same instance."""
        c1 = get_shadow_comparator()
        c2 = get_shadow_comparator()
        assert c1 is c2


class TestComparisonResult:
    """Test comparison result enum."""

    def test_result_values(self):
        """Test enum values."""
        assert ComparisonResult.IDENTICAL.value == "identical"
        assert ComparisonResult.DIFFERENT.value == "different"
