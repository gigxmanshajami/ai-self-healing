"""
XPath Generator Module
Generates robust XPath selectors from matched DOM elements.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class GeneratedXPath:
    """Result of XPath generation with multiple strategies."""
    primary: str           # Best/primary XPath
    by_id: Optional[str]   # ID-based (most robust)
    by_class: Optional[str] # Class-based
    by_hierarchy: str      # Position-based (fallback)
    by_attributes: Optional[str]  # Attribute-based
    confidence: float      # Confidence in generated XPath
    strategy_used: str     # Which strategy was primary
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary": self.primary,
            "alternatives": {
                "by_id": self.by_id,
                "by_class": self.by_class,
                "by_hierarchy": self.by_hierarchy,
                "by_attributes": self.by_attributes
            },
            "confidence": round(self.confidence, 4),
            "strategy": self.strategy_used
        }


class XPathGenerator:
    """
    Generates robust XPath expressions from element properties.
    
    Strategies (in order of preference):
    1. ID-based: Most stable, rarely changes
    2. Unique class combination: Good balance
    3. Attribute-based: Data attributes, name, etc.
    4. Hierarchy-based: Position in DOM (least stable)
    """

    # Attributes worth using for XPath
    USEFUL_ATTRIBUTES = [
        "name", "data-testid", "data-id", "aria-label",
        "title", "type", "role", "href", "src", "alt"
    ]

    def __init__(self):
        self.generation_history: List[GeneratedXPath] = []

    def generate(self, element: Dict[str, Any]) -> GeneratedXPath:
        """
        Generate XPath for an element using multiple strategies.
        
        Args:
            element: Element info dictionary with tag_name, element_id,
                    classes, attributes, parent_tag, etc.
                    
        Returns:
            GeneratedXPath with primary and alternative selectors
        """
        tag = element.get("tag_name", "div")
        element_id = element.get("element_id")
        classes = element.get("classes", [])
        attributes = element.get("attributes", {})
        parent_tag = element.get("parent_tag")
        xpath_hierarchy = element.get("xpath", "")
        
        # Strategy 1: ID-based (most robust)
        by_id = None
        if element_id:
            by_id = f'//*[@id="{element_id}"]'
        
        # Strategy 2: Class-based
        by_class = None
        if classes:
            if len(classes) == 1:
                by_class = f'//{tag}[contains(@class, "{classes[0]}")]'
            else:
                # Combine multiple classes
                conditions = " and ".join([
                    f'contains(@class, "{c}")' for c in classes[:3]
                ])
                by_class = f'//{tag}[{conditions}]'
        
        # Strategy 3: Attribute-based
        by_attributes = None
        for attr in self.USEFUL_ATTRIBUTES:
            if attr in attributes:
                value = attributes[attr]
                by_attributes = f'//{tag}[@{attr}="{value}"]'
                break
        
        # Strategy 4: Hierarchy-based (fallback)
        by_hierarchy = xpath_hierarchy or f"//{tag}"
        
        # Choose primary strategy
        primary, strategy, confidence = self._select_primary(
            by_id, by_class, by_attributes, by_hierarchy, tag
        )
        
        result = GeneratedXPath(
            primary=primary,
            by_id=by_id,
            by_class=by_class,
            by_hierarchy=by_hierarchy,
            by_attributes=by_attributes,
            confidence=confidence,
            strategy_used=strategy
        )
        
        self.generation_history.append(result)
        logger.info(f"Generated XPath using {strategy}: {primary}")
        
        return result

    def generate_from_text(
        self,
        tag: str,
        text_content: str,
        exact: bool = False
    ) -> str:
        """
        Generate XPath based on text content.
        
        Args:
            tag: HTML tag name
            text_content: Text to match
            exact: If True, match exact text; otherwise contains
            
        Returns:
            XPath string
        """
        text_clean = text_content.replace('"', '\\"')[:100]
        
        if exact:
            return f'//{tag}[text()="{text_clean}"]'
        else:
            return f'//{tag}[contains(text(), "{text_clean}")]'

    def generate_relative(
        self,
        anchor_xpath: str,
        target_info: Dict[str, Any],
        relationship: str = "following-sibling"
    ) -> str:
        """
        Generate relative XPath from an anchor element.
        
        Args:
            anchor_xpath: XPath of anchor element
            target_info: Info about target element
            relationship: Axis (following-sibling, preceding-sibling, child, etc.)
            
        Returns:
            Relative XPath string
        """
        tag = target_info.get("tag_name", "*")
        
        if relationship == "child":
            return f"{anchor_xpath}/{tag}"
        elif relationship == "descendant":
            return f"{anchor_xpath}//{tag}"
        else:
            return f"{anchor_xpath}/{relationship}::{tag}[1]"

    def validate_xpath(self, xpath: str) -> bool:
        """
        Basic validation of XPath syntax.
        
        Args:
            xpath: XPath string to validate
            
        Returns:
            True if appears valid
        """
        if not xpath:
            return False
        
        # Basic checks
        if not xpath.startswith("/") and not xpath.startswith("("):
            return False
        
        # Check balanced brackets
        if xpath.count("[") != xpath.count("]"):
            return False
        if xpath.count("(") != xpath.count(")"):
            return False
        
        # Check for common errors
        if "//" in xpath and xpath.startswith("///"):
            return False
        
        return True

    def simplify_xpath(self, xpath: str) -> str:
        """
        Simplify an XPath by removing unnecessary parts.
        
        Args:
            xpath: Original XPath
            
        Returns:
            Simplified XPath
        """
        # If ID-based, no need to simplify
        if "[@id=" in xpath and xpath.count("/") <= 2:
            return xpath
        
        # Remove unnecessary position predicates if ID exists
        if "[@id=" in xpath:
            # Extract ID-based portion
            import re
            id_match = re.search(r'/?\*?\[@id="[^"]+"\]', xpath)
            if id_match:
                return f'//{id_match.group(0).lstrip("/")}'
        
        return xpath

    def _select_primary(
        self,
        by_id: Optional[str],
        by_class: Optional[str],
        by_attributes: Optional[str],
        by_hierarchy: str,
        tag: str
    ) -> tuple:
        """
        Select the best primary XPath from options.
        
        Returns:
            Tuple of (xpath, strategy_name, confidence)
        """
        # Preference order with confidence scores
        if by_id:
            return by_id, "id", 0.95
        
        if by_attributes:
            return by_attributes, "attributes", 0.85
        
        if by_class:
            return by_class, "class", 0.75
        
        return by_hierarchy, "hierarchy", 0.5

    def get_generation_stats(self) -> Dict[str, Any]:
        """Get statistics about XPath generation."""
        if not self.generation_history:
            return {"total_generations": 0}
        
        stats = {
            "total_generations": len(self.generation_history),
            "by_strategy": {},
            "avg_confidence": 0.0
        }
        
        total_confidence = 0.0
        for xpath in self.generation_history:
            strategy = xpath.strategy_used
            stats["by_strategy"][strategy] = stats["by_strategy"].get(strategy, 0) + 1
            total_confidence += xpath.confidence
        
        stats["avg_confidence"] = round(
            total_confidence / len(self.generation_history), 4
        )
        
        return stats
