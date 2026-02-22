"""
AI Self-Healing Web Scraper - Main Application
Production-grade FastAPI backend with ML-powered selector recovery.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from loguru import logger
import sys

from api.routes import router
from api.product_routes import router as product_router
from storage.db import get_database
from ai_engine import SelfHealingEngine


# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO"
)
logger.add(
    "logs/scraper.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting AI Self-Healing Scraper...")
    
    # Initialize database
    db = await get_database()
    logger.info("Database connected")
    
    # Initialize ML model
    healing_engine = SelfHealingEngine(
        model_path="models/selector_model.pkl",
        confidence_threshold=0.6
    )
    logger.info(f"ML model loaded (trained: {healing_engine.model.is_trained})")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await db.disconnect()


# Create FastAPI app
app = FastAPI(
    title="AI Self-Healing Web Scraper",
    description="""
## 🤖 ML-Powered Web Scraping with Automatic Selector Recovery

This API provides intelligent web scraping with **self-healing capability**:

### Key Features
- **Automatic Failure Detection**: Identifies when selectors break
- **ML-Based Recovery**: Uses Logistic Regression to predict correct elements
- **XPath Generation**: Creates robust new selectors automatically
- **Learning**: Stores successful healings for future improvement

### How Self-Healing Works
1. Try original selector
2. If fails → analyze DOM
3. Extract features from all elements
4. ML model predicts best match
5. Generate new XPath
6. Retry and store for learning

### Tech Stack
- FastAPI + Async Python
- Selenium + BeautifulSoup
- scikit-learn (Logistic Regression)
- SQLite for history
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_timing_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = str(round(process_time, 2))
    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "code": "INTERNAL_ERROR"
        }
    )


# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(product_router, prefix="/api/v1")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """API root with welcome message."""
    return {
        "name": "AI Self-Healing Web Scraper",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
