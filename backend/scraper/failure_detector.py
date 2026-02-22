"""
Failure Detection Module
Detects when selectors fail and triggers self-healing process.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any, Dict
from datetime import datetime
from loguru import logger


class FailureType(Enum):
    """Types of selector failures that can occur."""
    ELEMENT_NOT_FOUND = "element_not_found"
    STALE_ELEMENT = "stale_element"
    TIMEOUT = "timeout"
    EMPTY_RESULT = "empty_result"
    WRONG_CONTENT = "wrong_content"
    MULTIPLE_MATCHES = "multiple_matches"


@dataclass
class FailureReport:
    """Detailed report of a selector failure."""
    failure_type: FailureType
    selector: str
    url: str
    timestamp: datetime
    expected_content: Optional[str] = None
    actual_content: Optional[str] = None
    error_message: Optional[str] = None
    dom_snapshot_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_type": self.failure_type.value,
            "selector": self.selector,
            "url": self.url,
            "timestamp": self.timestamp.isoformat(),
            "expected_content": self.expected_content,
            "actual_content": self.actual_content,
            "error_message": self.error_message,
            "dom_snapshot_path": self.dom_snapshot_path
        }


class FailureDetector:
    """
    Detects selector failures using multiple strategies:
    1. Element presence check
    2. Content validation
    3. Type checking
    4. Count validation
    """

    def __init__(self):
        self.failure_history: list[FailureReport] = []

    def detect_failure(
        self,
        element: Optional[Any],
        selector: str,
        url: str,
        expected_content: Optional[str] = None,
        expected_count: Optional[int] = None
    ) -> Optional[FailureReport]:
        """
        Analyze an element retrieval attempt and detect failures.
        
        Args:
            element: The retrieved element (or None if not found)
            selector: The selector used
            url: Current page URL
            expected_content: Optional content to validate against
            expected_count: Optional expected number of matches
            
        Returns:
            FailureReport if failure detected, None if successful
        """
        timestamp = datetime.utcnow()
        
        # Check 1: Element not found
        if element is None:
            report = FailureReport(
                failure_type=FailureType.ELEMENT_NOT_FOUND,
                selector=selector,
                url=url,
                timestamp=timestamp,
                error_message="No element found matching selector"
            )
            self._log_failure(report)
            return report
        
        # Check 2: Empty content
        if isinstance(element, list):
            if len(element) == 0:
                report = FailureReport(
                    failure_type=FailureType.EMPTY_RESULT,
                    selector=selector,
                    url=url,
                    timestamp=timestamp,
                    error_message="Selector returned empty list"
                )
                self._log_failure(report)
                return report
            
            # Check 3: Multiple matches when single expected
            if expected_count is not None and len(element) != expected_count:
                report = FailureReport(
                    failure_type=FailureType.MULTIPLE_MATCHES,
                    selector=selector,
                    url=url,
                    timestamp=timestamp,
                    expected_content=f"Expected {expected_count} elements",
                    actual_content=f"Found {len(element)} elements",
                    error_message="Element count mismatch"
                )
                self._log_failure(report)
                return report
        
        # Check 4: Content validation
        if expected_content:
            actual_content = self._extract_content(element)
            if expected_content.lower() not in actual_content.lower():
                report = FailureReport(
                    failure_type=FailureType.WRONG_CONTENT,
                    selector=selector,
                    url=url,
                    timestamp=timestamp,
                    expected_content=expected_content,
                    actual_content=actual_content[:200],
                    error_message="Content does not match expected value"
                )
                self._log_failure(report)
                return report
        
        # No failure detected
        logger.debug(f"Selector '{selector}' validated successfully")
        return None

    def detect_stale_element(
        self,
        selector: str,
        url: str,
        error: Exception
    ) -> FailureReport:
        """
        Create failure report for stale element exceptions.
        
        Args:
            selector: The selector that caused the error
            url: Current page URL
            error: The exception that was raised
            
        Returns:
            FailureReport for stale element
        """
        report = FailureReport(
            failure_type=FailureType.STALE_ELEMENT,
            selector=selector,
            url=url,
            timestamp=datetime.utcnow(),
            error_message=str(error)
        )
        self._log_failure(report)
        return report

    def detect_timeout(
        self,
        selector: str,
        url: str,
        timeout_seconds: int
    ) -> FailureReport:
        """
        Create failure report for timeout errors.
        
        Args:
            selector: The selector that timed out
            url: Current page URL
            timeout_seconds: How long was waited
            
        Returns:
            FailureReport for timeout
        """
        report = FailureReport(
            failure_type=FailureType.TIMEOUT,
            selector=selector,
            url=url,
            timestamp=datetime.utcnow(),
            error_message=f"Selector timed out after {timeout_seconds} seconds"
        )
        self._log_failure(report)
        return report

    def should_trigger_healing(self, failure: FailureReport) -> bool:
        """
        Determine if a failure should trigger self-healing.
        
        Some failures (like WRONG_CONTENT) might not need healing
        if the selector itself is still valid.
        
        Args:
            failure: The failure report to analyze
            
        Returns:
            True if healing should be triggered
        """
        healable_failures = {
            FailureType.ELEMENT_NOT_FOUND,
            FailureType.STALE_ELEMENT,
            FailureType.TIMEOUT,
            FailureType.EMPTY_RESULT
        }
        return failure.failure_type in healable_failures

    def get_failure_stats(self) -> Dict[str, Any]:
        """
        Get statistics about recent failures.
        
        Returns:
            Dict with failure counts by type
        """
        stats = {
            "total_failures": len(self.failure_history),
            "by_type": {},
            "recent_failures": []
        }
        
        for failure in self.failure_history:
            type_name = failure.failure_type.value
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1
        
        # Last 10 failures
        stats["recent_failures"] = [
            f.to_dict() for f in self.failure_history[-10:]
        ]
        
        return stats

    def _extract_content(self, element: Any) -> str:
        """Extract text content from various element types."""
        if hasattr(element, "text"):
            return element.text
        if hasattr(element, "get_text"):
            return element.get_text(strip=True)
        if isinstance(element, str):
            return element
        return str(element)

    def _log_failure(self, report: FailureReport) -> None:
        """Log and store failure report."""
        self.failure_history.append(report)
        logger.warning(
            f"Selector failure detected: {report.failure_type.value} "
            f"for selector '{report.selector}' at {report.url}"
        )

    def clear_history(self) -> None:
        """Clear failure history."""
        self.failure_history.clear()
