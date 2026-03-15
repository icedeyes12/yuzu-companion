"""Shadow Mode Testing - Compare old vs new code paths.

This module implements shadow mode testing where both the old
and new implementations run, but only the old result is returned
to the user. Differences are logged for analysis.
"""

import time
import json
import hashlib
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import threading


class ComparisonResult(Enum):
    """Result of comparing old vs new implementation."""
    IDENTICAL = "identical"           # Outputs match exactly
    SEMANTIC_EQUIVALENT = "semantic"  # Different format, same meaning
    DIFFERENT = "different"           # Meaningful differences
    OLD_ERROR = "old_error"           # Old implementation failed
    NEW_ERROR = "new_error"           # New implementation failed
    BOTH_ERROR = "both_error"         # Both implementations failed


@dataclass
class ShadowRun:
    """Record of a shadow mode execution."""
    run_id: str
    operation: str                      # e.g., "handle_user_message"
    input_hash: str                     # Hash of input for privacy
    
    # Timing
    old_duration_ms: float
    new_duration_ms: float
    overhead_ms: float                  # Time to run both
    
    # Results
    old_output: Optional[str] = None
    new_output: Optional[str] = None
    old_error: Optional[str] = None
    new_error: Optional[str] = None
    
    # Comparison
    comparison: ComparisonResult = ComparisonResult.IDENTICAL
    diff_details: Optional[str] = None
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    feature_flags: Dict[str, bool] = field(default_factory=dict)


class ShadowModeComparator:
    """Compare old vs new implementations in shadow mode.
    
    Usage:
        comparator = ShadowModeComparator()
        
        # Wrap a function
        result = comparator.compare(
            operation="chat",
            old_func=lambda: old_handle_message(msg),
            new_func=lambda: new_handle_message(msg),
            input_data=msg
        )
    """
    
    def __init__(self, log_path: str = "shadow_mode.log"):
        self._log_path = log_path
        self._runs: List[ShadowRun] = []
        self._lock = threading.Lock()
        self._enabled = True
        self._sample_rate = 1.0  # Log 100% of calls during testing
    
    def compare(
        self,
        operation: str,
        old_func: Callable[[], Any],
        new_func: Callable[[], Any],
        input_data: Any,
        return_old: bool = True
    ) -> Any:
        """Run both implementations and compare results.
        
        Args:
            operation: Name of the operation being tested
            old_func: Old implementation (returns result to user)
            new_func: New implementation (runs in shadow)
            input_data: Input for hashing (not stored raw)
            return_old: If True, return old result; if False, return new
        
        Returns:
            Result from old_func (by default) or new_func
        """
        if not self._enabled or self._should_skip():
            # Shadow mode disabled, just run old
            return old_func()
        
        # Generate run ID
        run_id = self._generate_run_id()
        
        # Hash input for privacy
        input_hash = self._hash_input(input_data)
        
        # Run old implementation
        old_start = time.time()
        try:
            old_result = old_func()
            old_output = str(old_result) if old_result is not None else None
            old_error = None
        except Exception as e:
            old_result = None
            old_output = None
            old_error = str(e)
        old_duration = (time.time() - old_start) * 1000
        
        # Run new implementation (in shadow)
        new_start = time.time()
        try:
            new_result = new_func()
            new_output = str(new_result) if new_result is not None else None
            new_error = None
        except Exception as e:
            new_result = None
            new_output = None
            new_error = str(e)
        new_duration = (time.time() - new_start) * 1000
        
        overhead = (time.time() - old_start) * 1000
        
        # Compare results
        comparison, diff = self._compare_outputs(
            old_output, new_output, old_error, new_error
        )
        
        # Create run record
        run = ShadowRun(
            run_id=run_id,
            operation=operation,
            input_hash=input_hash,
            old_duration_ms=old_duration,
            new_duration_ms=new_duration,
            overhead_ms=overhead,
            old_output=old_output[:1000] if old_output else None,  # Truncate
            new_output=new_output[:1000] if new_output else None,
            old_error=old_error,
            new_error=new_error,
            comparison=comparison,
            diff_details=diff,
            feature_flags=self._get_feature_flags(),
        )
        
        # Log and store
        self._log_run(run)
        with self._lock:
            self._runs.append(run)
        
        # Return appropriate result
        return old_result if return_old else new_result
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID."""
        return hashlib.sha256(
            f"{time.time()}-{threading.current_thread().ident}".encode()
        ).hexdigest()[:16]
    
    def _hash_input(self, input_data: Any) -> str:
        """Hash input data for privacy."""
        return hashlib.sha256(str(input_data).encode()).hexdigest()[:16]
    
    def _should_skip(self) -> bool:
        """Determine if this call should be skipped based on sample rate."""
        import random
        return random.random() > self._sample_rate
    
    def _compare_outputs(
        self,
        old_output: Optional[str],
        new_output: Optional[str],
        old_error: Optional[str],
        new_error: Optional[str]
    ) -> tuple:
        """Compare outputs and return result + diff."""
        # Handle errors first
        if old_error and new_error:
            return ComparisonResult.BOTH_ERROR, f"Old: {old_error[:100]} | New: {new_error[:100]}"
        if old_error:
            return ComparisonResult.OLD_ERROR, old_error[:100]
        if new_error:
            return ComparisonResult.NEW_ERROR, new_error[:100]
        
        # Compare outputs
        if old_output == new_output:
            return ComparisonResult.IDENTICAL, None
        
        # Check for semantic equivalence (e.g., whitespace differences)
        old_normalized = old_output.strip().lower() if old_output else ""
        new_normalized = new_output.strip().lower() if new_output else ""
        
        if old_normalized == new_normalized:
            return ComparisonResult.SEMANTIC_EQUIVALENT, "Whitespace/case differences only"
        
        # Calculate diff
        diff = self._calculate_diff(old_output, new_output)
        return ComparisonResult.DIFFERENT, diff[:500]
    
    def _calculate_diff(self, old: str, new: str) -> str:
        """Calculate simple diff between strings."""
        import difflib
        old_lines = old.splitlines() if old else []
        new_lines = new.splitlines() if new else []
        
        diff = list(difflib.unified_diff(
            old_lines[:20], new_lines[:20],  # Limit lines
            lineterm="",
            n=2
        ))
        
        return "\n".join(diff)
    
    def _get_feature_flags(self) -> Dict[str, bool]:
        """Get current feature flag states."""
        from ...infrastructure.config.container import FeatureFlags
        return {
            "USE_NEW_CHAT_HANDLER": FeatureFlags.USE_NEW_CHAT_HANDLER,
            "USE_NEW_DATABASE": FeatureFlags.USE_NEW_DATABASE,
            "USE_NEW_PROVIDERS": FeatureFlags.USE_NEW_PROVIDERS,
            "USE_NEW_TOOLS": FeatureFlags.USE_NEW_TOOLS,
        }
    
    def _log_run(self, run: ShadowRun) -> None:
        """Log run to file."""
        try:
            with open(self._log_path, "a") as f:
                f.write(json.dumps(asdict(run), default=str) + "\n")
        except Exception as e:
            print(f"[ShadowMode] Failed to log: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics on shadow runs."""
        with self._lock:
            runs = self._runs.copy()
        
        if not runs:
            return {"total": 0}
        
        total = len(runs)
        by_result = {}
        for run in runs:
            by_result[run.comparison.value] = by_result.get(run.comparison.value, 0) + 1
        
        avg_old_time = sum(r.old_duration_ms for r in runs) / total
        avg_new_time = sum(r.new_duration_ms for r in runs) / total
        avg_overhead = sum(r.overhead_ms for r in runs) / total
        
        return {
            "total": total,
            "by_result": by_result,
            "avg_old_time_ms": round(avg_old_time, 2),
            "avg_new_time_ms": round(avg_new_time, 2),
            "avg_overhead_ms": round(avg_overhead, 2),
            "performance_change_pct": round(
                ((avg_new_time - avg_old_time) / avg_old_time * 100) if avg_old_time > 0 else 0,
                2
            ),
        }
    
    def generate_report(self) -> str:
        """Generate human-readable report."""
        stats = self.get_stats()
        
        report = f"""
Shadow Mode Testing Report
==========================
Total Runs: {stats['total']}

Results Breakdown:
"""
        for result, count in stats.get("by_result", {}).items():
            pct = (count / stats['total'] * 100) if stats['total'] > 0 else 0
            report += f"  {result}: {count} ({pct:.1f}%)\n"
        
        report += f"""
Performance:
  Old avg: {stats.get('avg_old_time_ms', 0)}ms
  New avg: {stats.get('avg_new_time_ms', 0)}ms
  Overhead: {stats.get('avg_overhead_ms', 0)}ms
  Change: {stats.get('performance_change_pct', 0)}%
"""
        
        return report
    
    def enable(self) -> None:
        """Enable shadow mode."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable shadow mode."""
        self._enabled = False
    
    def set_sample_rate(self, rate: float) -> None:
        """Set sampling rate (0.0 to 1.0)."""
        self._sample_rate = max(0.0, min(1.0, rate))


# Singleton instance
_comparator: Optional[ShadowModeComparator] = None

def get_shadow_comparator() -> ShadowModeComparator:
    """Get global shadow mode comparator."""
    global _comparator
    if _comparator is None:
        _comparator = ShadowModeComparator()
    return _comparator


def shadow_compare(operation: str):
    """Decorator for shadow mode comparison.
    
    Usage:
        @shadow_compare("handle_message")
        def my_function(message):
            # This becomes the NEW implementation
            pass
    
    The OLD implementation should be defined separately and
    passed to the comparator's compare method.
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            comparator = get_shadow_comparator()
            
            # The decorated function is the NEW implementation
            new_func = lambda: func(*args, **kwargs)
            
            # OLD implementation must be defined in kwargs or use legacy
            old_func = kwargs.pop('_old_impl', None)
            if old_func is None:
                # Default: just run new without comparison
                return func(*args, **kwargs)
            
            return comparator.compare(
                operation=operation,
                old_func=lambda: old_func(*args, **kwargs),
                new_func=new_func,
                input_data=str(args) + str(kwargs),
            )
        return wrapper
    return decorator
