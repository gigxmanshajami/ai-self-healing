"""
Base Scraper Module
Core scraping logic with BeautifulSoup DOM parsing.
"""

from bs4 import BeautifulSoup, Tag
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from loguru import logger
import re
from lxml import html


@dataclass
class LxmlTagWrapper:
    """Wrapper for lxml element to mimic BeautifulSoup interface."""
    element: Any

    @property
    def name(self) -> str:
        """Return the tag name of the element."""
        return self.element.tag if hasattr(self.element, 'tag') else ''

    def get(self, attr: str, default=None):
        """Get an attribute value from the lxml element."""
        try:
            val = self.element.get(attr)
            return val if val is not None else default
        except Exception:
            return default

    def get_text(self, strip: bool = True) -> str:
        text = self.element.text_content()
        return text.strip() if strip else text

    @property
    def string(self):
        return self.element.text


@dataclass
class ElementInfo:
    """Structured representation of a DOM element."""
    tag_name: str
    element_id: Optional[str]
    classes: List[str]
    text_content: str
    attributes: Dict[str, str]
    parent_tag: Optional[str]
    sibling_count: int
    child_count: int
    xpath: str
    html: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag_name": self.tag_name,
            "element_id": self.element_id,
            "classes": self.classes,
            "text_content": self.text_content[:100] if self.text_content else "",
            "attributes": self.attributes,
            "parent_tag": self.parent_tag,
            "sibling_count": self.sibling_count,
            "child_count": self.child_count,
            "xpath": self.xpath,
            "html": self.html[:200] if self.html else ""
        }


class BaseScraper:
    """
    Core scraping logic with advanced DOM parsing capabilities.
    Provides element extraction and analysis for self-healing.
    """

    def __init__(self, html_content: str):
        """
        Initialize scraper with HTML content.
        
        Args:
            html_content: Raw HTML string to parse
        """
        self.soup = BeautifulSoup(html_content, "lxml")
        try:
            self.tree = html.fromstring(html_content)
        except Exception as e:
            logger.warning(f"Failed to parse HTML with lxml: {e}")
            self.tree = None
        self._element_cache: Dict[str, ElementInfo] = {}

    def find_by_selector(self, selector: str) -> Optional[Tag]:
        """
        Find element by CSS selector.
        
        Args:
            selector: CSS selector string
            
        Returns:
            BeautifulSoup Tag if found, None otherwise
        """
        try:
            element = self.soup.select_one(selector)
            return element
        except Exception as e:
            logger.debug(f"Selector error: {e}")
            return None

    def find_all_by_selector(self, selector: str) -> List[Tag]:
        """
        Find ALL elements matching a CSS selector.
        
        Args:
            selector: CSS selector string
            
        Returns:
            List of matching BeautifulSoup Tags
        """
        try:
            elements = self.soup.select(selector)
            return elements or []
        except Exception as e:
            logger.debug(f"Selector error: {e}")
            return []

    def extract_element_info(self, element: Tag) -> ElementInfo:
        """
        Extract comprehensive information about a DOM element.
        
        Args:
            element: BeautifulSoup Tag to analyze
            
        Returns:
            ElementInfo with all extracted data
        """
        # Get parent info
        parent = element.parent
        parent_tag = parent.name if parent else None
        
        # Count siblings
        siblings = list(element.parent.children) if element.parent else []
        sibling_count = len([s for s in siblings if isinstance(s, Tag)]) - 1
        
        # Get children count
        children = list(element.children)
        child_count = len([c for c in children if isinstance(c, Tag)])
        
        # Extract text content
        text = element.get_text(strip=True) if element.string else ""
        if not text:
            text = " ".join(element.stripped_strings)
        
        # Get all attributes
        attrs = dict(element.attrs) if element.attrs else {}
        
        # Generate XPath
        xpath = self._generate_xpath(element)
        
        return ElementInfo(
            tag_name=element.name,
            element_id=attrs.get("id"),
            classes=attrs.get("class", []) if isinstance(attrs.get("class"), list) else [],
            text_content=text[:500],
            attributes={k: str(v) for k, v in attrs.items() if k not in ["class", "id"]},
            parent_tag=parent_tag,
            sibling_count=sibling_count,
            child_count=child_count,
            xpath=xpath,
            html=str(element)[:500]
        )

    def get_all_elements(self) -> List[ElementInfo]:
        """
        Extract info for all meaningful elements in DOM.
        Filters out script, style, and empty elements.
        
        Returns:
            List of ElementInfo for all valid elements
        """
        all_elements = []
        excluded_tags = {"script", "style", "meta", "link", "head", "html", "noscript"}
        
        for element in self.soup.find_all(True):
            if element.name not in excluded_tags and not element.find_parent("noscript"):
                try:
                    info = self.extract_element_info(element)
                    all_elements.append(info)
                except Exception as e:
                    logger.debug(f"Error extracting element: {e}")
                    continue
        
        logger.info(f"Extracted {len(all_elements)} elements from DOM")
        return all_elements

    def _generate_xpath(self, element: Tag) -> str:
        """
        Generate XPath for an element.
        
        Args:
            element: BeautifulSoup Tag
            
        Returns:
            XPath string
        """
        parts = []
        current = element
        
        while current and current.name:
            if current.name == "[document]":
                break
            
            # Count preceding siblings with same tag
            siblings = list(current.find_previous_siblings(current.name))
            index = len(siblings) + 1
            
            if current.get("id"):
                parts.insert(0, f'//*[@id="{current.get("id")}"]')
                break
            else:
                parts.insert(0, f"{current.name}[{index}]")
            
            current = current.parent
        
        return "/" + "/".join(parts) if parts else ""

    def get_element_by_xpath(self, xpath: str) -> Optional[Any]:
        """
        Find element by XPath using lxml.
        """
        if self.tree is None:
            logger.warning("LXML tree not initialized - cannot evaluate XPath")
            return None

        try:
            elements = self.tree.xpath(xpath)
            if elements:
                # Wrap the lxml element to provide a compatible get_text method
                return LxmlTagWrapper(elements[0])
            return None
        except Exception as e:
            logger.warning(f"XPath evaluation failed: {e}")
            return None

    def find_similar_elements(
        self,
        reference: ElementInfo,
        candidates: List[ElementInfo],
        threshold: float = 0.5
    ) -> List[Tuple[ElementInfo, float]]:
        """
        Find elements similar to a reference element.
        
        Args:
            reference: The original element to match
            candidates: List of potential matches
            threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (element, score) tuples above threshold
        """
        similar = []
        
        for candidate in candidates:
            score = self._calculate_similarity(reference, candidate)
            if score >= threshold:
                similar.append((candidate, score))
        
        # Sort by similarity descending
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar

    def _calculate_similarity(
        self,
        ref: ElementInfo,
        candidate: ElementInfo
    ) -> float:
        """
        Calculate similarity score between two elements.
        
        Uses weighted combination of:
        - Tag match
        - Class overlap (Jaccard)
        - ID similarity
        - Text similarity
        - Attribute overlap
        """
        score = 0.0
        weights = {
            "tag": 0.2,
            "id": 0.25,
            "classes": 0.25,
            "text": 0.15,
            "attributes": 0.15
        }
        
        # Tag name match
        if ref.tag_name == candidate.tag_name:
            score += weights["tag"]
        
        # ID match
        if ref.element_id and candidate.element_id:
            if ref.element_id == candidate.element_id:
                score += weights["id"]
            elif ref.element_id in candidate.element_id or candidate.element_id in ref.element_id:
                score += weights["id"] * 0.5
        
        # Class overlap (Jaccard similarity)
        if ref.classes or candidate.classes:
            ref_set = set(ref.classes)
            cand_set = set(candidate.classes)
            if ref_set or cand_set:
                jaccard = len(ref_set & cand_set) / len(ref_set | cand_set)
                score += weights["classes"] * jaccard
        
        # Text content similarity
        if ref.text_content and candidate.text_content:
            ref_words = set(ref.text_content.lower().split())
            cand_words = set(candidate.text_content.lower().split())
            if ref_words or cand_words:
                text_sim = len(ref_words & cand_words) / max(len(ref_words | cand_words), 1)
                score += weights["text"] * text_sim
        
        # Attribute overlap
        if ref.attributes or candidate.attributes:
            ref_attrs = set(ref.attributes.keys())
            cand_attrs = set(candidate.attributes.keys())
            if ref_attrs or cand_attrs:
                attr_sim = len(ref_attrs & cand_attrs) / max(len(ref_attrs | cand_attrs), 1)
                score += weights["attributes"] * attr_sim
        
        return round(score, 4)

    def extract_text(self, selector: str) -> Optional[str]:
        """Extract text content from element matching selector."""
        element = self.find_by_selector(selector)
        if element:
            return element.get_text(strip=True)
        return None

    def extract_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Extract specific attribute from element matching selector."""
        element = self.find_by_selector(selector)
        if element:
            return element.get(attribute)
        return None
