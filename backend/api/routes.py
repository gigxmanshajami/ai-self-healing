"""
API Routes
FastAPI endpoints for the self-healing scraper.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional, List
from datetime import datetime
import uuid
import time

from .schemas import (
    ScrapeRequest, ScrapeResponse, ScrapeResult,
    HealRequest, HealResponse,
    LogsResponse, LogEntry,
    ModelStatusResponse, ModelMetricsResponse,
    SelectorHistoryResponse, SelectorHistoryEntry,
    HealthResponse, ErrorResponse,    
    Settings,
    JobStatus, HealingStrategy
)
from scraper import SeleniumDriver, BaseScraper, FailureDetector
from ai_engine import SelfHealingEngine, FeatureExtractor
from storage import get_database, get_selector_history
from loguru import logger


router = APIRouter()


def extract_element_value(element) -> str:
    """Smart extraction: returns the most meaningful value based on element type."""
    if element is None:
        return None
    tag = element.name if hasattr(element, 'name') else ''
    # Images → src
    if tag in ('img', 'video', 'source'):
        return element.get('src') or element.get('data-src') or element.get('srcset', '').split(',')[0].strip().split(' ')[0] or element.get('alt') or ''
    # Links → href
    if tag == 'a':
        text = element.get_text(strip=True)
        href = element.get('href', '')
        return f"{text} ({href})" if text else href
    # Inputs → value
    if tag in ('input', 'textarea', 'select'):
        return element.get('value') or element.get('placeholder') or ''
    # Meta tags → content
    if tag == 'meta':
        return element.get('content') or ''
    # Default → text, but fallback to key attributes if text is empty
    text = element.get_text(strip=True)
    if text:
        return text
    # Fallback: try common attributes
    for attr in ('src', 'href', 'data-src', 'alt', 'title', 'content', 'value'):
        val = element.get(attr)
        if val:
            return val
    return ''

# Lazy-loaded components
_healing_engine: Optional[SelfHealingEngine] = None
_failure_detector: Optional[FailureDetector] = None


def get_healing_engine() -> SelfHealingEngine:
    """Get or create healing engine instance."""
    global _healing_engine
    if _healing_engine is None:
        _healing_engine = SelfHealingEngine(
            model_path="models/selector_model.pkl",
            confidence_threshold=0.6
        )
    return _healing_engine


def get_failure_detector() -> FailureDetector:
    """Get or create failure detector instance."""
    global _failure_detector
    if _failure_detector is None:
        _failure_detector = FailureDetector()
    return _failure_detector


# ============ SCRAPE ENDPOINT ============

@router.post("/scrape", response_model=ScrapeResponse, tags=["Scraping"])
async def scrape_url(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """
    Execute a scraping job with self-healing capability.
    
    When a selector fails:
    1. The system detects the failure
    2. Scans the DOM for candidate elements
    3. Uses ML to predict the correct element
    4. Generates a new XPath selector
    5. Retries the scraping
    6. Stores the result for learning
    """
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    
    logger.info(f"Starting scrape job {job_id} for {request.url}")
    
    # Initialize database
    db = await get_database()
    settings = await db.get_settings()
    
    await db.insert_scrape_job(
        job_id=job_id,
        url=request.url,
        selectors=list(request.selectors.keys())
    )
    
    results: List[ScrapeResult] = []
    healing_triggered = False
    total_healed = 0
    screenshot_path = None
    error_message = None
    
    try:
        # Initialize Selenium
        # Use settings from DB for headless mode and other configs
        headless_mode = settings.get("headless", True)
        driver_timeout = request.timeout if request.timeout else settings.get("timeout", 15)
        
        with SeleniumDriver(headless=headless_mode, timeout=driver_timeout) as driver:
            # Navigate to URL
            if not driver.navigate(request.url):
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to navigate to {request.url}"
                )
            
            # Wait for specific selector if requested
            if request.wait_for_selector:
                driver.find_element(request.wait_for_selector, wait=True)
            
            # Get page source for parsing
            html = driver.get_page_source()
            scraper = BaseScraper(html)
            detector = get_failure_detector()
            healing_engine = get_healing_engine()
            
            # Process each selector
            for field, selector in request.selectors.items():
                # Check for XPath or CSS selector
                if selector.startswith('/') or 'xpath' in selector.lower():
                    element = scraper.get_element_by_xpath(selector)
                else:
                    element = scraper.find_by_selector(selector)
                
                failure = detector.detect_failure(element, selector, request.url)
                
                if not failure and element and hasattr(element, 'name'):
                    try:
                        # Save successful scrape fingerprint for future healing reference
                        info = scraper.extract_element_info(element).to_dict()
                        await db.save_selector_history(request.url, selector, info)
                    except Exception as e:
                        logger.warning(f"Failed to save history for {selector}: {e}")
                
                if failure and request.enable_healing:
                    # Trigger self-healing
                    healing_triggered = True
                    logger.info(f"Healing triggered for {field}: {selector}")

                    
                    # Get historical reference or fallback
                    reference = await db.get_last_successful_selector(request.url, selector)
                    
                    # Try historical xpath shortcut first (fastest healing path)
                    healed_via_history = False
                    if reference and reference.get("xpath"):
                        historical_xpath = reference["xpath"]
                        logger.info(f"Trying historical xpath: {historical_xpath}")
                        hist_element = scraper.get_element_by_xpath(historical_xpath)
                        if hist_element:
                            # Historical xpath still works!
                            text = extract_element_value(hist_element) or "-"
                            total_healed += 1
                            results.append(ScrapeResult(
                                field=field,
                                selector=selector,
                                value=text,
                                success=True,
                                healed=True,
                                new_selector=historical_xpath,
                                confidence=1.0
                            ))
                            await db.insert_healing_log(
                                original_selector=selector,
                                new_selector=historical_xpath,
                                success=True,
                                confidence=1.0,
                                candidates_analyzed=0,
                                strategy_used="historical_xpath",
                                healing_time_ms=0,
                                job_id=job_id
                            )
                            logger.info(f"Healed via historical xpath: {historical_xpath}")
                            healed_via_history = True
                    
                    if healed_via_history:
                        continue
                    
                    if not reference:
                        logger.warning(f"No history for {selector}, using generic reference")
                        reference = {
                            "tag_name": "div",
                            "classes": [],
                            "element_id": None
                        }
                    
                    # Fallback: full ML-based healing
                    # Get all DOM elements
                    all_elements = scraper.get_all_elements()
                    dom_dicts = [e.to_dict() for e in all_elements]
                    
                    healing_result = await healing_engine.heal(
                        original_selector=selector,
                        original_element_info=reference,
                        dom_elements=dom_dicts,
                        url=request.url
                    )
                    
                    if healing_result.success:
                        # Try new selector
                        if healing_result.new_selector.startswith('/') or 'xpath' in healing_result.new_selector.lower():
                            new_element = scraper.get_element_by_xpath(healing_result.new_selector)
                        else:
                            new_element = scraper.find_by_selector(healing_result.new_selector)
                        
                        # Store healing result
                        await db.insert_healing_log(
                            original_selector=selector,
                            new_selector=healing_result.new_selector,
                            success=True,
                            confidence=healing_result.confidence,
                            candidates_analyzed=healing_result.candidates_analyzed,
                            strategy_used=healing_result.strategy_used,
                            healing_time_ms=healing_result.healing_time_ms,
                            job_id=job_id
                        )
                        
                        results.append(ScrapeResult(
                            field=field,
                            selector=selector,
                            value=extract_element_value(new_element) if new_element else None,
                            success=True,
                            healed=True,
                            new_selector=healing_result.new_selector,
                            confidence=healing_result.confidence
                        ))
                        total_healed += 1
                    else:
                        results.append(ScrapeResult(
                            field=field,
                            selector=selector,
                            value=None,
                            success=False,
                            healed=False
                        ))
                else:
                    # Normal extraction
                    value = None
                    if element:
                        if request.extract_all:
                            # Get ALL matching elements
                            all_elements = scraper.find_all_by_selector(selector)
                            if all_elements:
                                texts = [extract_element_value(el) for el in all_elements if extract_element_value(el)]
                                value = f"[{len(texts)} matches]\n" + "\n".join(texts)
                        else:
                            value = extract_element_value(element)
                    
                    results.append(ScrapeResult(
                        field=field,
                        selector=selector,
                        value=value,
                        success=element is not None,
                        healed=False
                    ))
            
            # Take screenshot if requested
            if request.take_screenshot:
                screenshot_path = f"screenshots/{job_id}.png"
                driver.take_screenshot(screenshot_path)
        
        # Determine final status
        all_success = all(r.success for r in results)
        status = JobStatus.SUCCESS if all_success else JobStatus.FAILED
        
        # Update job in database
        await db.update_scrape_job(
            job_id=job_id,
            status=status.value,
            result={r.field: r.value for r in results},
            healing_triggered=healing_triggered
        )
        
    except Exception as e:
        logger.error(f"Scrape job {job_id} failed: {e}")
        error_message = str(e)
        status = JobStatus.FAILED
        
        await db.update_scrape_job(
            job_id=job_id,
            status="failed",
            error_message=error_message
        )
    
    execution_time = (time.time() - start_time) * 1000
    
    return ScrapeResponse(
        job_id=job_id,
        url=request.url,
        status=status,
        results=results,
        healing_triggered=healing_triggered,
        total_healed=total_healed,
        execution_time_ms=execution_time,
        screenshot_path=screenshot_path,
        error=error_message
    )


# ============ HEAL ENDPOINT ============

@router.post("/heal", response_model=HealResponse, tags=["Self-Healing"])
async def heal_selector(request: HealRequest):
    """
    Manually trigger self-healing for a failing selector.
    
    Use this endpoint when you know a selector is failing
    and want to get a healed version without running a full scrape.
    """
    start_time = time.time()
    healing_engine = get_healing_engine()
    
    try:
        # Fetch page and analyze
        with SeleniumDriver(headless=True, timeout=10) as driver:
            if not driver.navigate(request.url):
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to load {request.url}"
                )
            
            html = driver.get_page_source()
            scraper = BaseScraper(html)
            all_elements = scraper.get_all_elements()
            dom_dicts = [e.to_dict() for e in all_elements]
            
            # Use provided context or create minimal reference
            reference = request.element_context or {
                "tag_name": "div",
                "classes": [],
                "element_id": None
            }
            
            # Execute healing
            result = await healing_engine.heal(
                original_selector=request.selector,
                original_element_info=reference,
                dom_elements=dom_dicts,
                url=request.url
            )
        
        # Store result
        db = await get_database()
        await db.insert_healing_log(
            original_selector=request.selector,
            new_selector=result.new_selector,
            success=result.success,
            confidence=result.confidence,
            candidates_analyzed=result.candidates_analyzed,
            strategy_used=result.strategy_used,
            healing_time_ms=result.healing_time_ms,
            error_message=result.error_message
        )
        
        return HealResponse(
            success=result.success,
            original_selector=request.selector,
            new_selector=result.new_selector,
            confidence=result.confidence,
            strategy_used=HealingStrategy(result.strategy_used),
            candidates_analyzed=result.candidates_analyzed,
            healing_time_ms=result.healing_time_ms,
            error=result.error_message
        )
        
    except Exception as e:
        logger.error(f"Healing failed: {e}")
        return HealResponse(
            success=False,
            original_selector=request.selector,
            new_selector=None,
            confidence=0.0,
            strategy_used=HealingStrategy.ML_PREDICTION,
            candidates_analyzed=0,
            healing_time_ms=(time.time() - start_time) * 1000,
            error=str(e)
        )


# ============ LOGS ENDPOINT ============

@router.get("/stats/trend", tags=["Analytics"])
async def get_healing_trend(days: int = 7):
    """Get healing trend statistics for the last N days."""
    history = get_selector_history()
    stats = await history.get_daily_healing_stats(days=days)
    return {"trend": stats}


@router.get("/logs", response_model=LogsResponse, tags=["Monitoring"])
async def get_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    job_id: Optional[str] = None
):
    """
    Get structured logs including scrape jobs and healing attempts.
    """
    db = await get_database()
    
    # Get healing logs
    healing_logs = await db.get_healing_logs(limit=page_size * page)
    
    # Convert to LogEntry format
    logs = []
    for log in healing_logs:
        logs.append(LogEntry(
            id=log["id"],
            timestamp=datetime.fromisoformat(log["created_at"]) if isinstance(log["created_at"], str) else log["created_at"],
            level="INFO" if log["success"] else "WARNING",
            message=f"Healing {'succeeded' if log['success'] else 'failed'}: {log['original_selector']} -> {log['new_selector'] or 'N/A'}",
            job_id=log.get("job_id"),
            selector=log["original_selector"],
            metadata={
                "confidence": log["confidence"],
                "strategy": log["strategy_used"],
                "healing_time_ms": log["healing_time_ms"]
            }
        ))
    
    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated_logs = logs[start:end]
    
    return LogsResponse(
        logs=paginated_logs,
        total_count=len(logs),
        page=page,
        page_size=page_size
    )


# ============ MODEL STATUS ENDPOINT ============

@router.get("/models/status", response_model=ModelStatusResponse, tags=["Model"])
async def get_model_status():
    """
    Get ML model status, metrics, and statistics.
    """
    healing_engine = get_healing_engine()
    history_manager = get_selector_history()
    
    # Get model info from engine
    status = healing_engine.get_model_status()
    model_info = status.get("model", {})
    metrics = model_info.get("metrics", {}) or {}
    
    # Get persistent healing stats from DB
    healing_stats = await history_manager.get_aggregated_healing_stats()
    
    # Get feature importance
    feature_extractor = FeatureExtractor()
    feature_names = feature_extractor.get_feature_names()
    feature_importance = healing_engine.model.get_feature_importance(feature_names)
    
    return ModelStatusResponse(
        model=ModelMetricsResponse(
            model_type=model_info.get("model_type", "logistic"),
            is_trained=model_info.get("is_trained", False),
            accuracy=metrics.get("accuracy"),
            precision=metrics.get("precision"),
            recall=metrics.get("recall"),
            f1_score=metrics.get("f1"),
            training_samples=metrics.get("training_samples"),
            last_trained=datetime.fromisoformat(metrics["last_trained"]) if metrics.get("last_trained") else None,
            feature_importance=dict(list(feature_importance.items())[:10])  # Top 10
        ),
        healing_stats=healing_stats,
        xpath_stats=status.get("xpath_generator", {})
    )


# ============ SELECTOR HISTORY ENDPOINT ============

@router.get("/selectors/history", response_model=SelectorHistoryResponse, tags=["History"])
async def get_selector_history_endpoint(
    url: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get selector change history and patterns.
    """
    db = await get_database()
    history_manager = get_selector_history()
    
    # Get history
    raw_history = await db.get_selector_history(url=url, limit=limit)
    
    # Convert to response format
    history = []
    for record in raw_history:
        history.append(SelectorHistoryEntry(
            id=record["id"],
            url=record["url"],
            original_selector=record["original_selector"],
            new_selector=record.get("new_selector"),
            confidence=record.get("confidence"),
            strategy=record.get("strategy"),
            status=record.get("status", "active"),
            created_at=datetime.fromisoformat(record["created_at"]) if isinstance(record["created_at"], str) else record["created_at"]
        ))
    
    # Get patterns
    patterns = await history_manager.get_healing_patterns()
    
    return SelectorHistoryResponse(
        history=history,
        total_count=len(history),
        patterns=patterns
    )


# ============ SETTINGS ENDPOINT ============

@router.get("/settings", response_model=Settings, tags=["Settings"])
async def get_settings():
    """Get application settings."""
    db = await get_database()
    settings = await db.get_settings()
    if not settings:
        # Should not happen as we init with default
        return Settings()
    return settings


@router.post("/settings", response_model=Settings, tags=["Settings"])
async def update_settings(settings: Settings):
    """Update application settings."""
    db = await get_database()
    await db.update_settings(settings.dict())
    return settings


# ============ HEALTH CHECK ============

@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Check API health and component status.
    """
    try:
        db = await get_database()
        db_connected = db._connection is not None
    except Exception:
        db_connected = False
    
    healing_engine = get_healing_engine()
    model_loaded = healing_engine.model.is_trained
    
    return HealthResponse(
        status="healthy" if db_connected and model_loaded else "degraded",
        version="1.0.0",
        database_connected=db_connected,
        model_loaded=model_loaded
    )
