"""
Feature Extractor Module
Extracts ML features from DOM elements for selector prediction.
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loguru import logger
import re


@dataclass
class ElementFeatures:
    """Feature vector representation of a DOM element."""
    tag_encoded: np.ndarray  # One-hot encoded tag
    class_similarity: float  # Jaccard similarity with reference classes
    id_similarity: float     # Normalized Levenshtein for ID
    parent_tag_encoded: np.ndarray  # One-hot encoded parent tag
    sibling_count: float     # Normalized sibling count
    text_length: float       # Log-scaled text length
    attr_overlap: float      # Attribute overlap score
    tag_similarity: float    # 1.0 if match, 0.0 otherwise
    text_length_similarity: float # Ratio of lengths
    
    def to_vector(self) -> np.ndarray:
        """Convert to flat numpy array for ML model."""
        return np.concatenate([
            self.tag_encoded,
            [self.class_similarity],
            [self.id_similarity],
            self.parent_tag_encoded,
            [self.sibling_count],
            [self.text_length],
            [self.attr_overlap],
            [self.tag_similarity],
            [self.text_length_similarity]
        ])


class FeatureExtractor:
    """
    Extracts ML-ready features from DOM elements.
    
    Features:
    1. Tag name (one-hot encoded)
    2. Class similarity score (Jaccard index)
    3. ID similarity score (Levenshtein-based)
    4. Parent tag (one-hot encoded)
    5. Sibling count (normalized)
    6. Text length (log-scaled)
    7. Attribute overlap score
    8. Tag similarity (binary)
    9. Text length similarity (ratio)
    """

    # Common HTML tags for one-hot encoding
    COMMON_TAGS = [
        "div", "span", "a", "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "ul", "ol", "li", "table", "tr", "td", "th", "form", "input",
        "button", "img", "nav", "header", "footer", "section", "article",
        "main", "aside", "label", "select", "option", "textarea", "iframe"
    ]

    def __init__(self):
        self.tag_to_idx = {tag: idx for idx, tag in enumerate(self.COMMON_TAGS)}
        self.num_tags = len(self.COMMON_TAGS) + 1  # +1 for "other"

    def extract_features(
        self,
        element: Dict[str, Any],
        reference: Optional[Dict[str, Any]] = None
    ) -> ElementFeatures:
        """
        Extract feature vector from DOM element.
        
        Args:
            element: Element info dictionary
            reference: Original element to compare against (for similarity scores)
            
        Returns:
            ElementFeatures dataclass
        """
        # 1. Tag encoding
        tag_name = element.get("tag_name", "div")
        tag_encoded = self._encode_tag(tag_name)
        
        # 2. Class similarity
        if reference and reference.get("classes"):
            class_similarity = self._jaccard_similarity(
                element.get("classes", []),
                reference.get("classes", [])
            )
        else:
            class_similarity = 0.0
        
        # 3. ID similarity
        if reference and reference.get("element_id"):
            id_similarity = self._string_similarity(
                element.get("element_id", ""),
                reference.get("element_id", "")
            )
        else:
            id_similarity = 1.0 if element.get("element_id") else 0.0
        
        # 4. Parent tag encoding
        parent_tag_encoded = self._encode_tag(element.get("parent_tag", "body"))
        
        # 5. Sibling count (normalized with sigmoid-like function)
        sibling_count = element.get("sibling_count", 0)
        normalized_siblings = sibling_count / (sibling_count + 5)  # Soft normalization
        
        # 6. Text length (log-scaled)
        text = element.get("text_content", "")
        text_len_val = len(text)
        text_length = np.log1p(text_len_val) / 10  # Normalized log scale
        
        # 7. Attribute overlap
        if reference and reference.get("attributes"):
            attr_overlap = self._attribute_overlap(
                element.get("attributes", {}),
                reference.get("attributes", {})
            )
        else:
            attr_overlap = 0.5  # Neutral score if no reference

        # 8. Tag similarity
        if reference:
            ref_tag = reference.get("tag_name", "").lower()
            tag_similarity = 1.0 if tag_name.lower() == ref_tag else 0.0
        else:
            tag_similarity = 0.0
            
        # 9. Text length similarity
        if reference:
            # We don't always have reference text length, but if we do...
            # Or we infer it from text_content if present in reference
            ref_text = reference.get("text_content", "")
            ref_len = len(ref_text)
            if ref_len > 0 and text_len_val > 0:
                # Ratio of smaller / larger
                text_length_similarity = min(text_len_val, ref_len) / max(text_len_val, ref_len)
            elif ref_len == 0 and text_len_val == 0:
                text_length_similarity = 1.0
            else:
                text_length_similarity = 0.0
        else:
            text_length_similarity = 0.0
        
        return ElementFeatures(
            tag_encoded=tag_encoded,
            class_similarity=class_similarity,
            id_similarity=id_similarity,
            parent_tag_encoded=parent_tag_encoded,
            sibling_count=normalized_siblings,
            text_length=text_length,
            attr_overlap=attr_overlap,
            tag_similarity=tag_similarity,
            text_length_similarity=text_length_similarity
        )

    def extract_batch(
        self,
        elements: List[Dict[str, Any]],
        reference: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Extract features for multiple elements.
        
        Args:
            elements: List of element dictionaries
            reference: Reference element for similarity comparison
            
        Returns:
            2D numpy array of shape (n_elements, n_features)
        """
        feature_vectors = []
        
        for element in elements:
            features = self.extract_features(element, reference)
            feature_vectors.append(features.to_vector())
        
        return np.array(feature_vectors)

    def get_feature_names(self) -> List[str]:
        """Get names of all features for interpretability."""
        names = []
        
        # Tag encoding features
        names.extend([f"tag_{tag}" for tag in self.COMMON_TAGS])
        names.append("tag_other")
        
        # Scalar features
        names.append("class_similarity")
        names.append("id_similarity")
        
        # Parent tag encoding
        names.extend([f"parent_{tag}" for tag in self.COMMON_TAGS])
        names.append("parent_other")
        
        # More scalar features
        names.extend(["sibling_count", "text_length", "attr_overlap", "tag_similarity", "text_length_similarity"])
        
        return names

    def _encode_tag(self, tag: str) -> np.ndarray:
        """One-hot encode a tag name."""
        encoded = np.zeros(self.num_tags)
        tag = tag.lower()
        
        if tag in self.tag_to_idx:
            encoded[self.tag_to_idx[tag]] = 1.0
        else:
            encoded[-1] = 1.0  # "other" category
        
        return encoded

    def _jaccard_similarity(
        self,
        list1: List[str],
        list2: List[str]
    ) -> float:
        """Calculate Jaccard similarity between two lists."""
        if not list1 and not list2:
            return 1.0
        if not list1 or not list2:
            return 0.0
        
        set1, set2 = set(list1), set(list2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0

    def _string_similarity(
        self,
        str1: Optional[str],
        str2: Optional[str]
    ) -> float:
        """
        Calculate normalized string similarity.
        Uses simplified Levenshtein ratio.
        """
        if not str1 or not str2:
            return 0.0
        
        if str1 == str2:
            return 1.0
        
        # Simple character-level Jaccard as approximation
        set1, set2 = set(str1.lower()), set(str2.lower())
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0

    def _attribute_overlap(
        self,
        attrs1: Dict[str, str],
        attrs2: Dict[str, str]
    ) -> float:
        """
        Calculate attribute overlap score.
        Considers both key and value matching.
        """
        if not attrs1 and not attrs2:
            return 1.0
        if not attrs1 or not attrs2:
            return 0.0
        
        keys1, keys2 = set(attrs1.keys()), set(attrs2.keys())
        common_keys = keys1 & keys2
        
        if not common_keys:
            return 0.0
        
        # Score based on common keys and matching values
        matches = sum(
            1 for k in common_keys
            if attrs1.get(k) == attrs2.get(k)
        )
        
        key_overlap = len(common_keys) / len(keys1 | keys2)
        value_match_ratio = matches / len(common_keys)
        
        return (key_overlap + value_match_ratio) / 2

    def create_training_sample(
        self,
        element: Dict[str, Any],
        reference: Dict[str, Any],
        is_match: bool
    ) -> Tuple[np.ndarray, int]:
        """
        Create a labeled training sample.
        
        Args:
            element: Candidate element
            reference: Original reference element
            is_match: Whether this element is the correct match
            
        Returns:
            Tuple of (feature_vector, label)
        """
        features = self.extract_features(element, reference)
        label = 1 if is_match else 0
        return features.to_vector(), label
