"""
API Schemas
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============ ENUMS ============

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    HEALING = "healing"


class HealingStrategy(str, Enum):
    ID = "id"
    CLASS = "class"
    ATTRIBUTES = "attributes"
    HIERARCHY = "hierarchy"
    ML_PREDICTION = "ml_prediction"
    ERROR = "error"
    NONE = "none"


# ============ REQUEST MODELS ============

class ScrapeRequest(BaseModel):
    """Request to initiate a scraping job."""
    url: str = Field(..., description="URL to scrape")
    selectors: Dict[str, str] = Field(
        ..., 
        description="Map of field names to CSS selectors",
        example={"title": "h1.title", "price": ".product-price"}
    )
    wait_for_selector: Optional[str] = Field(
        None, 
        description="Wait for this selector before scraping"
    )
    timeout: int = Field(10, ge=1, le=60, description="Timeout in seconds")
    enable_healing: bool = Field(True, description="Enable self-healing")
    extract_all: bool = Field(False, description="Extract all matching elements instead of just the first")
    take_screenshot: bool = Field(False, description="Capture page screenshot")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/product",
                "selectors": {
                    "title": "h1.product-title",
                    "price": "span.price-value",
                    "description": ".product-description"
                },
                "enable_healing": True,
                "timeout": 15
            }
        }


class HealRequest(BaseModel):
    """Request to manually trigger healing for a selector."""
    url: str = Field(..., description="Page URL")
    selector: str = Field(..., description="Failing selector to heal")
    element_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional context about the original element"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/page",
                "selector": ".old-class-name",
                "element_context": {
                    "tag_name": "div",
                    "classes": ["old-class-name", "container"],
                    "text_content": "Expected text"
                }
            }
        }


class Settings(BaseModel):
    """Application settings."""
    api_url: str = Field("http://localhost:8000", description="Backend API URL")
    timeout: int = Field(15, ge=1, le=120, description="Request timeout in seconds")
    headless: bool = Field(True, description="Run browser in headless mode")
    confidence_threshold: float = Field(0.6, ge=0.1, le=1.0, description="Confidence threshold for healing")
    max_candidates: int = Field(100, ge=1, le=1000, description="Max candidates to analyze")
    retention_days: int = Field(30, ge=1, le=365, description="Data retention period in days")
    auto_retrain: bool = Field(False, description="Automatically retrain model")
    updated_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "api_url": "http://localhost:8000",
                "timeout": 15,
                "headless": True,
                "confidence_threshold": 0.6,
                "max_candidates": 100,
                "retention_days": 30,
                "auto_retrain": False
            }
        }


# ============ RESPONSE MODELS ============

class ScrapeResult(BaseModel):
    """Result of a scraping attempt for one selector."""
    field: str
    selector: str
    value: Optional[str]
    success: bool
    healed: bool = False
    new_selector: Optional[str] = None
    confidence: Optional[float] = None


class ScrapeResponse(BaseModel):
    """Response from scraping job."""
    job_id: str
    url: str
    status: JobStatus
    results: List[ScrapeResult]
    healing_triggered: bool = False
    total_healed: int = 0
    execution_time_ms: float
    screenshot_path: Optional[str] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "job_abc123",
                "url": "https://example.com/product",
                "status": "success",
                "results": [
                    {
                        "field": "title",
                        "selector": "h1.product-title",
                        "value": "Product Name",
                        "success": True,
                        "healed": False
                    }
                ],
                "healing_triggered": False,
                "total_healed": 0,
                "execution_time_ms": 1234.56
            }
        }


class HealResponse(BaseModel):
    """Response from healing attempt."""
    success: bool
    original_selector: str
    new_selector: Optional[str]
    confidence: float
    strategy_used: HealingStrategy
    candidates_analyzed: int
    healing_time_ms: float
    error: Optional[str] = None


class LogEntry(BaseModel):
    """Single log entry."""
    id: int
    timestamp: datetime
    level: str
    message: str
    job_id: Optional[str] = None
    selector: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LogsResponse(BaseModel):
    """Response with log entries."""
    logs: List[LogEntry]
    total_count: int
    page: int
    page_size: int


class ModelMetricsResponse(BaseModel):
    """ML model metrics."""
    model_type: str
    is_trained: bool
    accuracy: Optional[float]
    precision: Optional[float]
    recall: Optional[float]
    f1_score: Optional[float]
    training_samples: Optional[int]
    last_trained: Optional[datetime]
    feature_importance: Optional[Dict[str, float]]


class ModelStatusResponse(BaseModel):
    """Complete model status."""
    model: ModelMetricsResponse
    healing_stats: Dict[str, Any]
    xpath_stats: Dict[str, Any]


class SelectorHistoryEntry(BaseModel):
    """Single selector history entry."""
    id: int
    url: str
    original_selector: str
    new_selector: Optional[str]
    confidence: Optional[float]
    strategy: Optional[str]
    status: str
    created_at: datetime


class SelectorHistoryResponse(BaseModel):
    """Response with selector history."""
    history: List[SelectorHistoryEntry]
    total_count: int
    patterns: Dict[str, Any]


# ============ GENERAL RESPONSES ============

class HealthResponse(BaseModel):
    """API health check response."""
    status: str = "healthy"
    version: str = "1.0.0"
    database_connected: bool
    model_loaded: bool


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: str = "UNKNOWN_ERROR"


# ============ PRODUCT SCRAPER MODELS ============

class ProductScrapeRequest(BaseModel):
    """Request to scrape products from an e-commerce page."""
    url: str = Field(..., description="URL of the product listing page")
    container_xpath: str = Field(..., description="XPath of the main product container/card")
    max_products: int = Field(20, ge=1, le=200, description="Maximum products to extract")
    pagination_type: str = Field("scroll", description="Pagination method: scroll, next_button, none")
    next_button_xpath: Optional[str] = Field(None, description="XPath for next page button")
    enable_healing: bool = Field(True, description="Enable self-healing on selectors")
    timeout: int = Field(30, ge=5, le=120, description="Timeout in seconds")
    tracking_id: Optional[str] = Field(None, description="Client-generated tracking ID for live progress")


class ProductItem(BaseModel):
    """A single scraped product."""
    title: Optional[str] = None
    price: Optional[str] = None
    original_price: Optional[str] = None
    discount: Optional[str] = None
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[str] = None
    extra: Optional[Dict[str, str]] = None


class ProductScrapeResponse(BaseModel):
    """Response from product scraping job."""
    session_id: str
    url: str
    domain: str
    status: str
    products: List[ProductItem]
    total_found: int
    total_extracted: int
    execution_time_ms: float
    error: Optional[str] = None
    healed: bool = False
    healed_xpath: Optional[str] = None
    healing_confidence: Optional[float] = None


class ScrapeSession(BaseModel):
    """A saved scrape session for history."""
    id: str
    domain: str
    url: str
    session_name: str
    product_count: int
    created_at: str
