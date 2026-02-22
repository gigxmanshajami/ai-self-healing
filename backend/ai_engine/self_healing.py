"""
Self-Healing Orchestrator
Coordinates the complete self-healing flow when selectors fail.
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
import asyncio

from .feature_extractor import FeatureExtractor
from .selector_model import SelectorModel, create_synthetic_training_data
from .xpath_generator import XPathGenerator, GeneratedXPath


@dataclass
class HealingResult:
    """Result of a self-healing attempt."""
    success: bool
    original_selector: str
    new_selector: Optional[str]
    confidence: float
    healing_time_ms: float
    candidates_analyzed: int
    strategy_used: str
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "original_selector": self.original_selector,
            "new_selector": self.new_selector,
            "confidence": round(self.confidence, 4),
            "healing_time_ms": round(self.healing_time_ms, 2),
            "candidates_analyzed": self.candidates_analyzed,
            "strategy_used": self.strategy_used,
            "error_message": self.error_message
        }


@dataclass
class HealingSession:
    """Tracks a complete healing session with history."""
    session_id: str
    url: str
    started_at: datetime
    attempts: List[HealingResult] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    final_status: str = "in_progress"


class SelfHealingEngine:
    """
    Orchestrates the 8-step self-healing flow:
    
    1. Detect original selector failure
    2. Trigger healing process
    3. Scan full DOM for candidates
    4. Extract feature vectors
    5. ML predicts target element
    6. Generate new XPath
    7. Validate and retry scraping
    8. Store successful selector for learning
    
    This is the core brain of the self-healing system.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = 0.6,
        max_candidates: int = 100
    ):
        """
        Initialize self-healing engine.
        
        Args:
            model_path: Path to ML model
            confidence_threshold: Minimum confidence for accepting match
            max_candidates: Maximum DOM elements to analyze
        """
        self.feature_extractor = FeatureExtractor()
        self.model = SelectorModel(model_path=model_path)
        self.xpath_generator = XPathGenerator()
        
        self.confidence_threshold = confidence_threshold
        self.max_candidates = max_candidates
        
        self.healing_history: List[HealingResult] = []
        self.active_sessions: Dict[str, HealingSession] = {}
        
        # Initialize model if not trained
        if not self.model.is_trained:
            self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize model with synthetic data if no trained model exists."""
        logger.info("Initializing model with synthetic training data...")
        X, y = create_synthetic_training_data(n_samples=2000)
        self.model.train(X, y)

    async def heal(
        self,
        original_selector: str,
        original_element_info: Dict[str, Any],
        dom_elements: List[Dict[str, Any]],
        url: str
    ) -> HealingResult:
        """
        Execute the complete self-healing flow.
        
        Args:
            original_selector: The failing CSS/XPath selector
            original_element_info: Properties of the original element
            dom_elements: All elements currently in DOM
            url: Current page URL
            
        Returns:
            HealingResult with success status and new selector
        """
        import time
        start_time = time.time()
        
        logger.info(f"Starting healing for selector: {original_selector}")
        
        try:
            # Step 3: Filter and limit candidates
            candidates = self._filter_candidates(dom_elements, original_element_info)
            
            if not candidates:
                return HealingResult(
                    success=False,
                    original_selector=original_selector,
                    new_selector=None,
                    confidence=0.0,
                    healing_time_ms=(time.time() - start_time) * 1000,
                    candidates_analyzed=0,
                    strategy_used="none",
                    error_message="No suitable candidates found in DOM"
                )
            
            # Step 4: Extract features for all candidates
            features = self.feature_extractor.extract_batch(
                candidates,
                reference=original_element_info
            )
            
            # Step 5: ML predicts best match
            best_idx, confidence = self.model.predict_best_match(
                features,
                threshold=self.confidence_threshold
            )
            
            if confidence < self.confidence_threshold:
                return HealingResult(
                    success=False,
                    original_selector=original_selector,
                    new_selector=None,
                    confidence=confidence,
                    healing_time_ms=(time.time() - start_time) * 1000,
                    candidates_analyzed=len(candidates),
                    strategy_used="ml_prediction",
                    error_message=f"Best match confidence ({confidence:.2f}) below threshold"
                )
            
            # Step 6: Generate new XPath
            best_candidate = candidates[best_idx]
            xpath_result = self.xpath_generator.generate(best_candidate)
            
            # Step 7 & 8: Create result (validation happens in scraper)
            healing_time = (time.time() - start_time) * 1000
            
            result = HealingResult(
                success=True,
                original_selector=original_selector,
                new_selector=xpath_result.primary,
                confidence=confidence,
                healing_time_ms=healing_time,
                candidates_analyzed=len(candidates),
                strategy_used=xpath_result.strategy_used
            )
            
            self.healing_history.append(result)
            logger.info(
                f"Healing successful! New selector: {xpath_result.primary} "
                f"(confidence: {confidence:.2f})"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Healing failed with error: {e}")
            return HealingResult(
                success=False,
                original_selector=original_selector,
                new_selector=None,
                confidence=0.0,
                healing_time_ms=(time.time() - start_time) * 1000,
                candidates_analyzed=0,
                strategy_used="error",
                error_message=str(e)
            )

    def heal_sync(
        self,
        original_selector: str,
        original_element_info: Dict[str, Any],
        dom_elements: List[Dict[str, Any]],
        url: str
    ) -> HealingResult:
        """Synchronous wrapper for heal method."""
        return asyncio.get_event_loop().run_until_complete(
            self.heal(original_selector, original_element_info, dom_elements, url)
        )

    def _filter_candidates(
        self,
        elements: List[Dict[str, Any]],
        reference: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Filter DOM elements to reasonable candidates.
        
        Filters:
        - Same tag type (high priority)
        - Similar class names
        - Reasonable text length match
        - Interactive elements (buttons, links, headings)
        """
        ref_tag = reference.get("tag_name", "").lower()
        ref_classes = set(reference.get("classes", []))
        
        # Priority tags for content extraction
        content_tags = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 
                       'button', 'div', 'li', 'td', 'th', 'article', 'section',
                       'main', 'header', 'footer', 'nav', 'img', 'input', 'label'}
        
        scored_candidates = []
        
        for element in elements:
            score = 0
            elem_tag = element.get("tag_name", "").lower()
            
            # Tag match (exact)
            if elem_tag == ref_tag:
                score += 3
            
            # Class overlap
            elem_classes = set(element.get("classes", []))
            if ref_classes and elem_classes:
                overlap = len(ref_classes & elem_classes) / len(ref_classes | elem_classes)
                score += overlap * 2
            
            # Has ID (bonus)
            if element.get("element_id"):
                score += 1
            
            # Is a common content tag (bonus for lenient matching)
            if elem_tag in content_tags:
                score += 0.5
            
            # Has text content
            if element.get("text_content", "").strip():
                score += 0.5
            
            # Include if any score OR if it's a content tag
            if score > 0 or elem_tag in content_tags:
                scored_candidates.append((score, element))
        
        # Sort by score and limit
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        candidates = [c[1] for c in scored_candidates[:self.max_candidates]]
        
        logger.debug(f"Filtered {len(elements)} elements to {len(candidates)} candidates")
        return candidates

    def record_success(
        self,
        original_selector: str,
        new_selector: str,
        element_snapshot: Dict[str, Any]
    ) -> None:
        """
        Record successful healing for model training.
        
        Args:
            original_selector: The original failing selector
            new_selector: The new working selector
            element_snapshot: Properties of the matched element
        """
        logger.info(f"Recording successful healing: {original_selector} -> {new_selector}")
        # In production: store in database for retraining

    def record_failure(
        self,
        original_selector: str,
        attempted_selector: str,
        element_snapshot: Dict[str, Any]
    ) -> None:
        """
        Record failed healing attempt for model improvement.
        
        Args:
            original_selector: The original failing selector
            attempted_selector: The healing attempt that failed
            element_snapshot: Properties of the incorrect match
        """
        logger.warning(f"Recording failed healing attempt: {attempted_selector}")
        # In production: store as negative training example

    def get_healing_stats(self) -> Dict[str, Any]:
        """Get statistics about healing attempts."""
        if not self.healing_history:
            return {
                "total_attempts": 0,
                "success_rate": 0.0,
                "avg_confidence": 0.0,
                "avg_healing_time_ms": 0.0
            }
        
        successes = sum(1 for h in self.healing_history if h.success)
        total_confidence = sum(h.confidence for h in self.healing_history)
        total_time = sum(h.healing_time_ms for h in self.healing_history)
        
        by_strategy = {}
        for h in self.healing_history:
            strategy = h.strategy_used
            by_strategy[strategy] = by_strategy.get(strategy, 0) + 1
        
        return {
            "total_attempts": len(self.healing_history),
            "success_rate": round(successes / len(self.healing_history), 4),
            "avg_confidence": round(total_confidence / len(self.healing_history), 4),
            "avg_healing_time_ms": round(total_time / len(self.healing_history), 2),
            "successful_healings": successes,
            "failed_healings": len(self.healing_history) - successes,
            "by_strategy": by_strategy
        }

    def get_model_status(self) -> Dict[str, Any]:
        """Get ML model status and metrics."""
        return {
            "model": self.model.get_status(),
            "xpath_generator": self.xpath_generator.get_generation_stats(),
            "healing_stats": self.get_healing_stats()
        }
