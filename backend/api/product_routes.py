"""
Product Scraper Routes
Handles product listing scraping with auto-detection of product fields.
Includes self-healing for container XPath recovery.
"""

import uuid
import time
import re
import asyncio
import json
from urllib.parse import urlparse, urljoin
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from typing import List, Dict, Optional, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from api.schemas import (
    ProductScrapeRequest, ProductScrapeResponse, ProductItem, ScrapeSession
)
from scraper.selenium_driver import SeleniumDriver
from scraper import BaseScraper, FailureDetector
from ai_engine import SelfHealingEngine
from storage.db import get_database

router = APIRouter(tags=["Product Scraping"])

# Lazy-loaded healing components
_healing_engine: Optional[SelfHealingEngine] = None
_failure_detector: Optional[FailureDetector] = None


def is_css_selector(selector: str) -> bool:
    """Detect if a selector is CSS (vs XPath)."""
    s = selector.strip()
    # XPath starts with / or ./ or (
    if s.startswith('/') or s.startswith('./') or s.startswith('('):
        return False
    # CSS indicators: starts with . # [ or contains : > ~ +
    if s.startswith('.') or s.startswith('#') or s.startswith('['):
        return True
    if any(ch in s for ch in ['>', '~', '+', ':']):
        return True
    # If it contains no / and has class-like tokens, treat as CSS
    if '/' not in s:
        return True
    return False


def get_selector_by(selector: str):
    """Return (By.CSS_SELECTOR or By.XPATH, selector) based on auto-detection."""
    if is_css_selector(selector):
        return By.CSS_SELECTOR, selector
    return By.XPATH, selector


def get_healing_engine() -> SelfHealingEngine:
    global _healing_engine
    if _healing_engine is None:
        _healing_engine = SelfHealingEngine(
            model_path="models/selector_model.pkl",
            confidence_threshold=0.6
        )
    return _healing_engine


def get_failure_detector() -> FailureDetector:
    global _failure_detector
    if _failure_detector is None:
        _failure_detector = FailureDetector()
    return _failure_detector


def extract_domain(url: str) -> str:
    """Extract clean domain name from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    return domain


def batch_extract_products_js(driver, container_elements, base_url: str, max_products: int) -> List[ProductItem]:
    """
    Extract product fields from ALL container elements in a single JavaScript
    execution.  This replaces the old per-element Selenium XPath approach
    (~30 calls per product) with ONE browser round-trip.
    """
    js_script = r"""
    var containers = arguments[0];
    var baseUrl    = arguments[1];
    var maxItems   = arguments[2];

    function absUrl(href) {
        if (!href) return null;
        if (href.startsWith('http')) return href;
        try { return new URL(href, baseUrl).href; } catch(e) { return href; }
    }

    /* Get only the DIRECT text of an element, excluding child element text.
       This avoids grabbing badges like "FEATURED BESTSELLER" from parent containers. */
    function ownText(el) {
        var text = '';
        for (var i = 0; i < el.childNodes.length; i++) {
            if (el.childNodes[i].nodeType === 3) { // TEXT_NODE
                text += el.childNodes[i].textContent;
            }
        }
        return text.trim();
    }

    /* Find the deepest (most specific) element matching a selector that has
       meaningful own text, to avoid grabbing parent container text. */
    function deepestText(el, sel) {
        var matches = el.querySelectorAll(sel);
        for (var i = matches.length - 1; i >= 0; i--) {
            var t = ownText(matches[i]);
            if (t.length > 2) return t;
        }
        // Fallback to textContent of first match
        if (matches.length > 0) {
            var tc = (matches[0].textContent || '').trim();
            if (tc.length > 2) return tc;
        }
        return null;
    }

    function extractTitle(el) {
        // Priority 1: specific product name/title selectors — get own text
        var titleSels = [
            '[class*="product-title"]', '[class*="product-name"]',
            '[class*="prod-name"]', '[class*="productName"]',
        ];
        var href = null;
        for (var i = 0; i < titleSels.length; i++) {
            var m = el.querySelector(titleSels[i]);
            if (m) {
                // Try to get own text first (avoids badges), fallback to textContent
                var t = ownText(m) || (m.textContent || '').trim();
                if (t.length > 2) {
                    var link = m.tagName === 'A' ? m : m.querySelector('a') || m.closest('a');
                    href = link ? link.href : null;
                    return {text: t, href: href};
                }
            }
        }

        // Priority 2: headings inside the card
        var headingSels = ['h2 a','h3 a','h4 a','h2','h3','h4'];
        for (var i = 0; i < headingSels.length; i++) {
            var m = el.querySelector(headingSels[i]);
            if (m) {
                var t = (m.textContent || '').trim();
                if (t.length > 2) {
                    href = m.tagName === 'A' ? m.href : (m.closest('a') || {}).href || null;
                    return {text: t, href: href};
                }
            }
        }

        // Priority 3: generic title/name selectors — but prefer anchor inside
        var genericSels = [
            '[class*="title"] a', '[class*="name"] a',
            '[class*="title"]', '[class*="name"]',
        ];
        for (var i = 0; i < genericSels.length; i++) {
            var m = el.querySelector(genericSels[i]);
            if (m) {
                var t = ownText(m);
                if (!t || t.length < 3) t = (m.textContent || '').trim();
                if (t.length > 2 && t.length < 200) {
                    href = m.tagName === 'A' ? m.href : (m.closest('a') || {}).href || null;
                    return {text: t, href: href};
                }
            }
        }

        // Fallback: first anchor with decent text
        var links = el.querySelectorAll('a');
        for (var j = 0; j < links.length; j++) {
            var lt = (links[j].textContent || '').trim();
            if (lt.length > 5 && lt.length < 200) return {text: lt, href: links[j].href};
        }
        return {text: null, href: null};
    }

    function extractPrices(el) {
        /* Strategy: find LEAF elements (no children with price text) that contain
           currency symbols or price patterns. This avoids parent wrappers that
           concatenate multiple prices + sizes + icons into one string. */
        var priceR = /[₹$€£]\s*[\d,]+(?:\.?\d{0,2})?|[\d,]+\.\d{2}/;
        var candidates = el.querySelectorAll(
            '[class*="price"], [class*="cost"], [class*="offer"], [class*="sale"], ' +
            '[class*="mrp"], [class*="amount"], span, b, strong, em, p'
        );

        var prices = [];
        var seenText = new Set();

        for (var i = 0; i < candidates.length; i++) {
            var c = candidates[i];
            // Only consider leaf-ish elements (no child elements that also match price patterns)
            var childPrices = c.querySelectorAll('[class*="price"], [class*="cost"], [class*="mrp"], [class*="amount"]');
            if (childPrices.length > 0) continue; // skip parent wrapper

            var raw = ownText(c) || (c.textContent || '').trim();
            if (!raw || raw.length > 40 || seenText.has(raw)) continue; // skip garbage
            seenText.add(raw);

            if (priceR.test(raw)) {
                // Extract the numeric value
                var numMatch = raw.replace(/[^0-9.,₹$€£]/g, '').replace(/[₹$€£,]/g, '');
                var num = parseFloat(numMatch);
                if (!isNaN(num) && num > 0) {
                    prices.push({num: num, text: raw.trim()});
                }
            }
        }

        prices.sort(function(a, b) { return a.num - b.num; });
        var price = prices.length > 0 ? prices[0].text : null;
        var origPrice = prices.length > 1 ? prices[prices.length - 1].text : null;

        // Discount
        var disc = null;
        var discEls = el.querySelectorAll('[class*="discount"], [class*="off"], [class*="save"]');
        for (var i = 0; i < discEls.length; i++) {
            var dt = (discEls[i].textContent || '').trim();
            if (dt.length < 30 && (/\d+%/.test(dt) || dt.toLowerCase().indexOf('off') > -1)) {
                disc = dt;
                break;
            }
        }
        if (!disc) {
            // Try to find discount pattern in small text elements
            var smallEls = el.querySelectorAll('span, small, b');
            for (var j = 0; j < smallEls.length; j++) {
                var st = (smallEls[j].textContent || '').trim();
                var dm = st.match(/(\d+%\s*(?:off|Off|OFF))/);
                if (dm) { disc = dm[1]; break; }
            }
        }
        return {price: price, original_price: origPrice, discount: disc};
    }

    function extractImage(el) {
        var imgSels = ['img[class*="product"]', 'img[class*="image"]', 'picture img', 'img'];
        for (var i = 0; i < imgSels.length; i++) {
            var img = el.querySelector(imgSels[i]);
            if (img) {
                var src = img.src || img.getAttribute('data-src') ||
                          img.getAttribute('data-lazy-src') || img.srcset || '';
                if (src.indexOf(',') > -1 && src.indexOf(' ') > -1) src = src.split(',')[0].split(' ')[0];
                if (src && !src.startsWith('data:')) return absUrl(src);
            }
        }
        return null;
    }

    function extractRating(el) {
        var rEls = el.querySelectorAll('[class*="rating"], [class*="star"], [class*="review"]');
        for (var i = 0; i < rEls.length; i++) {
            var t = ownText(rEls[i]) || (rEls[i].textContent || '').trim();
            if (t && t.length < 20 && /\d[\d.]*/.test(t)) return t;
        }
        return null;
    }

    function extractDesc(el) {
        var dEls = el.querySelectorAll('[class*="desc"], [class*="subtitle"], [class*="detail"]');
        for (var i = 0; i < dEls.length; i++) {
            var t = (dEls[i].textContent || '').trim();
            if (t && t.length > 10 && t.length < 300) return t;
        }
        return null;
    }

    var results = [];
    var limit = Math.min(containers.length, maxItems);
    for (var c = 0; c < limit; c++) {
        var el = containers[c];
        var titleInfo = extractTitle(el);
        var priceInfo = extractPrices(el);
        results.push({
            title: titleInfo.text,
            product_url: absUrl(titleInfo.href),
            price: priceInfo.price,
            original_price: priceInfo.original_price,
            discount: priceInfo.discount,
            image_url: extractImage(el),
            rating: extractRating(el),
            description: extractDesc(el)
        });
    }
    return JSON.stringify(results);
    """

    try:
        elements_to_extract = container_elements[:max_products]
        raw = driver.execute_script(js_script, elements_to_extract, base_url, max_products)
        items_data = json.loads(raw) if isinstance(raw, str) else raw

        products = []
        for item in items_data:
            if item.get("title") or item.get("image_url"):
                products.append(ProductItem(**item))
        return products
    except Exception as e:
        logger.warning(f"JS batch extraction failed: {e}  — falling back to per-element extraction")
        # Compact fallback: just grab title + image via JS per element
        products = []
        for el in container_elements[:max_products]:
            try:
                data = driver.execute_script("""
                    var el = arguments[0], bu = arguments[1];
                    var a = el.querySelector('h2 a,h3 a,h2,h3,[class*="title"],[class*="name"]');
                    var img = el.querySelector('img');
                    return JSON.stringify({
                        title: a ? a.textContent.trim() : null,
                        product_url: a && a.href ? a.href : null,
                        image_url: img ? (img.src || img.getAttribute('data-src')) : null,
                        price: null, original_price: null, discount: null,
                        rating: null, description: null
                    });
                """, el, base_url)
                d = json.loads(data) if isinstance(data, str) else data
                if d.get("title") or d.get("image_url"):
                    products.append(ProductItem(**d))
            except:
                continue
        return products


def scroll_to_load_more(driver: SeleniumDriver, target_count: int, 
                         container_xpath: str, timeout: int = 30) -> int:
    """Scroll the page to load more products (infinite scroll)."""
    last_count = 0
    scroll_attempts = 0
    max_scroll_attempts = 20
    start_time = time.time()
    
    while scroll_attempts < max_scroll_attempts and (time.time() - start_time) < timeout:
        # Get current product count
        by, val = get_selector_by(container_xpath)
        containers = driver.find_elements(val, by=by)
        current_count = len(containers)
        
        if current_count >= target_count:
            logger.info(f"Reached target count: {current_count} >= {target_count}")
            break
        
        if current_count == last_count:
            scroll_attempts += 1
        else:
            scroll_attempts = 0
        
        last_count = current_count
        
        # Scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)
        
        logger.debug(f"Scroll attempt {scroll_attempts}, products found: {current_count}")
    
    return last_count


def paginate_with_button(driver: SeleniumDriver, next_button_xpath: str, 
                          container_xpath: str, target_count: int,
                          timeout: int = 30) -> int:
    """Click next page button to load more products."""
    total_count = 0
    pages_loaded = 0
    max_pages = 10
    start_time = time.time()
    
    while pages_loaded < max_pages and (time.time() - start_time) < timeout:
        by, val = get_selector_by(container_xpath)
        containers = driver.find_elements(val, by=by)
        total_count = len(containers)
        
        if total_count >= target_count:
            break
        
        try:
            next_btn = driver.find_element(next_button_xpath, by=By.XPATH, wait=False)
            if next_btn:
                next_btn.click()
                time.sleep(2)
                pages_loaded += 1
            else:
                break
        except:
            break
    
    return total_count


def drill_down_to_product_cards(driver, parent_element, base_xpath: str) -> tuple:
    """
    When only 1 large container is found, drill down to find repeating
    child elements that represent individual product cards.
    Uses a single JavaScript execution for speed instead of multiple
    Selenium find_elements calls.
    
    Returns:
        (child_elements, drilled_xpath) — the list of card elements and the
        refined XPath that was used, or (None, None) if drill-down failed.
    """
    # Run a single JS script that checks all patterns at once
    js_script = """
    var parent = arguments[0];
    var patterns = [
        // Class-based patterns
        {css: '[class*="product-card"]', name: 'product-card'},
        {css: '[class*="productWrapper"]', name: 'productWrapper'},
        {css: '[class*="product-item"]', name: 'product-item'},
        {css: '[class*="product_card"]', name: 'product_card'},
        {css: '[class*="product-box"]', name: 'product-box'},
        {css: '[class*="product-tile"]', name: 'product-tile'},
        {css: '[class*="product-grid-item"]', name: 'product-grid-item'},
        {css: '[class*="productItem"]', name: 'productItem'},
        {css: '[class*="card"]', name: 'card'},
        {css: '[class*="item"]', name: 'item'},
        // Data attributes
        {css: '[data-product]', name: 'data-product'},
        {css: '[data-product-id]', name: 'data-product-id'},
        {css: '[data-sku]', name: 'data-sku'},
        {css: '[data-item]', name: 'data-item'},
    ];
    
    var results = [];
    for (var i = 0; i < patterns.length; i++) {
        var els = parent.querySelectorAll(patterns[i].css);
        if (els.length >= 3) {
            // Quick heuristic: check if first element has img + text
            var sample = els[0];
            var hasImg = sample.querySelector('img') !== null;
            var hasText = sample.textContent.trim().length > 10;
            var score = els.length + (hasImg ? 100 : 0) + (hasText ? 50 : 0);
            if (3 <= els.length && els.length <= 200) score += 50;
            results.push({name: patterns[i].name, css: patterns[i].css, count: els.length, score: score});
        }
    }
    
    // Also check direct children pattern
    var childTags = ['div', 'li', 'article', 'a'];
    for (var t = 0; t < childTags.length; t++) {
        var directKids = parent.querySelectorAll(':scope > ' + childTags[t]);
        if (directKids.length >= 3) {
            var s = directKids[0];
            var hI = s.querySelector('img') !== null;
            var hT = s.textContent.trim().length > 10;
            var sc = directKids.length + (hI ? 100 : 0) + (hT ? 50 : 0);
            if (3 <= directKids.length && directKids.length <= 200) sc += 50;
            results.push({name: ':scope>' + childTags[t], css: ':scope > ' + childTags[t], count: directKids.length, score: sc, direct: true});
        }
    }
    
    // Sort by score descending
    results.sort(function(a, b) { return b.score - a.score; });
    
    return JSON.stringify(results.slice(0, 5));
    """
    
    try:
        result_json = driver.execute_script(js_script, parent_element)
        candidates = json.loads(result_json) if isinstance(result_json, str) else result_json
        
        if not candidates:
            logger.info("Drill-down: no repeating child patterns found via JS")
            return None, None
        
        for c in candidates:
            logger.info(f"Drill-down candidate: '{c['name']}' → {c['count']} elements (score={c['score']})")
        
        # Use the best candidate
        best = candidates[0]
        css_sel = best['css']
        
        # Now fetch elements using the winning CSS selector via Selenium
        if best.get('direct'):
            # For direct children, use XPath
            tag = css_sel.split('> ')[-1].strip()
            elements = parent_element.find_elements(By.XPATH, f'./{tag}')
        else:
            elements = parent_element.find_elements(By.CSS_SELECTOR, css_sel)
        
        if elements and len(elements) >= 3:
            full_xpath = f"{base_xpath} → drilled({best['name']}, {len(elements)} cards)"
            logger.info(f"Drill-down SUCCESS: {len(elements)} product cards via '{best['name']}'")
            return elements, full_xpath
        
    except Exception as e:
        logger.warning(f"JS drill-down failed: {e}")
    
    return None, None


# ============ PROGRESS TRACKING ============

# In-memory progress store for active scraping sessions
_scrape_progress: Dict[str, Dict[str, Any]] = {}


def update_progress(session_id: str, step: str, detail: str = "", progress: int = 0, products: list = None):
    """Update progress for a scraping session, optionally including partial products."""
    entry = _scrape_progress.get(session_id, {})
    entry.update({
        "step": step,
        "detail": detail,
        "progress": progress,
        "timestamp": time.time()
    })
    if products is not None:
        entry["products"] = products
    _scrape_progress[session_id] = entry
    logger.info(f"[{session_id}] Progress: {step} — {detail}")


def clear_progress(session_id: str):
    """Clean up progress entry when done."""
    _scrape_progress.pop(session_id, None)


@router.get("/product-scrape/progress/{session_id}")
async def scrape_progress_sse(session_id: str):
    """SSE endpoint for real-time scrape progress updates."""
    async def event_generator():
        last_step = None
        idle_count = 0
        while True:
            progress = _scrape_progress.get(session_id)
            if progress:
                current_step = f"{progress['step']}:{progress['detail']}"
                if current_step != last_step:
                    last_step = current_step
                    idle_count = 0
                    data = json.dumps(progress)
                    yield f"data: {data}\n\n"
                    
                    # If we sent "done" or "error", end the stream
                    if progress["step"] in ("done", "error"):
                        break
                else:
                    idle_count += 1
            else:
                idle_count += 1
            
            # Timeout after ~2 minutes of no updates
            if idle_count > 240:
                yield f"data: {json.dumps({'step': 'timeout', 'detail': 'No updates', 'progress': 0})}\n\n"
                break
                
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/product-scrape", response_model=ProductScrapeResponse)
async def scrape_products(request: ProductScrapeRequest):
    """Scrape products from an e-commerce page with self-healing support."""
    # Use client-provided tracking_id if available, otherwise generate one
    session_id = request.tracking_id or f"ps_{uuid.uuid4().hex[:12]}"
    start_time = time.time()
    domain = extract_domain(request.url)
    healed = False
    healed_xpath = None
    healing_confidence = None
    
    logger.info(f"Product scrape started: {domain} | container: {request.container_xpath} | max: {request.max_products}")
    update_progress(session_id, "initializing", f"Starting scrape for {domain}", 5)
    
    driver = None
    db = await get_database()
    try:
        driver = SeleniumDriver(headless=True, timeout=request.timeout)
        update_progress(session_id, "navigating", f"Loading {domain}...", 10)
        
        if not driver.navigate(request.url):
            update_progress(session_id, "error", "Failed to navigate to URL", 0)
            raise HTTPException(status_code=500, detail="Failed to navigate to URL")
        
        active_xpath = request.container_xpath
        selector_by, selector_val = get_selector_by(active_xpath)
        
        # Wait for product containers to appear
        update_progress(session_id, "searching", "Waiting for product containers to appear...", 20)
        container_found = False
        try:
            WebDriverWait(driver.driver, min(request.timeout, 15)).until(
                EC.presence_of_element_located((selector_by, selector_val))
            )
            container_found = True
            update_progress(session_id, "found", "Container selector matched!", 30)
        except:
            logger.warning(f"Original selector not found: {active_xpath} (detected as {'CSS' if selector_by == By.CSS_SELECTOR else 'XPath'})")
            update_progress(session_id, "healing", "Selector not found — trying self-healing...", 25)
        
        # ========== SELF-HEALING ==========
        if not container_found and request.enable_healing:
            logger.info("Container XPath failed — triggering self-healing...")
            
            # Step 1: Try historical XPath from previous successful scrapes
            reference = await db.get_last_successful_selector(request.url, active_xpath)
            if reference and reference.get("xpath"):
                historical_xpath = reference["xpath"]
                logger.info(f"Trying historical xpath: {historical_xpath}")
                try:
                    test_els = driver.find_elements(historical_xpath, by=By.XPATH)
                    if test_els:
                        active_xpath = historical_xpath
                        container_found = True
                        healed = True
                        healed_xpath = historical_xpath
                        healing_confidence = 1.0
                        logger.info(f"Self-healed via historical xpath: {historical_xpath} ({len(test_els)} elements)")
                        await db.insert_healing_log(
                            original_selector=request.container_xpath,
                            new_selector=historical_xpath,
                            success=True, confidence=1.0,
                            candidates_analyzed=0,
                            strategy_used="historical_xpath",
                            healing_time_ms=0,
                            job_id=session_id,
                        )
                except Exception as e:
                    logger.debug(f"Historical xpath failed: {e}")
            
            # Step 2: ML-based healing — analyze DOM for similar containers
            if not container_found:
                try:
                    page_html = driver.get_page_source()
                    scraper = BaseScraper(page_html)
                    healing_engine = get_healing_engine()
                    
                    ref_info = reference if reference else {
                        "tag_name": "div", "classes": [], "element_id": None
                    }
                    
                    all_elements = scraper.get_all_elements()
                    dom_dicts = [e.to_dict() for e in all_elements]
                    
                    healing_result = await healing_engine.heal(
                        original_selector=active_xpath,
                        original_element_info=ref_info,
                        dom_elements=dom_dicts,
                        url=request.url
                    )
                    
                    if healing_result.success:
                        new_xpath = healing_result.new_selector
                        test_els = driver.find_elements(new_xpath, by=By.XPATH)
                        if test_els:
                            active_xpath = new_xpath
                            container_found = True
                            healed = True
                            healed_xpath = new_xpath
                            healing_confidence = healing_result.confidence
                            logger.info(f"Self-healed via ML: {new_xpath} (confidence: {healing_result.confidence:.2f}, {len(test_els)} elements)")
                            await db.insert_healing_log(
                                original_selector=request.container_xpath,
                                new_selector=new_xpath,
                                success=True,
                                confidence=healing_result.confidence,
                                candidates_analyzed=healing_result.candidates_analyzed,
                                strategy_used=healing_result.strategy_used,
                                healing_time_ms=healing_result.healing_time_ms,
                                job_id=session_id,
                            )
                except Exception as e:
                    logger.warning(f"ML healing attempt failed: {e}")
            
            if not container_found:
                await db.insert_healing_log(
                    original_selector=request.container_xpath,
                    new_selector=None,
                    success=False, confidence=0,
                    candidates_analyzed=0,
                    strategy_used="all_failed",
                    healing_time_ms=(time.time() - start_time) * 1000,
                    job_id=session_id,
                )
        
        if not container_found:
            raise HTTPException(
                status_code=404, 
                detail=f"No elements found with XPath: {request.container_xpath}. Self-healing {'was attempted but failed' if request.enable_healing else 'is disabled'}."
            )
        
        # Save successful selector fingerprint for future healing
        try:
            page_html = driver.get_page_source()
            scraper = BaseScraper(page_html)
            el = scraper.get_element_by_xpath(active_xpath)
            if el:
                info = scraper.extract_element_info(el).to_dict()
                await db.save_selector_history(request.url, request.container_xpath, info)
        except Exception as e:
            logger.debug(f"Failed to save selector fingerprint: {e}")
        
        # Handle pagination to load more products
        if request.pagination_type == "scroll":
            update_progress(session_id, "scrolling", "Scrolling page to load more products...", 40)
            scroll_to_load_more(driver, request.max_products, active_xpath, request.timeout)
        elif request.pagination_type == "next_button" and request.next_button_xpath:
            update_progress(session_id, "paginating", "Clicking next page button...", 40)
            paginate_with_button(
                driver, request.next_button_xpath, active_xpath,
                request.max_products, request.timeout
            )
        
        # Find all product containers
        update_progress(session_id, "counting", "Counting product containers...", 50)
        final_by, final_val = get_selector_by(active_xpath)
        container_elements = driver.find_elements(final_val, by=final_by)
        total_found = len(container_elements)
        logger.info(f"Found {total_found} product containers")
        
        # Debug: log tag/class info of found containers
        for idx, el in enumerate(container_elements[:5]):
            try:
                tag = el.tag_name
                classes = el.get_attribute("class") or ""
                el_id = el.get_attribute("id") or ""
                child_count = len(el.find_elements(By.XPATH, './*'))
                text_preview = (el.text or "")[:80].replace('\n', ' ')
                logger.info(
                    f"Container [{idx}]: <{tag}> class='{classes[:100]}' "
                    f"id='{el_id}' children={child_count} text='{text_preview}...'"
                )
            except Exception as dbg_err:
                logger.debug(f"Debug log failed for container [{idx}]: {dbg_err}")
        
        # Auto drill-down: if only 1 container found, it's likely the
        # parent wrapper — drill into it to find individual product cards
        if total_found <= 2:
            update_progress(session_id, "drill_down", f"Only {total_found} wrapper(s) — drilling down to find individual product cards...", 55)
            logger.info(
                f"Only {total_found} container(s) found — attempting "
                f"drill-down to find individual product cards..."
            )
            drilled_elements, drilled_xpath = drill_down_to_product_cards(
                driver, container_elements[0], active_xpath
            )
            if drilled_elements and len(drilled_elements) > total_found:
                logger.info(
                    f"Drill-down successful: {len(drilled_elements)} product "
                    f"cards found (was {total_found} wrapper containers)"
                )
                container_elements = drilled_elements
                total_found = len(container_elements)
                
                # Debug: log first few drilled-down cards
                for idx, el in enumerate(container_elements[:3]):
                    try:
                        tag = el.tag_name
                        classes = el.get_attribute("class") or ""
                        text_preview = (el.text or "")[:80].replace('\n', ' ')
                        logger.info(
                            f"Product card [{idx}]: <{tag}> class='{classes[:80]}' "
                            f"text='{text_preview}...'"
                        )
                    except:
                        pass
            else:
                logger.warning(
                    "Drill-down did not find more elements — proceeding "
                    "with original containers"
                )
        
        # Extract product data from ALL containers in a single JS call (instant)
        extract_count = min(len(container_elements), request.max_products)
        update_progress(session_id, "extracting", f"Extracting data from {extract_count} products...", 60)
        
        products = batch_extract_products_js(
            driver, container_elements, request.url, request.max_products
        )
        
        # Stream the extracted products to the progress store
        products_data = [p.model_dump() for p in products]
        update_progress(
            session_id, "extracting",
            f"Extracted {len(products)} of {extract_count} products",
            90, products=products_data
        )
        logger.info(f"Batch extraction complete: {len(products)} products extracted via JS")
        
        execution_time = (time.time() - start_time) * 1000
        
        # Save session to DB
        session_name = f"{domain} - {len(products)} products"
        await db.save_scrape_session(
            session_id=session_id,
            domain=domain,
            url=request.url,
            session_name=session_name,
            container_xpath=active_xpath,
            products=[p.model_dump() for p in products],
            execution_time_ms=execution_time
        )
        
        status = "success" if products else "no_products"
        if healed:
            status = "healed"
        
        update_progress(session_id, "done", f"Completed! {len(products)} products extracted in {execution_time/1000:.1f}s", 100, products=products_data)
        
        response = ProductScrapeResponse(
            session_id=session_id,
            url=request.url,
            domain=domain,
            status=status,
            products=products,
            total_found=total_found,
            total_extracted=len(products),
            execution_time_ms=round(execution_time, 2),
            healed=healed,
            healed_xpath=healed_xpath,
            healing_confidence=healing_confidence,
        )
        
        # Clean up progress after a short delay so frontend can read final state
        await asyncio.sleep(2)
        clear_progress(session_id)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Product scrape failed: {e}")
        update_progress(session_id, "error", f"Failed: {str(e)[:100]}", 0)
        await asyncio.sleep(2)
        clear_progress(session_id)
        return ProductScrapeResponse(
            session_id=session_id,
            url=request.url,
            domain=domain,
            status="failed",
            products=[],
            total_found=0,
            total_extracted=0,
            execution_time_ms=round(execution_time, 2),
            error=str(e)
        )
    finally:
        if driver:
            driver.close()


@router.get("/scrape-sessions")
async def get_scrape_sessions(limit: int = 50):
    """Get recent scrape sessions for history."""
    db = await get_database()
    sessions = await db.get_scrape_sessions(limit)
    return {"sessions": sessions}


@router.get("/scrape-sessions/{session_id}")
async def get_session_detail(session_id: str):
    """Get full details of a scrape session including products."""
    db = await get_database()
    session = await db.get_session_by_id(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/validate-xpath")
async def validate_xpath(payload: dict):
    """
    Validate an XPath against a live URL.
    Returns match count and preview snippets.
    """
    url = payload.get("url", "").strip()
    xpath = payload.get("xpath", "").strip()
    
    if not url or not xpath:
        raise HTTPException(status_code=400, detail="Both url and xpath are required")
    
    driver = None
    try:
        driver = SeleniumDriver(headless=True, timeout=15)
        if not driver.navigate(url):
            raise HTTPException(status_code=500, detail="Failed to load URL")
        
        # Wait a moment for JS rendering
        import time as _time
        _time.sleep(2)
        
        elements = driver.find_elements(xpath, by=get_selector_by(xpath)[0])
        match_count = len(elements)
        
        # Build preview of first 5 matches
        previews = []
        for el in elements[:5]:
            try:
                tag = el.tag_name
                text = el.text[:100] if el.text else ""
                # Get key attributes
                attrs = {}
                for a in ["class", "id", "src", "href", "alt"]:
                    val = el.get_attribute(a)
                    if val:
                        attrs[a] = val[:80]
                previews.append({
                    "tag": tag,
                    "text": text,
                    "attributes": attrs,
                })
            except:
                continue
        
        return {
            "valid": match_count > 0,
            "match_count": match_count,
            "previews": previews,
            "xpath": xpath,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"XPath validation failed: {e}")
        return {
            "valid": False,
            "match_count": 0,
            "previews": [],
            "xpath": xpath,
            "error": str(e),
        }
    finally:
        if driver:
            driver.close()
